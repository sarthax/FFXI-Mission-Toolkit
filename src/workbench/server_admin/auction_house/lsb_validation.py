"""LandSandBoat-specific read-only Auction House preview validation.

The validator mirrors source-observable LSB listing/purchase prerequisites while remaining unable
to mutate server state. Every database reread is performed inside READ ONLY and rolled back.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .lsb_policy import LSBPolicy, LSBPolicyBinding, listing_fee, load_lsb_policy, validate_lsb_policy_binding
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
    seller_gil: int | None = None
    buyer_gil: int | None = None
    seller_active_listing_count: int | None = None
    seller_item_quantity: int | None = None
    buyer_inventory_capacity: int | None = None
    buyer_inventory_occupied: int | None = None
    cheapest_qualifying_auction_id: int | None = None
    delivery_row_count: int | None = None
    transaction_mode: str = "read_only_rolled_back"

    @property
    def buyer_inventory_free_slots(self) -> int | None:
        if self.buyer_inventory_capacity is None or self.buyer_inventory_occupied is None:
            return None
        return max(0, self.buyer_inventory_capacity - self.buyer_inventory_occupied)

    def as_dict(self) -> dict[str, Any]:
        out = asdict(self)
        out["buyer_inventory_free_slots"] = self.buyer_inventory_free_slots
        return out


@dataclass(frozen=True)
class LSBInvariantResult:
    issues: tuple[LSBValidationIssue, ...]
    details: dict[str, Any]

    @property
    def invariants_ready(self) -> bool:
        return not any(issue.blocking for issue in self.issues)

    def as_dict(self) -> dict[str, Any]:
        return {
            "invariants_ready": self.invariants_ready,
            "issues": [asdict(issue) for issue in self.issues],
            "details": dict(self.details),
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


def _columns(connection, table: str) -> set[str]:
    cursor = connection.cursor()
    try:
        cursor.execute(f"DESCRIBE `{table}`")
        return {str(row[0]) for row in (cursor.fetchall() or [])}
    finally:
        cursor.close()


def _pick(columns: set[str], *names: str) -> str | None:
    return next((name for name in names if name in columns), None)


def _scalar(connection, sql: str, params: tuple[Any, ...]) -> Any:
    cursor = connection.cursor()
    try:
        cursor.execute(sql, params)
        row = cursor.fetchone()
        return None if not row else row[0]
    finally:
        cursor.close()


def _character_gil(connection, char_id: int | None) -> int | None:
    if not char_id:
        return None
    cols = _columns(connection, "chars")
    id_col = _pick(cols, "charid", "charId", "char_id", "id")
    gil_col = _pick(cols, "gil")
    if not id_col or not gil_col:
        return None
    value = _scalar(connection, f"SELECT `{gil_col}` FROM `chars` WHERE `{id_col}`=%s LIMIT 1", (int(char_id),))
    return None if value is None else int(value)


def _seller_item_quantity(connection, seller_id: int | None, item_id: int | None) -> int | None:
    if not seller_id or not item_id:
        return None
    cols = _columns(connection, "char_inventory")
    char_col = _pick(cols, "charid", "charId", "char_id")
    item_col = _pick(cols, "itemId", "itemid", "item_id")
    qty_col = _pick(cols, "quantity", "qty")
    loc_col = _pick(cols, "location")
    if not char_col or not item_col or not qty_col:
        return None
    where = f"`{char_col}`=%s AND `{item_col}`=%s"
    params: tuple[Any, ...] = (int(seller_id), int(item_id))
    if loc_col:
        where += f" AND `{loc_col}`=0"
    value = _scalar(connection, f"SELECT COALESCE(SUM(`{qty_col}`),0) FROM `char_inventory` WHERE {where}", params)
    return int(value or 0)


def _seller_active_listings(service, seller_id: int | None) -> int | None:
    if not seller_id:
        return None
    a = service.schema.auction_columns
    value = _scalar(service.connection, f"SELECT COUNT(*) FROM `auction_house` WHERE `{a['seller_id']}`=%s AND `{a['sold_at']}`=0", (int(seller_id),))
    return int(value or 0)


def _buyer_inventory_state(connection, buyer_id: int | None) -> tuple[int | None, int | None]:
    if not buyer_id:
        return None, None
    storage_cols = _columns(connection, "char_storage")
    inv_col = _pick(storage_cols, "inventory")
    char_col = _pick(storage_cols, "charid", "charId", "char_id")
    if not inv_col or not char_col:
        return None, None
    capacity = _scalar(connection, f"SELECT `{inv_col}` FROM `char_storage` WHERE `{char_col}`=%s LIMIT 1", (int(buyer_id),))
    inv_cols = _columns(connection, "char_inventory")
    inv_char = _pick(inv_cols, "charid", "charId", "char_id")
    location = _pick(inv_cols, "location")
    slot = _pick(inv_cols, "slot")
    if not inv_char or not location or not slot:
        return None if capacity is None else int(capacity), None
    occupied = _scalar(connection, f"SELECT COUNT(DISTINCT `{slot}`) FROM `char_inventory` WHERE `{inv_char}`=%s AND `{location}`=0", (int(buyer_id),))
    return (None if capacity is None else int(capacity), int(occupied or 0))


def _cheapest_qualifying(service, listing: dict[str, Any] | None) -> int | None:
    if not listing:
        return None
    a = service.schema.auction_columns
    value = _scalar(
        service.connection,
        f"SELECT `{a['id']}` FROM `auction_house` WHERE `{a['item_id']}`=%s AND `{a['stack']}`=%s AND `{a['sold_at']}`=0 AND `{a['asking_price']}`<=%s ORDER BY `{a['asking_price']}` ASC, `{a['id']}` ASC LIMIT 1",
        (int(listing.get("item_id") or 0), 1 if listing.get("stack") else 0, int(listing.get("asking_price") or 0)),
    )
    return None if value is None else int(value)


def _delivery_count(connection, seller_id: int | None) -> int | None:
    if not seller_id:
        return None
    cols = _columns(connection, "delivery_box")
    char_col = _pick(cols, "charid", "charId", "char_id")
    if not char_col:
        return None
    value = _scalar(connection, f"SELECT COUNT(*) FROM `delivery_box` WHERE `{char_col}`=%s", (int(seller_id),))
    return int(value or 0)


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
            seller_id = int(payload.get("seller_id") or 0) or None
            item_id = int(payload.get("item_id") or 0) or None
            item = service.item_snapshot(int(item_id or 0))
            seller = service.character_snapshot(int(seller_id or 0))
            return LSBRereadEvidence(
                operation=operation,
                snapshot={"item": item, "seller": seller},
                seller_gil=_character_gil(connection, seller_id),
                seller_active_listing_count=_seller_active_listings(service, seller_id),
                seller_item_quantity=_seller_item_quantity(connection, seller_id, item_id),
                delivery_row_count=_delivery_count(connection, seller_id),
            )
        if operation in {"purchase_item", "admin_cleanup"}:
            buyer_id = int(payload.get("buyer_id") or 0) or None
            listing = service.active_listing_by_id(int(payload.get("auction_id") or 0))
            buyer = None if buyer_id is None else service.character_snapshot(buyer_id)
            seller_id = int((listing or {}).get("seller_id") or 0) or None
            capacity, occupied = _buyer_inventory_state(connection, buyer_id)
            return LSBRereadEvidence(
                operation=operation,
                snapshot={"listing": listing, "buyer": buyer},
                buyer_gil=_character_gil(connection, buyer_id),
                buyer_inventory_capacity=capacity,
                buyer_inventory_occupied=occupied,
                cheapest_qualifying_auction_id=_cheapest_qualifying(service, listing),
                delivery_row_count=_delivery_count(connection, seller_id),
            )
        raise ValueError(f"Unsupported LSB validation operation: {operation or 'unknown'}")
    finally:
        connection.rollback()


def _evaluate_invariants(*, operation: str, payload: dict[str, Any], evidence: LSBRereadEvidence, policy: LSBPolicy) -> LSBInvariantResult:
    issues: list[LSBValidationIssue] = []
    details: dict[str, Any] = {"policy_fingerprint": policy.policy_fingerprint}
    if operation == "list_item":
        item = evidence.snapshot.get("item") or {}
        seller = evidence.snapshot.get("seller") or {}
        if not item:
            issues.append(LSBValidationIssue("item_missing", "The previewed item is no longer available in the live item catalog."))
        if not seller:
            issues.append(LSBValidationIssue("seller_missing", "The previewed seller character no longer exists."))
        stack_size = max(1, int(item.get("stack_size") or 1))
        required_qty = stack_size if bool(payload.get("stack")) else 1
        details["required_quantity"] = required_qty
        details["seller_item_quantity"] = evidence.seller_item_quantity
        if evidence.seller_item_quantity is None or evidence.seller_item_quantity < required_qty:
            issues.append(LSBValidationIssue("seller_inventory_insufficient", "Seller inventory does not contain the required single item or full stack quantity."))
        fee = listing_fee(policy, price=int(payload.get("price") or 0), stack=bool(payload.get("stack")))
        details["listing_fee"] = fee
        details["seller_gil"] = evidence.seller_gil
        if fee is None:
            issues.append(LSBValidationIssue("lsb_listing_fee_unavailable", "The active LSB AH fee policy could not be resolved."))
        elif evidence.seller_gil is None or evidence.seller_gil < fee:
            issues.append(LSBValidationIssue("seller_gil_insufficient", "Seller does not have enough gil to pay the current LSB Auction House listing fee."))
        limit = int(policy.values.get("AH_LIST_LIMIT", 0)) if policy.policy_ready else None
        details["listing_limit"] = limit
        details["seller_active_listing_count"] = evidence.seller_active_listing_count
        if limit and evidence.seller_active_listing_count is not None and evidence.seller_active_listing_count >= limit:
            issues.append(LSBValidationIssue("listing_limit_reached", "Seller has reached the active LSB Auction House listing limit."))
    else:
        listing = evidence.snapshot.get("listing") or {}
        mode = str(payload.get("mode") or "").strip().lower()
        if not listing:
            issues.append(LSBValidationIssue("listing_missing", "The previewed auction is no longer active."))
        elif listing.get("sold_at") not in (None, 0, "", False):
            issues.append(LSBValidationIssue("listing_already_sold", "The previewed auction has already been sold."))
        if mode == "normal_purchase":
            buyer = evidence.snapshot.get("buyer") or {}
            if not buyer:
                issues.append(LSBValidationIssue("buyer_missing", "A normal LSB purchase requires a live buyer character."))
            asking = int(listing.get("asking_price") or 0)
            details["buyer_gil"] = evidence.buyer_gil
            details["asking_price"] = asking
            if evidence.buyer_gil is None or evidence.buyer_gil < asking:
                issues.append(LSBValidationIssue("buyer_gil_insufficient", "Buyer does not have enough gil for the previewed purchase price."))
            details["buyer_inventory_free_slots"] = evidence.buyer_inventory_free_slots
            if evidence.buyer_inventory_free_slots is None:
                issues.append(LSBValidationIssue("buyer_inventory_capacity_unknown", "Buyer inventory capacity could not be verified."))
            elif evidence.buyer_inventory_free_slots <= 0:
                issues.append(LSBValidationIssue("buyer_inventory_full", "Buyer inventory has no free slot for the purchased item."))
            auction_id = int(payload.get("auction_id") or 0)
            details["cheapest_qualifying_auction_id"] = evidence.cheapest_qualifying_auction_id
            if evidence.cheapest_qualifying_auction_id not in (None, auction_id):
                issues.append(LSBValidationIssue("cheapest_listing_changed", "The previewed auction is no longer the cheapest qualifying active listing."))
        details["seller_delivery_row_count"] = evidence.delivery_row_count
        if evidence.delivery_row_count is None:
            issues.append(LSBValidationIssue("seller_settlement_unverifiable", "Seller delivery-box settlement state could not be read."))
    return LSBInvariantResult(tuple(issues), details)


def prepare_lsb_preview_validation(
    *,
    service,
    operation: str,
    environment: dict[str, Any],
    preview: dict[str, Any],
    server_root: Path | str,
) -> tuple[LSBPreparedValidation, LSBRereadEvidence, LSBInvariantResult, LSBPolicy, LSBPolicyBinding]:
    """Re-read one LSB preview and evaluate fail-closed source-backed invariants and policy binding."""
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

    policy = load_lsb_policy(server_root)
    binding = validate_lsb_policy_binding(preview.get("policy_binding"), policy)
    prepared = LSBPreparedValidation(op, preview_fp, current_fp, issues)
    invariants = _evaluate_invariants(operation=op, payload=payload, evidence=evidence, policy=policy)
    return prepared, evidence, invariants, policy, binding
