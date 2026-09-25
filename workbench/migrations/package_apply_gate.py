"""Apply-readiness checks for assembled migration packages."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json

from workbench.migrations.package_cohesion import verify_package_cohesion


@dataclass(frozen=True)
class ApplyReadiness:
    status: str
    reasons: tuple[str, ...]


def assess_apply_readiness(package_root: Path) -> ApplyReadiness:
    cohesion=verify_package_cohesion(package_root)
    reasons=list(cohesion.issues)
    if cohesion.status!="COHERENT":
        return ApplyReadiness("BLOCKED",tuple(reasons or ("Package cohesion failed",)))

    validation_path=package_root/"WORKBENCH_VALIDATION_PACKAGE.json"
    if not validation_path.is_file():
        return ApplyReadiness("BLOCKED",("Validation package is missing",))

    validation=json.loads(validation_path.read_text(encoding="utf-8"))
    validation_status=validation.get("status")
    if validation_status=="BLOCKED":
        return ApplyReadiness("BLOCKED",("Validation package is BLOCKED",))
    if validation_status=="MANUAL_REQUIRED":
        return ApplyReadiness("MANUAL_REQUIRED",("Validation package requires manual review",))
    if validation_status!="READY":
        return ApplyReadiness("BLOCKED",(f"Unsupported validation status: {validation_status}",))

    return ApplyReadiness("READY",())
