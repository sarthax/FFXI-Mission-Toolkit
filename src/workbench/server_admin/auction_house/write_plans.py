"""Guarded Auction House write-plan contracts.

This module defines what a future Auction House mutation would need to prove before execution.
It deliberately contains no SQL executor and performs no database mutation.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
import hashlib
import json
from typing import Any, Iterable


_VERIFIED_FAMILIES = {"lsb-compatible", "legacy-dsp-topaz-compatible"}
_LSB_REQUIRED_TRIGGERS = {
    "list_item": ("auction_house_list",),
    "purchase_item": ("auction_house_buy", "delivery_box_insert"),
}


@dataclass(frozen=True)
class WriteIssue:
    code: str
    message: str
    blocking: bool = True


@dataclass(frozen=True)
class AuditIntent:
    operation: str
    target: dict[str, Any]
    before: dict[str, Any]
    expected_after: dict[str, Any]
    metadata: dict[str, Any]


@dataclass
class WritePlan:
    operation: str
    adapter_family: str
    environment: dict[str, Any]
    snapshot: dict[str, Any]
    snapshot_fingerprint: str
    required_tables: tuple[str, ...]
    required_triggers: tuple[str, ...]
    mutation_steps: tuple[str, ...]
    audit: AuditIntent
    issues: list[WriteIssue] = field(default_factory=list)
    executor_enabled: bool = False

    @property
    def contract_ready(self) -> bool:
        return not any(issue.blocking for issue in self.issues)

    @property
    def executable(self) -> bool:
        return self.contract_ready and self.executor_enabled

    def as_dict(self) -> dict[str, Any]:
        return {
            "operation": self.operation,
            "adapter_family": self.adapter_family,
            "environment": dict(self.environment),
            "snapshot": self.snapshot,
            "snapshot_fingerprint": self.snapshot_fingerprint,
            "required_tables": list(self.required_tables),
            "required_triggers": list(self.required_triggers),
            "mutation_steps": list(self.mutation_steps),
            "audit": asdict(self.audit),
            "issues": [asdict(issue) for issue in self.issues],
            "contract_ready": self.contract_ready,
            "executor_enabled": self.executor_enabled,
            "executable": self.executable,
        }


def snapshot_fingerprint(payload: dict[str, Any]) -> str:
    """Return a deterministic fingerprint for a preview/write snapshot."""
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _environment_issues(identity: dict[str, Any], *, live_confirmation: str | None) -> list[WriteIssue]:
    issues: list[WriteIssue] = []
    if not identity or not identity.get("is_active"):
        issues.append(WriteIssue("environment_not_active", "An active server environment is required."))
        return issues
    if not identity.get("enabled", True):
        issues.append(WriteIssue("environment_disabled", "The selected server environment is disabled."))
    env = str(identity.get("environment") or "").strip().lower()
    if env == "live":
        expected = str(identity.get("name") or "LIVE").strip()
        if str(live_confirmation or "").strip() != expected:
            issues.append(WriteIssue(
                "live_confirmation_required",
                f"LIVE mutations require typing the active profile name exactly: {expected}",
            ))
    elif env == "legacy":
        issues.append(WriteIssue(
            "legacy_environment_unclassified",
            "Legacy fallback environments are read/preview-only until migrated to a named environment.",
        ))
    return issues


def _family_issues(adapter_family: str) -> list[WriteIssue]:
    family = str(adapter_family or "unknown")
    if family not in _VERIFIED_FAMILIES:
        return [WriteIssue("adapter_unverified", f"Unsupported Auction House adapter family: {family}")]
    return []


def _missing_required(found: Iterable[str], required: Iterable[str], *, kind: str) -> list[WriteIssue]:
    present = {str(value) for value in found}
    issues: list[WriteIssue] = []
    for value in required:
        if value not in present:
            issues.append(WriteIssue(f"missing_{kind}", f"Required {kind} is not present: {value}"))
    return issues


def build_list_write_plan(
    *,
    adapter_family: str,
    environment: dict[str, Any],
    preview: dict[str, Any],
    schema_tables: Iterable[str],
    schema_triggers: Iterable[str],
    live_confirmation: str | None = None,
) -> WritePlan:
    """Build a non-executable write contract for a future single listing."""
    snapshot = dict(preview.get("snapshot") or {})
    payload = dict(preview.get("payload") or {})
    issues = _family_issues(adapter_family) + _environment_issues(environment, live_confirmation=live_confirmation)
    if not snapshot.get("item"):
        issues.append(WriteIssue("item_snapshot_missing", "Listing preview does not contain an item snapshot."))
    if not snapshot.get("seller"):
        issues.append(WriteIssue("seller_snapshot_missing", "Listing preview does not contain a seller snapshot."))
    if not payload.get("item_id") or not payload.get("seller_id") or not payload.get("price"):
        issues.append(WriteIssue("payload_incomplete", "Listing preview payload is incomplete."))

    required_tables = ("auction_house", "item_basic", "chars")
    issues.extend(_missing_required(schema_tables, required_tables, kind="table"))
    required_triggers: tuple[str, ...] = ()
    if adapter_family == "lsb-compatible":
        required_triggers = _LSB_REQUIRED_TRIGGERS["list_item"]
        issues.extend(_missing_required(schema_triggers, required_triggers, kind="trigger"))

    # We intentionally describe semantic steps instead of storing executable SQL. Player-backed
    # listing inventory semantics still need lineage-specific proof before an executor may exist.
    mutation_steps = (
        "re-read item and seller snapshots inside one DB transaction",
        "verify snapshot fingerprint and auctionability are unchanged",
        "verify lineage-specific listing source/inventory semantics",
        "create auction_house listing using the verified adapter contract",
        "commit transaction",
        "append Auction House audit record after commit",
    )
    audit = AuditIntent(
        operation="auction_house.list_item",
        target={"item_id": payload.get("item_id"), "seller_id": payload.get("seller_id")},
        before={"snapshot": snapshot},
        expected_after={"active_listing": payload},
        metadata={"environment": environment, "adapter_family": adapter_family},
    )
    issues.append(WriteIssue(
        "executor_not_enabled",
        "Auction House write execution is intentionally disabled; this plan is validation-only.",
    ))
    return WritePlan(
        operation="list_item",
        adapter_family=adapter_family,
        environment=dict(environment),
        snapshot=snapshot,
        snapshot_fingerprint=snapshot_fingerprint({"payload": payload, "snapshot": snapshot}),
        required_tables=required_tables,
        required_triggers=required_triggers,
        mutation_steps=mutation_steps,
        audit=audit,
        issues=issues,
        executor_enabled=False,
    )


def build_purchase_write_plan(
    *,
    adapter_family: str,
    environment: dict[str, Any],
    preview: dict[str, Any],
    schema_tables: Iterable[str],
    schema_triggers: Iterable[str],
    live_confirmation: str | None = None,
) -> WritePlan:
    """Build a non-executable write contract for a future purchase/admin cleanup."""
    snapshot = dict(preview.get("snapshot") or {})
    payload = dict(preview.get("payload") or {})
    listing = snapshot.get("listing")
    issues = _family_issues(adapter_family) + _environment_issues(environment, live_confirmation=live_confirmation)
    if not listing:
        issues.append(WriteIssue("listing_snapshot_missing", "Purchase preview does not contain an active listing snapshot."))
    if not payload.get("auction_id"):
        issues.append(WriteIssue("payload_incomplete", "Purchase preview payload is incomplete."))
    if payload.get("mode") == "normal_purchase" and not snapshot.get("buyer"):
        issues.append(WriteIssue("buyer_snapshot_missing", "Normal purchase requires an exact buyer snapshot."))

    required_tables = ("auction_house", "chars", "delivery_box")
    issues.extend(_missing_required(schema_tables, required_tables, kind="table"))
    required_triggers: tuple[str, ...] = ()
    if adapter_family == "lsb-compatible":
        required_triggers = _LSB_REQUIRED_TRIGGERS["purchase_item"]
        issues.extend(_missing_required(schema_triggers, required_triggers, kind="trigger"))

    mutation_steps = (
        "re-read exact active auction inside one DB transaction",
        "reject if auction row differs from the preview fingerprint",
        "verify lineage-specific seller proceeds / delivery-box behavior",
        "verify buyer debit semantics for normal purchase or admin-compensation semantics for cleanup",
        "apply the verified adapter operation without bypassing required triggers",
        "commit transaction",
        "append Auction House audit record after commit",
    )
    audit = AuditIntent(
        operation=f"auction_house.{payload.get('mode') or 'purchase'}",
        target={"auction_id": payload.get("auction_id"), "buyer_id": payload.get("buyer_id")},
        before={"snapshot": snapshot},
        expected_after={"active_listing_removed": bool(listing), "economic_effect": preview.get("economic_effect") or {}},
        metadata={"environment": environment, "adapter_family": adapter_family},
    )
    issues.append(WriteIssue(
        "executor_not_enabled",
        "Auction House write execution is intentionally disabled; this plan is validation-only.",
    ))
    return WritePlan(
        operation="purchase_item",
        adapter_family=adapter_family,
        environment=dict(environment),
        snapshot=snapshot,
        snapshot_fingerprint=snapshot_fingerprint({"payload": payload, "snapshot": snapshot}),
        required_tables=required_tables,
        required_triggers=required_triggers,
        mutation_steps=mutation_steps,
        audit=audit,
        issues=issues,
        executor_enabled=False,
    )
