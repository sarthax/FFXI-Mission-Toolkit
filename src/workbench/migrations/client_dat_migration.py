"""Reviewable, drift-aware client item-DAT patch orchestration.

This first generalized Workbench write slice supports PATCH_EXISTING only. Planning and
approval are side-effect free; the low-level item_dat_tools writer is invoked only by the
explicit approved apply function.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
import hashlib
import json
from pathlib import Path
import shutil
from typing import Any, Callable, Mapping, Sequence

from workbench.editors.items import dat_tools as item_dat_tools
from workbench.client.dat_adapter import ClientDatRecord, ItemDatAdapter
from workbench.migrations.generated_output import GeneratedOutput


@dataclass(frozen=True)
class ClientDatOperation:
    operation_id: str
    item_id: int
    fields: dict[str, Any]
    expected_fields: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ClientDatReadiness:
    status: str
    operations: tuple[dict[str, Any], ...]


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _record_fingerprint(record: ClientDatRecord) -> str:
    payload={
        "item_id":record.item_id,
        "snapshot_id":record.snapshot_id,
        "category":record.category,
        "layout":record.layout,
        "format":record.format,
        "source_path":record.source_path,
        "record_index":record.record_index,
        "fields":record.fields,
    }
    raw=json.dumps(payload,sort_keys=True,default=str,separators=(",",":"))
    return _sha256_text(raw)


def _operation_preview(record: ClientDatRecord | None, op: ClientDatOperation) -> dict[str, Any]:
    if record is None:
        return {
            "operation_id":op.operation_id,
            "item_id":op.item_id,
            "operation_type":"PATCH_EXISTING",
            "status":"MANUAL_REQUIRED",
            "reason":"Client item DAT record is missing.",
            "fields":dict(op.fields),
            "expected_fields":dict(op.expected_fields),
        }
    mismatches={
        key:{"expected":expected,"actual":record.fields.get(key)}
        for key,expected in op.expected_fields.items()
        if record.fields.get(key) != expected
    }
    if mismatches:
        status="MANUAL_REQUIRED"
        reason="Expected current client fields do not match."
    elif not op.fields:
        status="MANUAL_REQUIRED"
        reason="No client fields were requested for patching."
    else:
        status="READY"
        reason="Existing client record matches reviewed expectations."
    return {
        "operation_id":op.operation_id,
        "item_id":op.item_id,
        "operation_type":"PATCH_EXISTING",
        "status":status,
        "reason":reason,
        "snapshot_id":record.snapshot_id,
        "category":record.category,
        "layout":record.layout,
        "format":record.format,
        "source_path":record.source_path,
        "record_index":record.record_index,
        "source_fingerprint":_record_fingerprint(record),
        "fields":dict(op.fields),
        "expected_fields":dict(op.expected_fields),
        "field_mismatches":mismatches,
        "metadata":dict(op.metadata),
    }


def build_client_dat_patch_plan(
    plan_id: str,
    adapter: ItemDatAdapter,
    operations: Sequence[ClientDatOperation],
) -> GeneratedOutput:
    """Build a proposal-only plan. Does not call any DAT writer."""
    previews=[_operation_preview(adapter.read(op.item_id),op) for op in operations]
    status="READY" if previews and all(row["status"]=="READY" for row in previews) else "MANUAL_REQUIRED"
    payload={
        "schema":1,
        "kind":"WORKBENCH_CLIENT_DAT_PLAN",
        "plan_id":plan_id,
        "status":status,
        "snapshot_id":adapter.snapshot_id,
        "operations":previews,
    }
    return GeneratedOutput(
        output_id=f"generated:client-dat-plan:{plan_id}",
        relative_path=f"proposals/client-dat/{plan_id}.json",
        artifact_type="CLIENT_DAT_PLAN",
        content=json.dumps(payload,indent=2,sort_keys=True)+"\n",
        generator="workbench.client_dat_migration",
        metadata={"proposal_only":True,"plan_status":status,"operation_count":len(previews)},
    )


def assess_client_dat_plan_for_approval(
    plan_content: str | Mapping[str,Any],
    adapter: ItemDatAdapter,
) -> ClientDatReadiness:
    payload=json.loads(plan_content) if isinstance(plan_content,str) else dict(plan_content)
    if payload.get("kind")!="WORKBENCH_CLIENT_DAT_PLAN" or payload.get("schema")!=1:
        return ClientDatReadiness("BLOCKED",({"status":"BLOCKED","reason":"Unsupported client DAT plan format."},))
    if payload.get("status")!="READY":
        return ClientDatReadiness("BLOCKED",({"status":"BLOCKED","reason":"Client DAT plan itself is not READY."},))
    rows=[]
    for reviewed in payload.get("operations",[]):
        item_id=int(reviewed["item_id"])
        current=adapter.read(item_id)
        if current is None:
            rows.append({"operation_id":reviewed["operation_id"],"item_id":item_id,"status":"DRIFTED","reason":"Client DAT record is missing."})
            continue
        current_fp=_record_fingerprint(current)
        if current_fp != reviewed.get("source_fingerprint"):
            rows.append({"operation_id":reviewed["operation_id"],"item_id":item_id,"status":"DRIFTED","reason":"Client DAT record differs from reviewed plan."})
            continue
        rows.append({"operation_id":reviewed["operation_id"],"item_id":item_id,"status":"READY_FOR_APPROVAL"})
    overall="READY_FOR_APPROVAL" if rows and all(row["status"]=="READY_FOR_APPROVAL" for row in rows) else "DRIFTED"
    return ClientDatReadiness(overall,tuple(rows))


def build_client_dat_approval_request(
    plan_content: str,
    readiness: ClientDatReadiness,
    *,
    request_id: str,
) -> GeneratedOutput:
    payload={
        "schema":1,
        "kind":"WORKBENCH_CLIENT_DAT_APPROVAL_REQUEST",
        "request_id":request_id,
        "status":"PENDING",
        "requires_human_approval":True,
        "client_dat_plan_sha256":_sha256_text(plan_content),
        "technical_readiness":readiness.status,
    }
    return GeneratedOutput(
        output_id=f"generated:client-dat-approval:{request_id}",
        relative_path=f"proposals/approvals/{request_id}.json",
        artifact_type="CLIENT_DAT_APPROVAL_REQUEST",
        content=json.dumps(payload,indent=2,sort_keys=True)+"\n",
        generator="workbench.client_dat_migration",
        metadata={"proposal_only":True,"requires_human_approval":True,"approval_status":"PENDING"},
    )


def _eligible(plan_content: str, readiness: ClientDatReadiness, approval: str | Mapping[str,Any] | None) -> tuple[bool,str]:
    if readiness.status!="READY_FOR_APPROVAL":
        return False,"Technical client DAT readiness is not READY_FOR_APPROVAL."
    if approval is None:
        return False,"No human approval record was supplied."
    payload=json.loads(approval) if isinstance(approval,str) else dict(approval)
    if payload.get("kind")!="WORKBENCH_CLIENT_DAT_APPROVAL_REQUEST" or payload.get("schema")!=1:
        return False,"Unsupported client DAT approval record."
    if payload.get("client_dat_plan_sha256")!=_sha256_text(plan_content):
        return False,"Approval record does not match the reviewed client DAT plan."
    if payload.get("status")!="APPROVED":
        return False,"Client DAT approval is not APPROVED."
    return True,"Technical readiness and matching human approval are present."


def apply_approved_client_dat_plan(
    plan_content: str,
    adapter: ItemDatAdapter,
    approval_record: str | Mapping[str,Any],
    journal_path: Path,
    *,
    writer: Callable[[int,dict[str,Any]],dict[str,Any]] = item_dat_tools.patch_client_item,
) -> dict[str,Any]:
    """Apply an approved PATCH_EXISTING plan and journal low-level backup metadata."""
    readiness=assess_client_dat_plan_for_approval(plan_content,adapter)
    ok,reason=_eligible(plan_content,readiness,approval_record)
    if not ok:
        raise ValueError(f"Client DAT plan is not eligible for apply: {reason}")
    payload=json.loads(plan_content)
    entries=[]
    for op in payload.get("operations",[]):
        result=dict(writer(int(op["item_id"]),dict(op.get("fields") or {})))
        if not result.get("ok"):
            raise ValueError(f"Client DAT writer failed for item {op['item_id']}")
        entries.append({
            "operation_id":op["operation_id"],
            "item_id":int(op["item_id"]),
            "fields":dict(op.get("fields") or {}),
            "dat":result.get("dat"),
            "dat_ui":result.get("dat_ui"),
            "category":result.get("category"),
            "record_index":result.get("record_index"),
            "format":result.get("format"),
            "target":result.get("target"),
            "target_existed":bool(result.get("target_existed")),
            "backup_path":result.get("backup_path"),
        })
    journal={
        "schema":1,
        "kind":"WORKBENCH_CLIENT_DAT_APPLY_JOURNAL",
        "status":"APPLIED",
        "client_dat_plan_sha256":_sha256_text(plan_content),
        "entries":entries,
    }
    journal_path.parent.mkdir(parents=True,exist_ok=True)
    journal_path.write_text(json.dumps(journal,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    return journal


def rollback_client_dat_apply(journal_path: Path) -> dict[str,Any]:
    """Restore recorded low-level snapshots, or remove an overlay created by first write."""
    journal=json.loads(journal_path.read_text(encoding="utf-8"))
    if journal.get("kind")!="WORKBENCH_CLIENT_DAT_APPLY_JOURNAL":
        raise ValueError("Unsupported client DAT apply journal")
    restored=[]
    removed=[]
    for entry in reversed(journal.get("entries",[])):
        target=Path(str(entry.get("dat") or ""))
        backup_raw=entry.get("backup_path")
        if entry.get("target_existed"):
            if not backup_raw:
                raise ValueError(f"Missing backup path for item {entry.get('item_id')}")
            backup=Path(str(backup_raw))
            if not backup.is_file():
                raise FileNotFoundError(backup)
            target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(backup,target)
            restored.append(int(entry["item_id"]))
        else:
            if target.exists():
                target.unlink()
            removed.append(int(entry["item_id"]))
    journal["status"]="ROLLED_BACK"
    journal["rollback"]={"restored_item_ids":restored,"removed_item_ids":removed}
    journal_path.write_text(json.dumps(journal,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    return journal
