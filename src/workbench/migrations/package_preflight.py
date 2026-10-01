"""Artifact-level preflight for conditional migration backends."""
from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from workbench.migrations.backend_registry import default_backend_registry


@dataclass(frozen=True)
class PreflightResult:
    path: str
    backend_id: str | None
    status: str
    issues: tuple[dict[str, Any], ...] = ()


def preflight_manifest_artifacts(
    manifest: dict,
    source_root: Path,
    *,
    backend_registry=None,
) -> tuple[dict, tuple[PreflightResult, ...]]:
    registry=backend_registry or default_backend_registry()
    result={
        **manifest,
        "migration":dict(manifest.get("migration",{})),
        "execution":{
            **dict(manifest.get("execution",{})),
            "steps":[dict(step) for step in manifest.get("execution",{}).get("steps",[])],
        },
        "artifacts":[dict(item) for item in manifest.get("artifacts",[])],
        "generated_artifacts":[dict(item) for item in manifest.get("generated_artifacts",[])],
    }
    migration=result.get("migration",{})
    source_family=migration.get("source_family")
    target_family=migration.get("target_family")
    findings=[]

    for step in result["execution"]["steps"]:
        if step.get("conversion_status")!="CONDITIONAL":
            continue
        path=step.get("path")
        artifact_type=step.get("artifact_type")
        if not path or not source_family or not target_family:
            findings.append(PreflightResult(
                str(path),
                step.get("converter_backend_id"),
                "MANUAL_REQUIRED",
                ({"type":"MISSING_PREFLIGHT_CONTEXT"},),
            ))
            continue

        backend=registry.resolve(source_family,target_family,artifact_type)
        if backend is None:
            findings.append(PreflightResult(
                str(path),None,"MANUAL_REQUIRED",
                ({"type":"BACKEND_NOT_FOUND"},),
            ))
            continue

        source_path=(source_root/str(path)).resolve()
        try:
            source_path.relative_to(source_root.resolve())
        except ValueError:
            findings.append(PreflightResult(
                str(path),backend.backend_id,"MANUAL_REQUIRED",
                ({"type":"PATH_ESCAPE"},),
            ))
            continue

        if not source_path.is_file():
            findings.append(PreflightResult(
                str(path),backend.backend_id,"MANUAL_REQUIRED",
                ({"type":"SOURCE_MISSING"},),
            ))
            continue

        text=source_path.read_text(encoding="utf-8",errors="replace")
        converted=backend.convert(text)
        findings.append(PreflightResult(
            str(path),backend.backend_id,converted.status,converted.issues,
        ))
        step["preflight_status"]=converted.status
        step["preflight_issue_count"]=len(converted.issues)
        if converted.status=="CONVERTED":
            step["conversion_status"]="SUPPORTED"
            step["metadata"]={
                **dict(step.get("metadata",{})),
                "conditional_backend_preflight":"PASSED",
            }
        else:
            step["metadata"]={
                **dict(step.get("metadata",{})),
                "conditional_backend_preflight":"MANUAL_REQUIRED",
            }

    return result,tuple(findings)
