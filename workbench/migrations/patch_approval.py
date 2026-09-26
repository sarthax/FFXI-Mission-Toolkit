"""Drift-aware approval checks for review-only Workbench patch plans."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from workbench.migrations.patch_operations import PatchOperation, preview_patch_operations


@dataclass(frozen=True)
class PatchApprovalTarget:
    target_path: str
    status: str
    reason: str | None = None


@dataclass(frozen=True)
class PatchApprovalResult:
    status: str
    targets: tuple[PatchApprovalTarget, ...]


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _safe_target(root: Path, relative_path: str) -> Path:
    root=root.resolve()
    path=(root/relative_path).resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"Patch target escapes root: {relative_path}") from exc
    return path


def assess_patch_plan_for_approval(
    patch_plan: str | Mapping[str,Any],
    target_root: Path,
) -> PatchApprovalResult:
    payload=json.loads(patch_plan) if isinstance(patch_plan,str) else dict(patch_plan)
    if payload.get("kind")!="WORKBENCH_PATCH_PLAN" or payload.get("schema")!=1:
        return PatchApprovalResult(
            "BLOCKED",
            (PatchApprovalTarget("<plan>","BLOCKED","Unsupported patch plan format."),),
        )
    if payload.get("status")!="READY":
        return PatchApprovalResult(
            "BLOCKED",
            (PatchApprovalTarget("<plan>","BLOCKED","Patch plan itself is not READY."),),
        )

    results=[]
    for target in payload.get("targets",[]):
        relative=str(target.get("target_path") or "")
        try:
            path=_safe_target(target_root,relative)
        except ValueError as exc:
            results.append(PatchApprovalTarget(relative,"BLOCKED",str(exc)))
            continue
        if not path.is_file():
            results.append(PatchApprovalTarget(relative,"DRIFTED","Target file is missing."))
            continue

        source_text=path.read_text(encoding="utf-8",errors="replace")
        if _sha256_text(source_text)!=target.get("source_sha256"):
            results.append(PatchApprovalTarget(relative,"DRIFTED","Target source hash differs from the reviewed patch plan."))
            continue

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
            results.append(PatchApprovalTarget(relative,"DRIFTED","Patch anchors no longer replay cleanly."))
            continue
        if _sha256_text(preview.output)!=target.get("preview_sha256"):
            results.append(PatchApprovalTarget(relative,"DRIFTED","Patch preview hash differs from the reviewed plan."))
            continue
        results.append(PatchApprovalTarget(relative,"READY_FOR_APPROVAL"))

    overall="READY_FOR_APPROVAL" if results and all(r.status=="READY_FOR_APPROVAL" for r in results) else "DRIFTED"
    return PatchApprovalResult(overall,tuple(results))
