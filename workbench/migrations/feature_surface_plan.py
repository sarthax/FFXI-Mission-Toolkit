"""Conservative migration planning from semantic FeatureSurface comparisons."""
from __future__ import annotations

import hashlib

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
        if semantic_aligned:
            action="NOT_REQUIRED"
            status="COMPATIBLE"
            reason="Target feature has aligned behavioral capabilities and entity coverage; representation drift alone does not require migration."
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

    return actions
