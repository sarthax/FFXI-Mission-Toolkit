"""Integrity checks for packaged patch plans and approval requests."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path


@dataclass(frozen=True)
class PatchPackageIntegrityResult:
    status: str
    issues: tuple[str, ...]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_patch_package_integrity(package_root: Path) -> PatchPackageIntegrityResult:
    journal_path=package_root/"WORKBENCH_GENERATED_OUTPUTS.json"
    if not journal_path.is_file():
        return PatchPackageIntegrityResult("NOT_APPLICABLE",())

    journal=json.loads(journal_path.read_text(encoding="utf-8"))
    outputs=journal.get("outputs",[])
    patch_plans=[]
    approvals=[]
    for record in outputs:
        artifact_type=str(record.get("artifact_type") or "").upper()
        relative=record.get("relative_path")
        if not relative:
            continue
        path=package_root/str(relative)
        if artifact_type=="PATCH_PLAN":
            patch_plans.append(path)
        elif artifact_type=="PATCH_APPROVAL_REQUEST":
            approvals.append(path)

    if not patch_plans and not approvals:
        return PatchPackageIntegrityResult("NOT_APPLICABLE",())

    issues=[]
    plan_hashes={}
    for path in patch_plans:
        if not path.is_file():
            issues.append(f"Missing packaged patch plan: {path.relative_to(package_root).as_posix()}")
            continue
        try:
            payload=json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            issues.append(f"Invalid patch plan JSON: {path.relative_to(package_root).as_posix()}")
            continue
        if payload.get("kind")!="WORKBENCH_PATCH_PLAN":
            issues.append(f"Unexpected patch plan kind: {path.relative_to(package_root).as_posix()}")
            continue
        plan_hashes[_sha256(path)]=path

    for path in approvals:
        if not path.is_file():
            issues.append(f"Missing packaged approval request: {path.relative_to(package_root).as_posix()}")
            continue
        try:
            payload=json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            issues.append(f"Invalid approval request JSON: {path.relative_to(package_root).as_posix()}")
            continue
        if payload.get("kind")!="WORKBENCH_PATCH_APPROVAL_REQUEST":
            issues.append(f"Unexpected approval request kind: {path.relative_to(package_root).as_posix()}")
            continue
        requested_hash=payload.get("patch_plan_sha256")
        if requested_hash not in plan_hashes:
            issues.append(
                f"Approval request is not linked to a packaged patch plan: "
                f"{path.relative_to(package_root).as_posix()}"
            )

    status="COHERENT" if not issues else "FAILED"
    return PatchPackageIntegrityResult(status,tuple(issues))
