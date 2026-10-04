"""Read-only DSP/Topaz Auction House invariant validation.

Consumes database reread evidence and evaluates the source-verified legacy preconditions that a
future executor would need to satisfy. This module performs no SQL and cannot authorize writes.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class LegacyAuctionPolicy:
    """Runtime Auction House policy values from the active server configuration.

    Defaults mirror the historical Topaz retail-like map configuration. A future executable
    adapter must load the active server's actual values rather than assuming these defaults.
    """

    base_fee_single: int = 1
    base_fee_stacks: int = 4
    tax_rate_single: float = 1.0
    tax_rate_stacks: float = 0.5
    max_fee: int = 10000
    list_limit: int = 7
    max_delivery_queue_slot: int | None = None


@dataclass(frozen=True)
class InvariantIssue:
    code: str
    message: str
    blocking: bool = True


@dataclass
class InvariantReport:
    operation: str
    listing_fee: int | None = None
    required_quantity: int | None = None
    seller_gil: int | None = None
    buyer_gil: int | None = None
    active_listing_count: int | None = None
    next_delivery_slot: int | None = None
    settlement_ready: bool = False
    issues: list[InvariantIssue] = field(default_factory=list)
    executor_enabled: bool = False

    @property
    def invariants_ready(self) -> bool:
        return not any(issue.blocking for issue in self.issues)

    @property
    def executable(self) -> bool:
        return False

    def as_dict(self) -> dict[str, Any]:
        return {
            "operation": self.operation,
            "listing_fee": self.listing_fee,
            "required_quantity": self.required_quantity,
            "seller_gil": self.seller_gil,
            "buyer_gil": self.buyer_gil,
            "active_listing_count": self.active_listing_count,
            "next_delivery_slot": self.next_delivery_slot,
            "settlement_ready": self.settlement_ready,
            "issues": [asdict(issue) for issue in self.issues],
            "invariants_ready": self.invariants_ready,
            "executor_enabled": False,
            "executable": False,
        }


def legacy_listing_fee(price: int, *, stack: bool, policy: LegacyAuctionPolicy) -> int:
    """Mirror the legacy packet-handler fee calculation and clamp behavior."""
    price = max(0, int(price))
    if stack:
        raw = int(policy.base_fee_stacks + (price * policy.tax_rate_stacks / 100.0))
    else:
        raw = int(policy.base_fee_single + (price * policy.tax_rate_single / 100.0))
    return max(0, min(raw, max(0, int(policy.max_fee))))


def _quantity(row: dict[str, Any]) -> int:
    for key in ("quantity", "qty"):
        if key in row:
            try:
                return int(row.get(key) or 0)
            except (TypeError, ValueError):
                return 0
    return 0


def _delivery_slot(row: dict[str, Any]) -> int | None:
    try:
        return None if row.get("slot") is None else int(row.get("slot"))
    except (TypeError, ValueError):
        return None


def _delivery_box(row: dict[str, Any]) -> int | None:
    try:
        return None if row.get("box") is None else int(row.get("box"))
    except (TypeError, ValueError):
        return None


def _settlement_state(delivery_rows: list[dict[str, Any]] | tuple[dict[str, Any], ...], policy: LegacyAuctionPolicy) -> tuple[bool, int, list[InvariantIssue]]:
    issues: list[InvariantIssue] = []
    incoming_slots = [slot for row in delivery_rows if _delivery_box(row) == 1 for slot in [_delivery_slot(row)] if slot is not None]
    if len(incoming_slots) != len(set(incoming_slots)):
        issues.append(InvariantIssue("delivery_slot_collision", "Seller delivery-box queue contains duplicate incoming slots."))
    if any(slot < 0 for slot in incoming_slots):
        issues.append(InvariantIssue("delivery_slot_invalid", "Seller delivery-box queue contains an invalid negative slot."))

    max_slot = max(incoming_slots) if incoming_slots else None
    next_slot = 8 if max_slot is None or max_slot < 8 else max_slot + 1
    if policy.max_delivery_queue_slot is not None and next_slot > int(policy.max_delivery_queue_slot):
        issues.append(InvariantIssue(
            "delivery_queue_safety_limit",
            f"Next seller delivery slot {next_slot} exceeds configured admin safety ceiling {policy.max_delivery_queue_slot}.",
        ))
    return not any(issue.blocking for issue in issues), next_slot, issues


def validate_legacy_invariants(
    *,
    operation: str,
    preview: dict[str, Any],
    evidence: Any,
    policy: LegacyAuctionPolicy,
) -> InvariantReport:
    """Validate listing/purchase invariants over a fresh read-only reread snapshot."""
    op = str(operation or "").strip().lower()
    payload = dict(preview.get("payload") or {})
    snapshot = dict(getattr(evidence, "snapshot", None) or {})
    issues: list[InvariantIssue] = []
    report = InvariantReport(
        operation=op,
        seller_gil=getattr(evidence, "seller_gil", None),
        buyer_gil=getattr(evidence, "buyer_gil", None),
        active_listing_count=getattr(evidence, "seller_active_listing_count", None),
        issues=issues,
        executor_enabled=False,
    )

    if getattr(evidence, "transaction_mode", None) != "read_only_rolled_back":
        issues.append(InvariantIssue("reread_not_read_only", "Invariant validation requires read-only, rolled-back database evidence."))

    if op == "list_item":
        item = snapshot.get("item") or {}
        stack = bool(payload.get("stack"))
        stack_size = max(1, int(item.get("stack_size") or 1))
        required = stack_size if stack else 1
        report.required_quantity = required
        if not item:
            issues.append(InvariantIssue("item_missing", "Listing item is missing from the fresh reread."))
        if int(item.get("category_id") or 0) <= 0:
            issues.append(InvariantIssue("item_not_auctionable", "Item is not assigned to an Auction House category."))
        if stack and stack_size <= 1:
            issues.append(InvariantIssue("item_not_stackable", "A stack listing requires an item with stack size greater than one."))

        quantities = [_quantity(row) for row in (getattr(evidence, "inventory_rows", ()) or ())]
        if stack:
            if required not in quantities:
                issues.append(InvariantIssue("full_stack_unavailable", f"No inventory row contains the required full stack of {required}."))
        elif not any(quantity >= 1 for quantity in quantities):
            issues.append(InvariantIssue("single_item_unavailable", "Seller does not have the listed item in the reread inventory rows."))

        fee = legacy_listing_fee(int(payload.get("price") or 0), stack=stack, policy=policy)
        report.listing_fee = fee
        if report.seller_gil is None:
            issues.append(InvariantIssue("seller_gil_unknown", "Seller gil could not be read from the active server schema."))
        elif int(report.seller_gil) < fee:
            issues.append(InvariantIssue("seller_gil_insufficient", f"Seller has {report.seller_gil} gil but the listing fee is {fee}."))

        if report.active_listing_count is None:
            issues.append(InvariantIssue("listing_count_unknown", "Seller active-listing count could not be read."))
        elif int(policy.list_limit) > 0 and int(report.active_listing_count) >= int(policy.list_limit):
            issues.append(InvariantIssue(
                "listing_limit_reached",
                f"Seller already has {report.active_listing_count} active listings; configured limit is {policy.list_limit}.",
            ))
        return report

    if op in {"purchase_item", "admin_cleanup"}:
        listing = snapshot.get("listing") or {}
        if not listing:
            issues.append(InvariantIssue("listing_missing", "The previewed active listing is missing from the fresh reread."))
            return report
        asking_price = int(listing.get("asking_price") or 0)
        if op == "purchase_item" and payload.get("mode") == "normal_purchase":
            if report.buyer_gil is None:
                issues.append(InvariantIssue("buyer_gil_unknown", "Buyer gil could not be read from the active server schema."))
            elif int(report.buyer_gil) < asking_price:
                issues.append(InvariantIssue("buyer_gil_insufficient", f"Buyer has {report.buyer_gil} gil but the purchase requires {asking_price}."))

        ready, next_slot, delivery_issues = _settlement_state(getattr(evidence, "delivery_rows", ()) or (), policy)
        report.next_delivery_slot = next_slot
        report.settlement_ready = ready
        issues.extend(delivery_issues)
        return report

    issues.append(InvariantIssue("operation_unsupported", f"Unsupported invariant operation: {op or 'unknown'}"))
    return report
