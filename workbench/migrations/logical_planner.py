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
from workbench.migrations.entity_identity import EntityIdentityDrift


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


def plan_entity_identity_drifts(
    drifts: list[EntityIdentityDrift] | tuple[EntityIdentityDrift, ...],
    migration_id: str,
) -> list[MigrationAction]:
    actions=[]
    for drift in drifts:
        actions.append(MigrationAction(
            action_id=f"entity-renumber:{drift.symbol}:{drift.source_id}:{drift.target_id}",
            migration_id=migration_id,
            action="RENUMBER",
            status="AUTO_MIGRATABLE",
            reason="The same symbolic entity identity resolves to different numeric IDs across source and target snapshots.",
            metadata={
                "logical_type":"entity",
                "symbol":drift.symbol,
                "source_value":drift.source_id,
                "target_value":drift.target_id,
                "classification":drift.classification,
                "match_basis":"SYMBOL_IDENTITY",
            },
        ))
    return actions


def plan_collision_findings(
    collision_result: dict,
    migration_id: str,
) -> list[MigrationAction]:
    """Convert generic ID/content collision findings into conservative migration actions.

    Hard same-identity/different-content collisions are BLOCKED. Content-equivalent renumber
    candidates remain MANUAL_REQUIRED because normalized field equality is not proof of semantic
    entity equivalence. Exact equivalents need no action.
    """
    actions=[]
    for index,finding in enumerate(collision_result.get("findings",[]), start=1):
        classification=finding.get("classification")
        logical_type=finding.get("logical_type")
        source_identity=finding.get("source_identity")
        target_identity=finding.get("target_identity")
        digest=hashlib.sha256(json.dumps(
            {"classification":classification,"logical_type":logical_type,
             "source_identity":source_identity,"target_identity":target_identity},
            sort_keys=True,default=str,
        ).encode("utf-8")).hexdigest()[:12]
        metadata={
            "logical_type":logical_type,
            "classification":classification,
            "source_identity":source_identity,
            "target_identity":target_identity,
            "identifier_namespaces":finding.get("identifier_namespaces",[]),
            "collision_confidence":finding.get("confidence"),
            "collision_status":finding.get("status"),
            "source_fingerprint":finding.get("source_fingerprint"),
            "target_fingerprint":finding.get("target_fingerprint"),
            "source_snapshot_id":collision_result.get("source_snapshot_id"),
            "target_snapshot_id":collision_result.get("target_snapshot_id"),
        }

        if classification=="EXACT_IDENTITY_EQUIVALENT":
            action="NOT_REQUIRED"; status="COMPATIBLE"
            reason="Logical identity and normalized content are already compatible."
        elif classification=="ID_CONTENT_COLLISION":
            action="MANUAL_REVIEW"; status="BLOCKED"
            reason="Target logical identity is occupied by different normalized content; automatic migration is unsafe."
        elif classification=="CONTENT_RENUMBER_CANDIDATE":
            action="RENUMBER"; status="MANUAL_REQUIRED"
            reason="Equivalent normalized content appears under a different identity, but semantic equivalence is not verified."
        elif classification in {"SOURCE_IDENTITY_AMBIGUOUS","TARGET_IDENTITY_AMBIGUOUS"}:
            action="MANUAL_REVIEW"; status="BLOCKED"
            reason="Duplicate logical identity makes deterministic migration unsafe."
        elif classification in {"SOURCE_IDENTITY_UNRESOLVED","TARGET_IDENTITY_UNRESOLVED"}:
            action="MANUAL_REVIEW"; status="MANUAL_REQUIRED"
            reason="Logical identity is incomplete and requires review before migration."
        else:
            action="MANUAL_REVIEW"; status="MANUAL_REQUIRED"
            reason="No deterministic collision-safe migration rule has been established."

        actions.append(MigrationAction(
            action_id=f"collision:{digest}:{index}",
            migration_id=migration_id,
            action=action,
            status=status,
            reason=reason,
            metadata=metadata,
        ))
    return actions
