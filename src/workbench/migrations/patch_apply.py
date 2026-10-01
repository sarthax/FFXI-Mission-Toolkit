"""Deterministic patch-plan application behind explicit approval gates."""
from __future__ import annotations

from pathlib import Path
import hashlib
import json
import shutil
from typing import Any, Mapping

from workbench.migrations.patch_approval import assess_patch_plan_for_approval
from workbench.migrations.patch_approval_request import assess_patch_execution_eligibility
from workbench.migrations.patch_operations import PatchOperation, preview_patch_operations


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _safe_path(root: Path, relative_path: str) -> Path:
    root=root.resolve()
    path=(root/relative_path).resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"Patch target escapes root: {relative_path}") from exc
    return path


def apply_approved_patch_plan(
    patch_plan_content: str,
    target_root: Path,
    approval_record: str | Mapping[str,Any],
    journal_path: Path,
) -> dict:
    readiness=assess_patch_plan_for_approval(patch_plan_content,target_root)
    eligibility=assess_patch_execution_eligibility(
        patch_plan_content,
        readiness,
        approval_record,
    )
    if eligibility.status!="ELIGIBLE_FOR_DETERMINISTIC_APPLY":
        raise ValueError(f"Patch plan is not eligible for apply: {eligibility.status} - {eligibility.reason}")

    payload=json.loads(patch_plan_content)
    backup_root=journal_path.parent/(journal_path.stem+"_backups")
    entries=[]

    for target in payload.get("targets",[]):
        relative=str(target["target_path"])
        path=_safe_path(target_root,relative)
        source_bytes=path.read_bytes()
        source_text=source_bytes.decode("utf-8",errors="replace")

        operations=tuple(
            PatchOperation(
                operation_id=str(op["operation_id"]),
                target_path=str(op["target_path"]),
                operation_type=str(op["operation_type"]),
                anchor=str(op["anchor"]),
                content=str(op["content"]),
                expected_occurrences=int(op.get("expected_occurrences",1)),
                metadata=dict(op.get("metadata") or {}),
            )
            for op in target.get("operations",[])
        )
        preview=preview_patch_operations(source_text,operations)
        if preview.status!="READY":
            raise ValueError(f"Patch preview is no longer READY for {relative}")

        backup=_safe_path(backup_root,relative)
        backup.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(path,backup)

        path.write_text(preview.output,encoding="utf-8",newline="\n")
        entries.append({
            "target_path":relative,
            "backup_path":backup.relative_to(journal_path.parent.resolve()).as_posix(),
            "before_sha256":_sha256_bytes(source_bytes),
            "after_sha256":_sha256_bytes(path.read_bytes()),
        })

    journal={
        "schema":1,
        "kind":"WORKBENCH_PATCH_APPLY_JOURNAL",
        "status":"APPLIED",
        "target_root":str(target_root.resolve()),
        "patch_plan_sha256":_sha256_bytes(patch_plan_content.encode("utf-8")),
        "entries":entries,
    }
    journal_path.parent.mkdir(parents=True,exist_ok=True)
    journal_path.write_text(json.dumps(journal,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    return journal


def rollback_patch_apply(journal_path: Path) -> dict:
    journal=json.loads(journal_path.read_text(encoding="utf-8"))
    if journal.get("kind")!="WORKBENCH_PATCH_APPLY_JOURNAL":
        raise ValueError("Unsupported patch apply journal")

    target_root=Path(journal["target_root"])
    restored=[]
    for entry in reversed(journal.get("entries",[])):
        target=_safe_path(target_root,str(entry["target_path"]))
        backup=_safe_path(journal_path.parent,str(entry["backup_path"]))
        if not backup.is_file():
            raise FileNotFoundError(backup)
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(backup,target)
        restored.append(str(entry["target_path"]))

    journal["status"]="ROLLED_BACK"
    journal["rollback"]={"restored":restored}
    journal_path.write_text(json.dumps(journal,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    return journal
