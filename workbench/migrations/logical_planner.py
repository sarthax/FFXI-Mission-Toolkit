"""Generic migration planning from source-neutral logical comparisons.

The planner is deliberately conservative: equivalence produces NOT_REQUIRED;
unexplained field differences require review until a source/target-specific rule
can prove a safe conversion.
"""
from __future__ import annotations
import hashlib
import json
from workbench.core.schema import MigrationAction
from workbench.adapters.servers.logical import LogicalComparison
from workbench.migrations.record_match import RecordMatch


def _stable_suffix(comparison: LogicalComparison) -> str:
    payload=json.dumps({
        "type":comparison.logical_type,
        "identity":list(comparison.identity),
    },sort_keys=True,default=str).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:12]


def plan_logical_comparison(comparison: LogicalComparison, migration_id: str) -> list[MigrationAction]:
    suffix=_stable_suffix(comparison)
    if comparison.status=="EQUIVALENT":
        return [MigrationAction(
            action_id=f"logical:{suffix}:equivalent",
            migration_id=migration_id,
            action="NOT_REQUIRED",
            status="COMPATIBLE",
            reason="Source and target logical records are equivalent after adapter normalization.",
            metadata={"logical_type":comparison.logical_type,"identity":list(comparison.identity)},
        )]

    actions=[]
    for diff in comparison.differences:
        actions.append(MigrationAction(
            action_id=f"logical:{suffix}:{diff.field}",
            migration_id=migration_id,
            action="MANUAL_REVIEW",
            status="MANUAL_REQUIRED",
            reason="Logical field differs and no verified conversion rule has been declared.",
            metadata={
                "logical_type":comparison.logical_type,
                "identity":list(comparison.identity),
                "field":diff.field,
                "difference_status":diff.status,
                "source_value":diff.source_value,
                "target_value":diff.target_value,
            },
        ))
    return actions


def plan_record_match(match: RecordMatch, migration_id: str) -> list[MigrationAction]:
    actions=[]
    for field,source_value,target_value in match.identity_changes:
        actions.append(MigrationAction(
            action_id=f"match:{_stable_suffix(LogicalComparison(match.logical_type,match.source.identity,'DIFFERENT',()))}:{field}",
            migration_id=migration_id,
            action="RENUMBER",
            status="AUTO_MIGRATABLE",
            reason="Logical records match semantically but use different physical identifiers.",
            metadata={
                "logical_type":match.logical_type,
                "match_basis":match.match_basis,
                "field":field,
                "source_value":source_value,
                "target_value":target_value,
                "source_identity":list(match.source.identity),
                "target_identity":list(match.target.identity),
            },
        ))
    return actions
