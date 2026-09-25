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
) -> dict:
    artifact_map={a.artifact_id:a for a in artifacts}

    steps=[]
    for order,action in enumerate(plan.ordered_actions, start=1):
        artifact=artifact_map.get(action.artifact_id) if action.artifact_id else None
        steps.append({
            "order":order,
            "action_id":action.action_id,
            "action":action.action,
            "status":action.status,
            "artifact_id":action.artifact_id,
            "path":artifact.path if artifact else None,
            "artifact_type":artifact.artifact_type if artifact else None,
            "backend":_backend_for(artifact),
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
