"""DSP/Topaz TEST-only administrative Auction House cleanup purchase."""
from __future__ import annotations

import time
from typing import Any

from .legacy_test_executor import LegacyTestExecutionBlocked, evaluate_legacy_test_write_gate
from .write_probe import probe_write_readiness


def _delivery_columns(connection) -> set[str]:
    cursor = connection.cursor()
    try:
        cursor.execute("DESCRIBE `delivery_box`")
        return {str(row[0]) for row in (cursor.fetchall() or [])}
    finally:
        cursor.close()


def execute_legacy_test_admin_buy(
    *, service, environment: dict[str, Any], auction_id: int, expected_price: int,
    confirmation: str, feature_enabled: bool | None = None, sold_at: int | None = None,
) -> dict[str, Any]:
    """Close one active listing as an admin sale and verify seller settlement."""
    gate = evaluate_legacy_test_write_gate(
        environment=environment,
        schema_family_hint=service.schema.family_hint,
        confirmation=confirmation,
        feature_enabled=feature_enabled,
    )
    if not gate.ready:
        codes = ", ".join(i.code for i in gate.issues if i.blocking)
        raise LegacyTestExecutionBlocked(f"Auction House legacy TEST execution blocked: {codes}")

    auction_id = int(auction_id)
    expected_price = int(expected_price)
    if auction_id <= 0 or expected_price <= 0:
        raise LegacyTestExecutionBlocked("auction_id and expected_price must be positive")

    readiness = probe_write_readiness(service.connection)
    if not readiness.legacy_purchase_prerequisites_present:
        raise LegacyTestExecutionBlocked("Legacy purchase settlement prerequisites are missing")

    a = service.schema.auction_columns
    required = ("id", "item_id", "stack", "seller_id", "seller_name", "asking_price", "buyer_name", "sale_price", "sold_at")
    if any(not a.get(name) for name in required):
        raise LegacyTestExecutionBlocked("Legacy Auction House schema is missing admin-buy columns")

    needed_delivery = {"charid", "box", "itemid", "quantity", "sender"}
    if not needed_delivery.issubset(_delivery_columns(service.connection)):
        raise LegacyTestExecutionBlocked("delivery_box schema cannot verify seller settlement")

    timestamp = int(sold_at if sold_at is not None else time.time())
    if timestamp <= 0:
        raise LegacyTestExecutionBlocked("sold_at must be positive")

    connection = service.connection
    cursor = connection.cursor()
    try:
        cursor.execute("START TRANSACTION")
        cursor.execute(
            f"SELECT `{a['item_id']}`,`{a['stack']}`,`{a['seller_id']}`,`{a['seller_name']}`,`{a['asking_price']}`,`{a['sale_price']}`,`{a['sold_at']}` "
            f"FROM `auction_house` WHERE `{a['id']}`=%s FOR UPDATE",
            (auction_id,),
        )
        row = cursor.fetchone()
        if not row:
            raise LegacyTestExecutionBlocked("The target auction row does not exist")
        item_id, stack, seller_id, seller_name, asking_price, sale_price, old_sold_at = row
        item_id, seller_id = int(item_id), int(seller_id or 0)
        asking_price, sale_price, old_sold_at = int(asking_price or 0), int(sale_price or 0), int(old_sold_at or 0)
        if sale_price != 0 or old_sold_at != 0:
            raise LegacyTestExecutionBlocked("The target auction row is no longer active")
        if asking_price != expected_price:
            raise LegacyTestExecutionBlocked("The target auction price changed; refresh before buying")

        settlement_sql = (
            "SELECT COUNT(*) FROM `delivery_box` WHERE `charid`=%s AND `box`=1 "
            "AND `itemid`=%s AND `quantity`=%s AND `sender`='AH-Jeuno'"
        )
        cursor.execute(settlement_sql, (seller_id, item_id, asking_price))
        before = int((cursor.fetchone() or (0,))[0] or 0)

        cursor.execute(
            f"UPDATE `auction_house` SET `{a['buyer_name']}`=%s,`{a['sale_price']}`=%s,`{a['sold_at']}`=%s "
            f"WHERE `{a['id']}`=%s AND `{a['asking_price']}`=%s AND `{a['sale_price']}`=0 AND `{a['sold_at']}`=0",
            ("ADMIN", asking_price, timestamp, auction_id, expected_price),
        )
        if int(getattr(cursor, "rowcount", 0) or 0) != 1:
            raise LegacyTestExecutionBlocked("Admin buy did not claim exactly one active listing")

        cursor.execute(settlement_sql, (seller_id, item_id, asking_price))
        after = int((cursor.fetchone() or (0,))[0] or 0)
        if after != before + 1:
            raise LegacyTestExecutionBlocked("Seller settlement was not queued exactly once")

        cursor.execute(
            f"SELECT `{a['buyer_name']}`,`{a['sale_price']}`,`{a['sold_at']}` FROM `auction_house` WHERE `{a['id']}`=%s",
            (auction_id,),
        )
        sold = cursor.fetchone()
        if not sold or str(sold[0] or "") != "ADMIN" or int(sold[1] or 0) != asking_price or int(sold[2] or 0) != timestamp:
            raise LegacyTestExecutionBlocked("Admin-buy post-state verification failed")

        item = service.item_snapshot(item_id)
        quantity = max(1, int((item or {}).get("stack_size") or 1)) if bool(stack) else 1
        connection.commit()
        return {
            "status": "committed", "operation": "admin_buy", "test_only": True,
            "auction_id": auction_id, "item_id": item_id, "item_name": (item or {}).get("name"),
            "stack": bool(stack), "quantity": quantity, "seller_id": seller_id,
            "seller_name": str(seller_name or ""), "sale_price": asking_price,
            "buyer_name": "ADMIN", "buyer_inventory_added": 0, "buyer_gil_charged": 0,
            "seller_proceeds_queued": asking_price, "sold_at": timestamp,
            "note": "Administrative cleanup sale: seller is compensated by native AH delivery-box triggers and the item is consumed by administration.",
        }
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
