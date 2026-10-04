"""Read-only Auction House validation pipeline for legacy DSP/Topaz lineages."""
from __future__ import annotations

from typing import Any

from .database_reread import RereadEvidence, prepare_from_database_reread
from .invariants import InvariantReport, LegacyAuctionPolicy, validate_legacy_invariants
from .transactional_adapter import PreparedTransaction


def prepare_validate_from_database_reread(
    *,
    service,
    family: str,
    operation: str,
    environment: dict[str, Any],
    preview: dict[str, Any],
    policy: LegacyAuctionPolicy,
    preview_environment: dict[str, Any] | None = None,
) -> tuple[PreparedTransaction, RereadEvidence, InvariantReport]:
    """Collect fresh read-only state and evaluate both freshness and semantic invariants.

    This pipeline cannot mutate or commit. ``PreparedTransaction`` covers lineage/environment,
    stale-preview, claim-cardinality, and cheapest-row checks. ``InvariantReport`` covers fee,
    quantity/stack, listing-limit, funds, and seller-settlement readiness.
    """
    prepared, evidence = prepare_from_database_reread(
        service=service,
        family=family,
        operation=operation,
        environment=environment,
        preview=preview,
        preview_environment=preview_environment,
    )
    invariants = validate_legacy_invariants(
        operation=operation,
        preview=preview,
        evidence=evidence,
        policy=policy,
    )
    return prepared, evidence, invariants
