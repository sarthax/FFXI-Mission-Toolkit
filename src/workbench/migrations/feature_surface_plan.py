"""Conservative migration planning from semantic FeatureSurface comparisons."""
from __future__ import annotations

import hashlib
from dataclasses import replace
from typing import Iterable, Mapping

from workbench.core.schema import MigrationAction
from workbench.migrations.feature_surface import FeatureSurface, FeatureSurfaceComparison


def _id(migration_id: str, role: str, path: str) -> str:
    digest=hashlib.sha256(f"{migration_id}|{role}|{path}".encode("utf-8")).hexdigest()[:12]
    return f"surface:{digest}"


def plan_feature_surface(
    source: FeatureSurface,
    comparison: FeatureSurfaceComparison,
    migration_id: str,
) -> list[MigrationAction]:
    """Translate semantic comparison into conservative artifact actions.

    If target capabilities and entity coverage are aligned, physical representation
    differences alone do not require copying source artifacts. Otherwise unresolved
    source artifacts remain MANUAL_REVIEW until a plugin/backend proves a safe rule.
    """
    entity_aligned=not comparison.source_only_entity_ids and not comparison.target_only_entity_ids
    capability_aligned=comparison.capability_coverage_status=="CAPABILITIES_ALIGNED"
    semantic_aligned=entity_aligned and capability_aligned

    target_roles=set(comparison.shared_roles) | set(comparison.target_only_roles)
    actions=[]
    for artifact in source.artifacts:
        if semantic_aligned and artifact.role in comparison.shared_roles:
            action="NOT_REQUIRED"
            status="COMPATIBLE"
            reason="Target feature has aligned behavior and a matching implementation role."
        elif semantic_aligned:
            action="MANUAL_REVIEW"
            status="MANUAL_REQUIRED"
            reason="Behavior is aligned, but this source-only artifact role still requires an explicit representation rule before migration can be suppressed."
        elif artifact.role in target_roles:
            action="MANUAL_REVIEW"
            status="MANUAL_REQUIRED"
            reason="A target artifact role exists, but feature-level semantic coverage is not fully aligned."
        else:
            action="MANUAL_REVIEW"
            status="MANUAL_REQUIRED"
            reason="Source artifact role has no direct target role and no verified migration rule proves how it should be represented."

        actions.append(MigrationAction(
            action_id=_id(migration_id,artifact.role,artifact.path),
            migration_id=migration_id,
            action=action,
            status=status,
            reason=reason,
            metadata={
                "feature_id":source.feature_id,
                "source_role":artifact.role,
                "source_path":artifact.path,
                "artifact_type":artifact.artifact_type,
                "semantic_alignment":semantic_aligned,
                "role_alignment":"SHARED" if artifact.role in comparison.shared_roles else "SOURCE_ONLY",
                "capability_coverage_status":comparison.capability_coverage_status,
                "entity_coverage_aligned":entity_aligned,
            },
        ))

    for capability in comparison.source_only_capabilities:
        actions.append(MigrationAction(
            action_id=f"capability:{migration_id}:{capability}",
            migration_id=migration_id,
            action="MANUAL_REVIEW",
            status="MANUAL_REQUIRED",
            reason="Required source capability has no target capability observation.",
            metadata={
                "feature_id":source.feature_id,
                "capability":capability,
                "gap_type":"SOURCE_ONLY_CAPABILITY",
            },
        ))

    for drift in comparison.capability_status_drift:
        capability=drift["capability"]
        actions.append(MigrationAction(
            action_id=f"capability-status:{migration_id}:{capability}",
            migration_id=migration_id,
            action="MANUAL_REVIEW",
            status="MANUAL_REQUIRED",
            reason="Source and target declare the same capability with different confidence/status.",
            metadata={
                "feature_id":source.feature_id,
                "capability":capability,
                "gap_type":"CAPABILITY_STATUS_DRIFT",
                "source_status":drift["source_status"],
                "target_status":drift["target_status"],
            },
        ))

    if comparison.source_only_entity_ids or comparison.target_only_entity_ids:
        actions.append(MigrationAction(
            action_id=f"entity-coverage:{migration_id}:{source.feature_id}",
            migration_id=migration_id,
            action="MANUAL_REVIEW",
            status="MANUAL_REQUIRED",
            reason="Source and target feature surfaces reference different entity membership.",
            metadata={
                "feature_id":source.feature_id,
                "gap_type":"ENTITY_COVERAGE_DRIFT",
                "source_only_entity_ids":list(comparison.source_only_entity_ids),
                "target_only_entity_ids":list(comparison.target_only_entity_ids),
            },
        ))

    for drift in comparison.role_path_drift:
        actions.append(MigrationAction(
            action_id=_id(migration_id,f"path-drift:{drift['role']}","|".join(drift["source_paths"])),
            migration_id=migration_id,
            action="MANUAL_REVIEW",
            status="MANUAL_REQUIRED",
            reason="The same semantic artifact role is represented at different source/target paths and no verified path/representation rule suppresses review.",
            metadata={
                "feature_id":source.feature_id,
                "gap_type":"ROLE_PATH_DRIFT",
                "role":drift["role"],
                "source_paths":list(drift["source_paths"]),
                "target_paths":list(drift["target_paths"]),
            },
        ))

    return actions


def bind_surface_actions_to_artifacts(
    actions: Iterable[MigrationAction],
    role_artifact_ids: Mapping[str,str],
) -> tuple[MigrationAction, ...]:
    """Attach canonical artifact IDs to role-based feature-surface actions."""
    bound=[]
    for action in actions:
        role=str(action.metadata.get("source_role") or "")
        artifact_id=role_artifact_ids.get(role)
        if artifact_id:
            bound.append(replace(action,artifact_id=artifact_id))
    return tuple(bound)
