"""Database-backed, read-only reread adapter for DSP/Topaz Auction House validation.

The adapter opens a READ ONLY transaction, re-reads mutation-relevant state, then rolls the
transaction back unconditionally. It contains no mutation SQL and cannot commit.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any

from .transactional_adapter import PreparedTransaction, prepare_legacy_transaction


@dataclass(frozen=True)
class RereadEvidence:
    operation: str
    snapshot: dict[str, Any]
    seller_gil: int | None
    buyer_gil: int | None
    seller_active_listing_count: int | None
    inventory_rows: tuple[dict[str, Any], ...]
    delivery_rows: tuple[dict[str, Any], ...]
    claim_count: int | None
    cheapest_qualifying_auction_id: int | None
    transaction_mode: str = "read_only_rolled_back"

    def as_dict(self) -> dict[str, Any]:
        out = asdict(self)
        out["inventory_rows"] = [dict(row) for row in self.inventory_rows]
        out["delivery_rows"] = [dict(row) for row in self.delivery_rows]
        return out


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


def _rows(connection, sql: str, params: tuple[Any, ...]) -> list[tuple[Any, ...]]:
    cursor = connection.cursor()
    try:
        cursor.execute(sql, params)
        return list(cursor.fetchall() or [])
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


def _inventory_rows(connection, char_id: int | None, item_id: int | None) -> tuple[dict[str, Any], ...]:
    if not char_id or not item_id:
        return ()
    cols = _columns(connection, "char_inventory")
    char_col = _pick(cols, "charid", "charId", "char_id")
    item_col = _pick(cols, "itemId", "itemid", "item_id")
    qty_col = _pick(cols, "quantity", "qty")
    loc_col = _pick(cols, "location")
    slot_col = _pick(cols, "slot")
    if not char_col or not item_col or not qty_col:
        return ()
    select_cols = [char_col, item_col, qty_col]
    if loc_col:
        select_cols.append(loc_col)
    if slot_col:
        select_cols.append(slot_col)
    sql = "SELECT " + ", ".join(f"`{name}`" for name in select_cols) + f" FROM `char_inventory` WHERE `{char_col}`=%s AND `{item_col}`=%s ORDER BY " + ", ".join(f"`{name}`" for name in select_cols)
    rows = _rows(connection, sql, (int(char_id), int(item_id)))
    return tuple({name: row[index] for index, name in enumerate(select_cols)} for row in rows)


def _delivery_rows(connection, char_id: int | None) -> tuple[dict[str, Any], ...]:
    if not char_id:
        return ()
    cols = _columns(connection, "delivery_box")
    char_col = _pick(cols, "charid", "charId", "char_id")
    if not char_col:
        return ()
    wanted = [name for name in (char_col, "box", "slot", "itemid", "itemId", "quantity", "sender", "sent") if name in cols]
    if not wanted:
        return ()
    sql = "SELECT " + ", ".join(f"`{name}`" for name in wanted) + f" FROM `delivery_box` WHERE `{char_col}`=%s ORDER BY " + ", ".join(f"`{name}`" for name in wanted)
    rows = _rows(connection, sql, (int(char_id),))
    return tuple({name: row[index] for index, name in enumerate(wanted)} for row in rows)


def _active_listing_count(service, seller_id: int | None) -> int | None:
    if not seller_id:
        return None
    a = service.schema.auction_columns
    value = _scalar(
        service.connection,
        f"SELECT COUNT(*) FROM `auction_house` WHERE `{a['seller_id']}`=%s AND `{a['sold_at']}`=0",
        (int(seller_id),),
    )
    return int(value or 0)


def _cheapest_qualifying(service, listing: dict[str, Any] | None) -> int | None:
    if not listing:
        return None
    a = service.schema.auction_columns
    value = _scalar(
        service.connection,
        f"SELECT `{a['id']}` FROM `auction_house` WHERE `{a['item_id']}`=%s AND `{a['stack']}`=%s AND `{a['sold_at']}`=0 ORDER BY `{a['asking_price']}` ASC, `{a['id']}` ASC LIMIT 1",
        (int(listing['item_id']), 1 if listing.get('stack') else 0),
    )
    return None if value is None else int(value)


def collect_legacy_reread(*, service, operation: str, preview: dict[str, Any]) -> RereadEvidence:
    """Collect fresh DSP/Topaz state inside a read-only transaction and always roll it back."""
    connection = service.connection
    cursor = connection.cursor()
    try:
        cursor.execute("START TRANSACTION READ ONLY")
    finally:
        cursor.close()

    try:
        payload = dict(preview.get("payload") or {})
        op = str(operation or "").strip().lower()
        if op == "list_item":
            item = service.item_snapshot(int(payload.get("item_id") or 0))
            seller = service.character_snapshot(int(payload.get("seller_id") or 0))
            snapshot = {"item": item, "seller": seller}
            seller_id = int(payload.get("seller_id") or 0) or None
            item_id = int(payload.get("item_id") or 0) or None
            return RereadEvidence(
                operation=op,
                snapshot=snapshot,
                seller_gil=_character_gil(connection, seller_id),
                buyer_gil=None,
                seller_active_listing_count=_active_listing_count(service, seller_id),
                inventory_rows=_inventory_rows(connection, seller_id, item_id),
                delivery_rows=_delivery_rows(connection, seller_id),
                claim_count=None,
                cheapest_qualifying_auction_id=None,
            )

        if op in {"purchase_item", "admin_cleanup"}:
            auction_id = int(payload.get("auction_id") or 0)
            buyer_id = int(payload.get("buyer_id") or 0) or None
            listing = service.active_listing_by_id(auction_id)
            buyer = None if buyer_id is None else service.character_snapshot(buyer_id)
            snapshot = {"listing": listing, "buyer": buyer}
            seller_id = int((listing or {}).get("seller_id") or 0) or None
            item_id = int((listing or {}).get("item_id") or 0) or None
            return RereadEvidence(
                operation=op,
                snapshot=snapshot,
                seller_gil=_character_gil(connection, seller_id),
                buyer_gil=_character_gil(connection, buyer_id),
                seller_active_listing_count=_active_listing_count(service, seller_id),
                inventory_rows=_inventory_rows(connection, buyer_id, item_id),
                delivery_rows=_delivery_rows(connection, seller_id),
                claim_count=1 if listing is not None else 0,
                cheapest_qualifying_auction_id=_cheapest_qualifying(service, listing),
            )

        raise ValueError(f"Unsupported reread operation: {op or 'unknown'}")
    finally:
        connection.rollback()


def prepare_from_database_reread(
    *,
    service,
    family: str,
    operation: str,
    environment: dict[str, Any],
    preview: dict[str, Any],
    preview_environment: dict[str, Any] | None = None,
) -> tuple[PreparedTransaction, RereadEvidence]:
    evidence = collect_legacy_reread(service=service, operation=operation, preview=preview)
    prepared = prepare_legacy_transaction(
        family=family,
        schema_family_hint=service.schema.family_hint,
        operation=operation,
        environment=environment,
        preview=preview,
        current={
            "snapshot": evidence.snapshot,
            "claim_count": evidence.claim_count,
            "cheapest_qualifying_auction_id": evidence.cheapest_qualifying_auction_id,
        },
        preview_environment=preview_environment,
    )
    return prepared, evidence
