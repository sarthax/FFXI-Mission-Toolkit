"""LandSandBoat-specific read-only Auction House preview validation.

LSB does not use the legacy DSP/Topaz external Auction House fee policy contract. This module
therefore validates live LSB lineage/schema/trigger state and preview freshness without importing
legacy config-policy assumptions. It starts a READ ONLY transaction and always rolls it back.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from .write_plans import snapshot_fingerprint


@dataclass(frozen=True)
class LSBValidationIssue:
    code: str
    message: str
    blocking: bool = True


@dataclass
class LSBPreparedValidation:
    operation: str
    preview_fingerprint: str
    current_fingerprint: str
    issues: list[LSBValidationIssue] = field(default_factory=list)

    @property
    def validation_ready(self) -> bool:
        return not any(issue.blocking for issue in self.issues)

    def as_dict(self) -> dict[str, Any]:
        return {
            "operation": self.operation,
            "preview_fingerprint": self.preview_fingerprint,
            "current_fingerprint": self.current_fingerprint,
            "issues": [asdict(issue) for issue in self.issues],
            "validation_ready": self.validation_ready,
            "executor_enabled": False,
            "executable": False,
        }


@dataclass(frozen=True)
class LSBRereadEvidence:
    operation: str
    snapshot: dict[str, Any]
    transaction_mode: str = "read_only_rolled_back"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class LSBNotApplicableGate:
    gate: str
    issues: tuple[dict[str, Any], ...]

    @property
    def policy_ready(self) -> bool:
        return True

    @property
    def binding_ready(self) -> bool:
        return True

    def as_dict(self) -> dict[str, Any]:
        return {
            "gate": self.gate,
            "applicable": False,
            "issues": [dict(item) for item in self.issues],
            "executor_enabled": False,
            "executable": False,
        }


@dataclass(frozen=True)
class LSBInvariantResult:
    issues: tuple[LSBValidationIssue, ...]

    @property
    def invariants_ready(self) -> bool:
        return not any(issue.blocking for issue in self.issues)

    def as_dict(self) -> dict[str, Any]:
        return {
            "invariants_ready": self.invariants_ready,
            "issues": [asdict(issue) for issue in self.issues],
            "executor_enabled": False,
            "executable": False,
        }


def _environment_key(environment: dict[str, Any]) -> tuple[Any, ...]:
    return (
        environment.get("profile_id"),
        str(environment.get("name") or ""),
        str(environment.get("environment") or ""),
        str(environment.get("family") or ""),
    )


def _fingerprint(payload: dict[str, Any], snapshot: dict[str, Any]) -> str:
    return snapshot_fingerprint({"payload": payload, "snapshot": snapshot})


def _collect_snapshot(service, operation: str, preview: dict[str, Any]) -> LSBRereadEvidence:
    connection = service.connection
    cursor = connection.cursor()
    try:
        cursor.execute("START TRANSACTION READ ONLY")
    finally:
        cursor.close()

    try:
        payload = dict(preview.get("payload") or {})
        if operation == "list_item":
            snapshot = {
                "item": service.item_snapshot(int(payload.get("item_id") or 0)),
                "seller": service.character_snapshot(int(payload.get("seller_id") or 0)),
            }
        elif operation in {"purchase_item", "admin_cleanup"}:
            buyer_id = int(payload.get("buyer_id") or 0) or None
            snapshot = {
                "listing": service.active_listing_by_id(int(payload.get("auction_id") or 0)),
                "buyer": None if buyer_id is None else service.character_snapshot(buyer_id),
            }
        else:
            raise ValueError(f"Unsupported LSB validation operation: {operation or 'unknown'}")
        return LSBRereadEvidence(operation=operation, snapshot=snapshot)
    finally:
        connection.rollback()


def prepare_lsb_preview_validation(
    *,
    service,
    operation: str,
    environment: dict[str, Any],
    preview: dict[str, Any],
) -> tuple[LSBPreparedValidation, LSBRereadEvidence, LSBInvariantResult, LSBNotApplicableGate, LSBNotApplicableGate]:
    """Re-read one LSB preview and evaluate fail-closed freshness/basic semantic invariants."""
    op = str(operation or "").strip().lower()
    evidence = _collect_snapshot(service, op, preview)
    payload = dict(preview.get("payload") or {})
    preview_snapshot = dict(preview.get("snapshot") or {})
    preview_fp = _fingerprint(payload, preview_snapshot)
    current_fp = _fingerprint(payload, evidence.snapshot)
    issues: list[LSBValidationIssue] = []

    if str(environment.get("family") or "").strip().lower() != "lsb" or not environment.get("is_active"):
        issues.append(LSBValidationIssue("lsb_environment_invalid", "LSB validation requires the active environment to explicitly identify LandSandBoat."))
    preview_environment = preview.get("environment") if isinstance(preview.get("environment"), dict) else None
    if preview_environment is None:
        issues.append(LSBValidationIssue("preview_environment_missing", "The preview is not bound to a server environment."))
    elif _environment_key(preview_environment) != _environment_key(environment):
        issues.append(LSBValidationIssue("preview_environment_mismatch", "The preview was generated for a different server environment."))

    supplied_fp = str(preview.get("snapshot_fingerprint") or "")
    if supplied_fp and supplied_fp != preview_fp:
        issues.append(LSBValidationIssue("preview_fingerprint_invalid", "The supplied preview fingerprint does not match the preview payload and snapshot."))
    if preview_fp != current_fp:
        issues.append(LSBValidationIssue("stale_preview", "Mutation-relevant LSB state changed after preview; generate a fresh preview."))

    invariant_issues: list[LSBValidationIssue] = []
    if op == "list_item":
        if not evidence.snapshot.get("item"):
            invariant_issues.append(LSBValidationIssue("item_missing", "The previewed item is no longer available in the live item catalog."))
        if not evidence.snapshot.get("seller"):
            invariant_issues.append(LSBValidationIssue("seller_missing", "The previewed seller character no longer exists."))
    elif op in {"purchase_item", "admin_cleanup"}:
        listing = evidence.snapshot.get("listing") or {}
        if not listing:
            invariant_issues.append(LSBValidationIssue("listing_missing", "The previewed auction is no longer active."))
        elif listing.get("sold_at") not in (None, 0, "", False):
            invariant_issues.append(LSBValidationIssue("listing_already_sold", "The previewed auction has already been sold."))
        if str(payload.get("mode") or "").strip().lower() == "normal_purchase" and not evidence.snapshot.get("buyer"):
            invariant_issues.append(LSBValidationIssue("buyer_missing", "A normal LSB purchase requires a live buyer character."))

    prepared = LSBPreparedValidation(
        operation=op,
        preview_fingerprint=preview_fp,
        current_fingerprint=current_fp,
        issues=issues,
    )
    invariants = LSBInvariantResult(tuple(invariant_issues))
    not_applicable = ({
        "code": "lsb_legacy_policy_not_applicable",
        "message": "DSP/Topaz external AH fee-policy configuration is not part of the LSB validation contract.",
        "blocking": False,
    },)
    policy = LSBNotApplicableGate("policy", not_applicable)
    binding = LSBNotApplicableGate("policy_binding", not_applicable)
    return prepared, evidence, invariants, policy, binding
