"""Cohesion checks for assembled migration package workspaces."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import hashlib
import json


@dataclass(frozen=True)
class PackageCohesionResult:
    status: str
    issues: tuple[str, ...]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_package_cohesion(package_root: Path) -> PackageCohesionResult:
    issues=[]
    manifest_path=package_root/"WORKBENCH_PACKAGE_MANIFEST.json"
    validation_path=package_root/"WORKBENCH_VALIDATION_PACKAGE.json"
    source_journal_path=package_root/"WORKBENCH_MATERIALIZATION.json"
    generated_journal_path=package_root/"WORKBENCH_GENERATED_OUTPUTS.json"

    required=[manifest_path,validation_path,source_journal_path,generated_journal_path]
    missing=[p.name for p in required if not p.is_file()]
    if missing:
        return PackageCohesionResult("INCOMPLETE",tuple(f"Missing {name}" for name in missing))

    manifest=json.loads(manifest_path.read_text(encoding="utf-8"))
    validation=json.loads(validation_path.read_text(encoding="utf-8"))
    source_journal=json.loads(source_journal_path.read_text(encoding="utf-8"))
    generated_journal=json.loads(generated_journal_path.read_text(encoding="utf-8"))

    migration_id=manifest.get("migration",{}).get("migration_id")
    if validation.get("migration",{}).get("migration_id")!=migration_id:
        issues.append("Validation package migration_id does not match manifest")
    if source_journal.get("migration",{}).get("migration_id")!=migration_id:
        issues.append("Source journal migration_id does not match manifest")

    for record in source_journal.get("artifacts",[]):
        rel=record.get("package_path")
        expected=record.get("sha256")
        path=package_root/rel if rel else None
        if path is None or not path.is_file():
            issues.append(f"Missing staged source artifact: {rel}")
        elif expected and _sha256(path)!=expected:
            issues.append(f"Hash mismatch for staged source artifact: {rel}")

    for record in generated_journal.get("outputs",generated_journal.get("artifacts",[])):
        rel=record.get("package_path") or record.get("path")
        expected=record.get("sha256")
        path=package_root/rel if rel else None
        if path is None or not path.is_file():
            issues.append(f"Missing generated artifact: {rel}")
        elif expected and _sha256(path)!=expected:
            issues.append(f"Hash mismatch for generated artifact: {rel}")

    status="COHERENT" if not issues else "FAILED"
    return PackageCohesionResult(status,tuple(issues))
