"""Assemble a complete non-destructive migration package workspace."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
from typing import Iterable

from workbench.migrations.generated_output import (
    GeneratedOutput,
    GeneratedOutputResult,
    materialize_generated_outputs,
    write_generated_output_journal,
)
from workbench.migrations.package_materialize import (
    MaterializeResult,
    materialize_package,
    write_materialization_journal,
)
from workbench.migrations.package_validation import build_validation_package


@dataclass(frozen=True)
class PackageAssemblyResult:
    package_root: Path
    source_result: MaterializeResult
    generated_result: GeneratedOutputResult
    validation_status: str
    manifest_path: Path
    validation_path: Path
    source_journal_path: Path
    generated_journal_path: Path
    status: str


def assemble_migration_package(
    manifest: dict,
    source_root: Path,
    package_root: Path,
    *,
    generated_outputs: Iterable[GeneratedOutput] = (),
    overwrite: bool = False,
) -> PackageAssemblyResult:
    """Build a reviewable package workspace without applying anything to a target."""
    package_root.mkdir(parents=True,exist_ok=True)

    source_result=materialize_package(
        manifest,
        source_root,
        package_root,
        overwrite=overwrite,
    )
    source_journal=write_materialization_journal(
        package_root,
        manifest,
        source_result,
    )

    generated_result=materialize_generated_outputs(
        generated_outputs,
        package_root,
        overwrite=overwrite,
    )
    generated_journal=write_generated_output_journal(
        package_root,
        generated_result,
    )

    validation=build_validation_package(manifest)

    manifest_path=package_root/"WORKBENCH_PACKAGE_MANIFEST.json"
    manifest_path.write_text(
        json.dumps(manifest,indent=2,sort_keys=True)+"\n",
        encoding="utf-8",
    )

    validation_path=package_root/"WORKBENCH_VALIDATION_PACKAGE.json"
    validation_path.write_text(
        json.dumps(validation,indent=2,sort_keys=True)+"\n",
        encoding="utf-8",
    )

    if source_result.status=="INCOMPLETE":
        status="INCOMPLETE"
    elif validation["status"]=="BLOCKED":
        status="BLOCKED"
    elif validation["status"]=="MANUAL_REQUIRED":
        status="MANUAL_REQUIRED"
    else:
        status="ASSEMBLED"

    return PackageAssemblyResult(
        package_root=package_root,
        source_result=source_result,
        generated_result=generated_result,
        validation_status=validation["status"],
        manifest_path=manifest_path,
        validation_path=validation_path,
        source_journal_path=source_journal,
        generated_journal_path=generated_journal,
        status=status,
    )
