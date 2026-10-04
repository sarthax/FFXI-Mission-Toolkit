"""Non-executable transactional adapter foundation for Auction House writes.

This module is deliberately incapable of mutating a database. It validates the state and
transaction invariants that a future lineage-specific adapter must satisfy, and provides an
in-memory rollback harness for regression fixtures.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass, field
from typing import Any

from .execution_contracts import evaluate_execution_contract
from .write_plans import snapshot_fingerprint


_SUPPORTED_FAMILIES = {"dsp", "topaz"}


@dataclass(frozen=True)
class AdapterIssue:
    code: str
    message: str
    blocking: bool = True


@dataclass
class PreparedTransaction:
    family: str
    operation: str
    environment: dict[str, Any]
    preview_fingerprint: str
    current_fingerprint: str
    issues: list[AdapterIssue] = field(default_factory=list)
    executor_enabled: bool = False

    @property
    def validation_ready(self) -> bool:
        return not any(issue.blocking for issue in self.issues)

    @property
    def executable(self) -> bool:
        return False

    def as_dict(self) -> dict[str, Any]:
        return {
            "family": self.family,
            "operation": self.operation,
            "environment": dict(self.environment),
            "preview_fingerprint": self.preview_fingerprint,
            "current_fingerprint": self.current_fingerprint,
            "issues": [asdict(issue) for issue in self.issues],
            "validation_ready": self.validation_ready,
            "executor_enabled": False,
            "executable": False,
        }


def _fingerprint(payload: dict[str, Any], snapshot: dict[str, Any]) -> str:
    return snapshot_fingerprint({"payload": payload, "snapshot": snapshot})


def _environment_key(environment: dict[str, Any]) -> tuple[Any, ...]:
    return (
        environment.get("profile_id"),
        str(environment.get("name") or ""),
        str(environment.get("environment") or ""),
        str(environment.get("family") or ""),
    )


def prepare_legacy_transaction(
    *,
    family: str,
    schema_family_hint: str,
    operation: str,
    environment: dict[str, Any],
    preview: dict[str, Any],
    current: dict[str, Any],
    preview_environment: dict[str, Any] | None = None,
) -> PreparedTransaction:
    """Validate a future DSP/Topaz transaction without performing a write.

    ``current`` must be produced from a fresh in-transaction reread by the future database-backed
    adapter. The foundation merely compares normalized state and reports blocking conditions.
    """
    normalized_family = str(family or "").strip().lower()
    normalized_operation = str(operation or "").strip().lower()
    issues: list[AdapterIssue] = []

    contract = evaluate_execution_contract(
        profile_family=normalized_family,
        schema_family_hint=schema_family_hint,
    )
    for issue in contract.get("issues") or []:
        if issue.get("code") == "execution_adapter_not_implemented":
            # This module *is* the non-executable adapter foundation; the database-backed adapter
            # is still absent, so keep execution disabled without making fixture validation useless.
            continue
        issues.append(AdapterIssue(str(issue.get("code")), str(issue.get("message")), bool(issue.get("blocking", True))))

    if normalized_family not in _SUPPORTED_FAMILIES:
        issues.append(AdapterIssue("adapter_family_unsupported", "Only DSP and Topaz use this legacy adapter foundation."))
    if normalized_operation not in {"list_item", "purchase_item", "admin_cleanup"}:
        issues.append(AdapterIssue("operation_unsupported", f"Unsupported adapter operation: {normalized_operation or 'unknown'}"))
    if not environment or not environment.get("is_active"):
        issues.append(AdapterIssue("environment_not_active", "An active named server environment is required."))
    if str(environment.get("family") or "").strip().lower() != normalized_family:
        issues.append(AdapterIssue("environment_lineage_mismatch", "The active environment lineage does not match the adapter lineage."))
    if preview_environment is not None and _environment_key(preview_environment) != _environment_key(environment):
        issues.append(AdapterIssue("preview_environment_mismatch", "The preview was generated for a different server environment."))

    payload = dict(preview.get("payload") or {})
    preview_snapshot = dict(preview.get("snapshot") or {})
    current_snapshot = dict(current.get("snapshot") or {})
    preview_fp = _fingerprint(payload, preview_snapshot)
    current_fp = _fingerprint(payload, current_snapshot)
    supplied_fp = str(preview.get("snapshot_fingerprint") or "")
    if supplied_fp and supplied_fp != preview_fp:
        issues.append(AdapterIssue("preview_fingerprint_invalid", "The supplied preview fingerprint does not match the preview payload and snapshot."))
    if preview_fp != current_fp:
        issues.append(AdapterIssue("stale_preview", "Mutation-relevant state changed after preview; the transaction must be rejected."))

    if normalized_operation in {"purchase_item", "admin_cleanup"}:
        listing = current_snapshot.get("listing") or {}
        if not listing:
            issues.append(AdapterIssue("listing_missing", "The previewed auction is no longer active."))
        elif listing.get("sold_at") not in (None, 0, "", False):
            issues.append(AdapterIssue("listing_already_sold", "The previewed auction has already been sold."))
        if current.get("claim_count") not in (None, 1):
            issues.append(AdapterIssue("claim_cardinality_invalid", "A purchase must atomically claim exactly one active auction row."))
        if normalized_operation == "purchase_item" and current.get("cheapest_qualifying_auction_id") not in (None, payload.get("auction_id")):
            issues.append(AdapterIssue("cheapest_listing_changed", "The previewed auction is no longer the cheapest qualifying active listing."))

    return PreparedTransaction(
        family=normalized_family,
        operation=normalized_operation,
        environment=dict(environment),
        preview_fingerprint=preview_fp,
        current_fingerprint=current_fp,
        issues=issues,
        executor_enabled=False,
    )


@dataclass
class RollbackSimulation:
    before: dict[str, Any]
    working: dict[str, Any]
    after: dict[str, Any]
    rolled_back: bool
    failure_stage: str | None


def simulate_transaction_rollback(
    state: dict[str, Any],
    *,
    staged_changes: dict[str, Any],
    fail_after_stage: str | None = None,
) -> RollbackSimulation:
    """Exercise all-or-nothing fixture behavior without touching a database.

    The caller provides nested replacement values representing hypothetical transaction stages.
    Any requested failure restores the exact original fixture state.
    """
    before = deepcopy(state)
    working = deepcopy(state)
    failure_stage: str | None = None
    for stage, replacement in staged_changes.items():
        working[stage] = deepcopy(replacement)
        if fail_after_stage == stage:
            failure_stage = stage
            working = deepcopy(before)
            break
    rolled_back = failure_stage is not None
    after = deepcopy(working)
    return RollbackSimulation(
        before=before,
        working=working,
        after=after,
        rolled_back=rolled_back,
        failure_stage=failure_stage,
    )
