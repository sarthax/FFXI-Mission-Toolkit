"""Unified lifecycle assessment for packaged Workbench patch plans."""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Mapping

from workbench.migrations.package_cohesion import verify_package_cohesion
from workbench.migrations.patch_approval import assess_patch_plan_for_approval
from workbench.migrations.patch_approval_request import assess_patch_execution_eligibility


@dataclass(frozen=True)
class PatchLifecycleStatus:
    status: str
    reason: str
    patch_plan_path: str | None = None
    approval_request_path: str | None = None


def _generated_outputs(package_root: Path) -> list[dict]:
    journal=package_root/"WORKBENCH_GENERATED_OUTPUTS.json"
    if not journal.is_file():
        return []
    payload=json.loads(journal.read_text(encoding="utf-8"))
    return list(payload.get("outputs",[]))


def _first_path(package_root: Path, outputs: list[dict], artifact_type: str) -> Path | None:
    for record in outputs:
        if str(record.get("artifact_type") or "").upper()!=artifact_type:
            continue
        relative=record.get("relative_path")
        if relative:
            return package_root/str(relative)
    return None


def assess_patch_lifecycle(
    package_root: Path,
    target_root: Path,
    *,
    approval_record: str | Mapping[str,Any] | None = None,
    apply_journal_path: Path | None = None,
) -> PatchLifecycleStatus:
    cohesion=verify_package_cohesion(package_root)
    if cohesion.status!="COHERENT":
        return PatchLifecycleStatus(
            "PACKAGE_FAILED",
            "; ".join(cohesion.issues) or "Package cohesion failed.",
        )

    outputs=_generated_outputs(package_root)
    patch_plan_path=_first_path(package_root,outputs,"PATCH_PLAN")
    approval_path=_first_path(package_root,outputs,"PATCH_APPROVAL_REQUEST")
    if patch_plan_path is None or not patch_plan_path.is_file():
        return PatchLifecycleStatus("NOT_APPLICABLE","No packaged patch plan is present.")

    patch_plan_content=patch_plan_path.read_text(encoding="utf-8")
    readiness=assess_patch_plan_for_approval(patch_plan_content,target_root)
    if readiness.status!="READY_FOR_APPROVAL":
        return PatchLifecycleStatus(
            "DRIFTED",
            f"Patch plan technical readiness is {readiness.status}.",
            patch_plan_path.relative_to(package_root).as_posix(),
            approval_path.relative_to(package_root).as_posix() if approval_path else None,
        )

    if apply_journal_path is not None and apply_journal_path.is_file():
        journal=json.loads(apply_journal_path.read_text(encoding="utf-8"))
        if journal.get("kind")=="WORKBENCH_PATCH_APPLY_JOURNAL":
            state=journal.get("status")
            if state in {"APPLIED","ROLLED_BACK"}:
                return PatchLifecycleStatus(
                    state,
                    "Patch apply journal records this lifecycle state.",
                    patch_plan_path.relative_to(package_root).as_posix(),
                    approval_path.relative_to(package_root).as_posix() if approval_path else None,
                )

    if approval_record is None and approval_path is not None and approval_path.is_file():
        approval_record=approval_path.read_text(encoding="utf-8")

    eligibility=assess_patch_execution_eligibility(
        patch_plan_content,
        readiness,
        approval_record,
    )
    return PatchLifecycleStatus(
        eligibility.status,
        eligibility.reason,
        patch_plan_path.relative_to(package_root).as_posix(),
        approval_path.relative_to(package_root).as_posix() if approval_path else None,
    )
