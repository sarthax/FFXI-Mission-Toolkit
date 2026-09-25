"""Machine-readable migration package manifests.

Converts a dependency-ordered PackagePlan plus canonical Artifact records into a
portable manifest. This is planning metadata only; no source, SQL, DAT, or target
files are modified.
"""
from __future__ import annotations

from dataclasses import asdict
from typing import Iterable

from workbench.core.schema import Artifact
from workbench.migrations.package_plan import PackagePlan
from workbench.migrations.backend_registry import default_backend_registry
from workbench.migrations.generated_output import GeneratedOutput


def _backend_for(artifact: Artifact | None) -> str:
    if artifact is None:
        return "manual"
    kind=(artifact.artifact_type or "").upper()
    if kind == "LUA":
        return "lua"
    if kind == "SQL":
        return "sql"
    return "manual"


def build_package_manifest(
    plan: PackagePlan,
    artifacts: Iterable[Artifact] = (),
    *,
    feature_id: str | None = None,
    source_snapshot_id: str | None = None,
    target_snapshot_id: str | None = None,
    source_family: str | None = None,
    target_family: str | None = None,
    backend_registry=None,
) -> dict:
    artifact_map={a.artifact_id:a for a in artifacts}
    if backend_registry is None and source_family and target_family:
        backend_registry=default_backend_registry()

    steps=[]
    for order,action in enumerate(plan.ordered_actions, start=1):
        artifact=artifact_map.get(action.artifact_id) if action.artifact_id else None
        backend=_backend_for(artifact)
        converter_backend_id=None
        conversion_status="NOT_APPLICABLE"
        if backend in {"lua","sql"}:
            if backend_registry is not None and source_family and target_family:
                resolved=backend_registry.resolve(source_family,target_family,artifact.artifact_type)
                converter_backend_id=resolved.backend_id if resolved else None
                conversion_status=(getattr(resolved,"support_level","SUPPORTED") if resolved else "UNSUPPORTED")
            else:
                conversion_status="UNSPECIFIED"
        steps.append({
            "order":order,
            "action_id":action.action_id,
            "action":action.action,
            "status":action.status,
            "artifact_id":action.artifact_id,
            "path":artifact.path if artifact else None,
            "artifact_type":artifact.artifact_type if artifact else None,
            "backend":backend,
            "converter_backend_id":converter_backend_id,
            "conversion_status":conversion_status,
            "reason":action.reason,
            "metadata":dict(action.metadata),
        })

    return {
        "schema":2,
        "kind":"WORKBENCH_MIGRATION_PACKAGE_PLAN",
        "migration":{
            "migration_id":plan.migration_id,
            "feature_id":feature_id,
            "source_snapshot_id":source_snapshot_id,
            "target_snapshot_id":target_snapshot_id,
            "source_family":source_family,
            "target_family":target_family,
            "status":plan.status,
        },
        "execution":{
            "steps":steps,
            "dependency_links":[
                {"dependent_action_id":dependent,"prerequisite_action_id":prerequisite}
                for dependent,prerequisite in plan.dependency_links
            ],
            "cycle_action_ids":list(plan.cycle_action_ids),
        },
        "excluded_actions":[
            {
                "action_id":action.action_id,
                "action":action.action,
                "artifact_id":action.artifact_id,
                "status":action.status,
                "reason":action.reason,
            }
            for action in plan.excluded_actions
        ],
        "artifacts":[
            asdict(artifact)
            for artifact in sorted(artifact_map.values(), key=lambda a:a.artifact_id)
        ],
    }


def converter_scope(manifest: dict, backend: str) -> tuple[str, ...]:
    """Return planned relative paths for one deterministic converter backend."""
    paths=[]
    for step in manifest.get("execution",{}).get("steps",[]):
        if step.get("backend") != backend:
            continue
        path=step.get("path")
        if path:
            paths.append(str(path).replace("\\","/"))
    return tuple(paths)


def attach_generated_outputs(
    manifest: dict,
    outputs: Iterable[GeneratedOutput],
) -> dict:
    """Attach already-target-formatted generated artifacts to a package manifest.

    Generated outputs do not require a source converter backend. They remain explicit
    generated artifacts and are validated separately before any apply step.
    """
    result={
        **manifest,
        "migration":dict(manifest.get("migration",{})),
        "execution":{
            **dict(manifest.get("execution",{})),
            "steps":[dict(step) for step in manifest.get("execution",{}).get("steps",[])],
        },
        "artifacts":[dict(a) for a in manifest.get("artifacts",[])],
        "generated_artifacts":[dict(a) for a in manifest.get("generated_artifacts",[])],
    }
    generated=result["generated_artifacts"]
    known={str(item.get("output_id")) for item in generated}
    for output in outputs:
        if output.output_id in known:
            raise ValueError(f"Duplicate generated output in package manifest: {output.output_id}")
        generated.append({
            "output_id":output.output_id,
            "path":output.relative_path.replace("\\","/"),
            "artifact_type":output.artifact_type,
            "generator":output.generator,
            "metadata":dict(output.metadata),
            "target_formatted":not bool(output.metadata.get("proposal_only")),
            "proposal_only":bool(output.metadata.get("proposal_only")),
            "conversion_status":"NOT_REQUIRED",
        })
        known.add(output.output_id)
    generated.sort(key=lambda item:item["output_id"])
    return result
