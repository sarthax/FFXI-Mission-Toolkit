"""Unified review summary for assembled Workbench migration packages."""
from __future__ import annotations

from dataclasses import dataclass, asdict
import json
from pathlib import Path
from typing import Any

from workbench.migrations.package_apply_gate import assess_apply_readiness
from workbench.migrations.package_cohesion import verify_package_cohesion
from workbench.migrations.patch_lifecycle import assess_patch_lifecycle


@dataclass(frozen=True)
class PackageReviewSummary:
    status: str
    migration_id: str | None
    feature_id: str | None
    execution_step_count: int
    excluded_action_count: int
    generated_artifact_count: int
    validation_status: str
    cohesion_status: str
    apply_readiness: str
    patch_lifecycle: str


def _read_json(path: Path) -> dict[str,Any]:
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def build_package_review_summary(
    package_root: Path,
    target_root: Path,
) -> PackageReviewSummary:
    manifest=_read_json(package_root/"WORKBENCH_PACKAGE_MANIFEST.json")
    validation=_read_json(package_root/"WORKBENCH_VALIDATION_PACKAGE.json")
    generated=_read_json(package_root/"WORKBENCH_GENERATED_OUTPUTS.json")

    cohesion=verify_package_cohesion(package_root)
    apply=assess_apply_readiness(package_root)
    patch=assess_patch_lifecycle(package_root,target_root)

    migration=manifest.get("migration",{})
    generated_count=len(generated.get("outputs",[]))

    if cohesion.status!="COHERENT":
        status="PACKAGE_FAILED"
    elif patch.status not in {"NOT_APPLICABLE","ELIGIBLE_FOR_DETERMINISTIC_APPLY"}:
        status=patch.status
    elif validation.get("status")=="MANUAL_REQUIRED":
        status="MANUAL_REQUIRED"
    elif apply.status=="READY":
        status="READY"
    else:
        status=apply.status

    return PackageReviewSummary(
        status=status,
        migration_id=migration.get("migration_id"),
        feature_id=migration.get("feature_id"),
        execution_step_count=len(manifest.get("execution",{}).get("steps",[])),
        excluded_action_count=len(manifest.get("excluded_actions",[])),
        generated_artifact_count=generated_count,
        validation_status=str(validation.get("status") or "UNKNOWN"),
        cohesion_status=cohesion.status,
        apply_readiness=apply.status,
        patch_lifecycle=patch.status,
    )


def package_review_summary_dict(package_root: Path, target_root: Path) -> dict[str,Any]:
    return asdict(build_package_review_summary(package_root,target_root))
