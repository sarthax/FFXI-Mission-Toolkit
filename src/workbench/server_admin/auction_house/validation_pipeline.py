"""Read-only Auction House validation pipeline for legacy DSP/Topaz lineages."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .config_policy import ConfigPolicyLoad, load_active_legacy_policy
from .database_reread import RereadEvidence, prepare_from_database_reread
from .invariants import InvariantReport, LegacyAuctionPolicy, validate_legacy_invariants
from .policy_binding import PolicyBindingCheck, validate_preview_policy_binding
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


def prepare_validate_from_active_config(
    *,
    service,
    family: str,
    operation: str,
    environment: dict[str, Any],
    preview: dict[str, Any],
    server_root: Path | str,
    preview_environment: dict[str, Any] | None = None,
) -> tuple[PreparedTransaction, RereadEvidence, InvariantReport | None, ConfigPolicyLoad, PolicyBindingCheck]:
    """Run validation using the exact active AH config and reject stale policy bindings.

    Missing/invalid active configuration or any change in the policy fingerprint/source/family is
    fail-closed. Database reread/freshness evidence is still returned for diagnostics, but semantic
    invariant validation is not allowed to proceed under a different policy than the preview used.
    """
    policy_load = load_active_legacy_policy(server_root=server_root, family=family)
    binding = validate_preview_policy_binding(preview, policy_load)
    prepared, evidence = prepare_from_database_reread(
        service=service,
        family=family,
        operation=operation,
        environment=environment,
        preview=preview,
        preview_environment=preview_environment,
    )
    if not policy_load.policy_ready or policy_load.policy is None or not binding.binding_ready:
        return prepared, evidence, None, policy_load, binding
    invariants = validate_legacy_invariants(
        operation=operation,
        preview=preview,
        evidence=evidence,
        policy=policy_load.policy,
    )
    return prepared, evidence, invariants, policy_load, binding
