"""Validation records derived from generic FeatureSurface comparisons."""
from __future__ import annotations
from datetime import datetime, timezone

from workbench.core.schema import ValidationRun, ValidationResult
from workbench.migrations.feature_surface import FeatureSurfaceComparison


def build_feature_surface_validation(
    comparison: FeatureSurfaceComparison,
    *,
    run_id: str,
    source_snapshot_id: str,
    target_snapshot_id: str,
) -> tuple[ValidationRun, list[ValidationResult]]:
    now=datetime.now(timezone.utc).isoformat()
    entity_aligned=not comparison.source_only_entity_ids and not comparison.target_only_entity_ids

    run=ValidationRun(
        run_id=run_id,
        name=f"Feature surface comparison: {comparison.feature_id}",
        source_snapshot_id=source_snapshot_id,
        target_snapshot_id=target_snapshot_id,
        feature_id=comparison.feature_id,
        status="VERIFIED",
        started_at=now,
        finished_at=now,
        metadata={
            "comparison_status":comparison.status,
            "source_family":comparison.source_family,
            "target_family":comparison.target_family,
            "shared_roles":list(comparison.shared_roles),
            "source_only_roles":list(comparison.source_only_roles),
            "target_only_roles":list(comparison.target_only_roles),
        },
    )

    entity_validation=ValidationResult(
        validation_id=f"{run_id}:entity-coverage",
        validation_type="FEATURE_SURFACE_ENTITY_COVERAGE",
        subject_id=comparison.feature_id,
        status="VERIFIED" if entity_aligned else "FAILED",
        run_id=run_id,
        source=source_snapshot_id,
        target=target_snapshot_id,
        notes=[
            f"Shared entity IDs: {len(comparison.shared_entity_ids)}",
            f"Source-only entity IDs: {len(comparison.source_only_entity_ids)}",
            f"Target-only entity IDs: {len(comparison.target_only_entity_ids)}",
            "This validates entity-set coverage only; artifact role/layout drift is recorded separately and is not treated as feature equivalence.",
        ],
    )
    return run,[entity_validation]
