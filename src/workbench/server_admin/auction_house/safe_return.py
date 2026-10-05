"""Select a rollback-safe DSP/Topaz AH return strategy for Test administration."""
from __future__ import annotations

from typing import Any

from .legacy_test_executor import LegacyTestExecutionBlocked, evaluate_legacy_test_write_gate
from .listing_management import execute_legacy_test_return_to_seller
from .write_probe import probe_write_readiness

_TRANSACTIONAL_ENGINES = {"innodb", "ndb", "ndbcluster"}


def _table_engines(connection, names: tuple[str, ...]) -> dict[str, str]:
    cursor = connection.cursor()
    try:
        placeholders = ",".join(["%s"] * len(names))
        cursor.execute(
            "SELECT `TABLE_NAME`,`ENGINE` FROM `information_schema`.`TABLES` "
            f"WHERE `TABLE_SCHEMA`=DATABASE() AND `TABLE_NAME` IN ({placeholders})",
            names,
        )
        return {str(row[0]): str(row[1] or "") for row in (cursor.fetchall() or [])}
    finally:
        cursor.close()


def _transactional(engines: dict[str, str], *names: str) -> bool:
    return all(str(engines.get(name) or "").strip().lower() in _TRANSACTIONAL_ENGINES for name in names)


def _delivery_columns(connection) -> set[str]:
    cursor = connection.cursor()
    try:
        cursor.execute("DESCRIBE `delivery_box`")
        return {str(row[0]) for row in (cursor.fetchall() or [])}
    finally:
        cursor.close()


def execute_legacy_test_delivery_return(
    *, service, environment: dict[str, Any], auction_id: int, confirmation: str,
    feature_enabled: bool | None = None,
) -> dict[str, Any]:
    """Remove one active listing and queue its item in the seller delivery box atomically."""
    gate = evaluate_legacy_test_write_gate(
        environment=environment,
        schema_family_hint=service.schema.family_hint,
        confirmation=confirmation,
        feature_enabled=feature_enabled,
    )
    if not gate.ready:
        codes = ", ".join(issue.code for issue in gate.issues if issue.blocking)
        raise LegacyTestExecutionBlocked(f"Auction House legacy TEST execution blocked: {codes}")

    auction_id = int(auction_id)
    if auction_id <= 0:
        raise LegacyTestExecutionBlocked("auction_id must be positive")

    engines = _table_engines(service.connection, ("auction_house", "delivery_box"))
    if not _transactional(engines, "auction_house", "delivery_box"):
        raise LegacyTestExecutionBlocked("Delivery-box return requires transactional auction_house and delivery_box tables")
    readiness = probe_write_readiness(service.connection)
    if "delivery_box_insert" not in set(readiness.triggers):
        raise LegacyTestExecutionBlocked("delivery_box_insert trigger is required for safe delivery return")

    required_delivery = {
        "charid", "charname", "box", "slot", "itemid", "itemsubid", "quantity",
        "extra", "senderid", "sender", "received", "sent",
    }
    if not required_delivery.issubset(_delivery_columns(service.connection)):
        raise LegacyTestExecutionBlocked("delivery_box schema does not match the verified legacy return contract")

    a = service.schema.auction_columns
    required = ("id", "item_id", "stack", "seller_id", "seller_name", "asking_price", "sale_price", "sold_at")
    if any(not a.get(name) for name in required):
        raise LegacyTestExecutionBlocked("Legacy Auction House schema is missing required return columns")

    connection = service.connection
    cursor = connection.cursor()
    try:
        cursor.execute("START TRANSACTION")
        cursor.execute(
            f"SELECT `{a['item_id']}`,`{a['stack']}`,`{a['seller_id']}`,`{a['seller_name']}`,"
            f"`{a['asking_price']}`,`{a['sale_price']}`,`{a['sold_at']}` FROM `auction_house` "
            f"WHERE `{a['id']}`=%s FOR UPDATE",
            (auction_id,),
        )
        row = cursor.fetchone()
        if not row:
            raise LegacyTestExecutionBlocked("The target auction row does not exist")
        item_id, stack, seller_id, seller_name, asking_price, sale_price, sold_at = row
        item_id = int(item_id)
        seller_id = int(seller_id or 0)
        asking_price = int(asking_price or 0)
        if int(sale_price or 0) != 0 or int(sold_at or 0) != 0:
            raise LegacyTestExecutionBlocked("The target auction row is no longer active")

        item = service.item_snapshot(item_id)
        seller = service.character_snapshot(seller_id)
        if not item or not seller:
            raise LegacyTestExecutionBlocked("Item or seller state could not be verified")
        quantity = max(1, int(item.get("stack_size") or 1)) if bool(stack) else 1

        count_sql = (
            "SELECT COUNT(*) FROM `delivery_box` WHERE `charid`=%s AND `box`=1 "
            "AND `itemid`=%s AND `quantity`=%s AND `sender`='AH-Admin Return'"
        )
        cursor.execute(count_sql, (seller_id, item_id, quantity))
        before = int((cursor.fetchone() or (0,))[0] or 0)

        cursor.execute(
            f"DELETE FROM `auction_house` WHERE `{a['id']}`=%s AND `{a['sale_price']}`=0 AND `{a['sold_at']}`=0 LIMIT 1",
            (auction_id,),
        )
        if int(getattr(cursor, "rowcount", 0) or 0) != 1:
            raise LegacyTestExecutionBlocked("Return did not remove exactly one active listing")

        cursor.execute(
            "INSERT INTO `delivery_box` "
            "(`charid`,`charname`,`box`,`slot`,`itemid`,`itemsubid`,`quantity`,`extra`,`senderid`,`sender`,`received`,`sent`) "
            "VALUES (%s,%s,1,0,%s,0,%s,NULL,0,'AH-Admin Return',0,0)",
            (seller_id, str(seller.get("char_name") or seller_name or ""), item_id, quantity),
        )
        if int(getattr(cursor, "rowcount", 0) or 0) != 1:
            raise LegacyTestExecutionBlocked("Delivery return did not queue exactly one item row")

        cursor.execute(count_sql, (seller_id, item_id, quantity))
        after = int((cursor.fetchone() or (0,))[0] or 0)
        if after != before + 1:
            raise LegacyTestExecutionBlocked("Delivery return post-state verification failed")
        cursor.execute(f"SELECT 1 FROM `auction_house` WHERE `{a['id']}`=%s LIMIT 1", (auction_id,))
        if cursor.fetchone() is not None:
            raise LegacyTestExecutionBlocked("Auction row still exists after delivery return")

        connection.commit()
        return {
            "status": "committed",
            "operation": "return_to_seller",
            "return_method": "delivery_box",
            "test_only": True,
            "auction_id": auction_id,
            "seller_id": seller_id,
            "seller_name": seller.get("char_name"),
            "item_id": item_id,
            "item_name": item.get("name"),
            "stack": bool(stack),
            "quantity": quantity,
            "asking_price": asking_price,
            "listing_fee_refunded": 0,
            "note": "Item queued to seller delivery box because direct Inventory rollback safety was unavailable.",
        }
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()


def execute_legacy_test_safe_return(
    *, service, environment: dict[str, Any], auction_id: int, confirmation: str,
    feature_enabled: bool | None = None,
) -> dict[str, Any]:
    """Prefer native-style Inventory return when transactional; otherwise use delivery box."""
    engines = _table_engines(service.connection, ("auction_house", "char_inventory", "delivery_box"))
    if _transactional(engines, "auction_house", "char_inventory"):
        result = execute_legacy_test_return_to_seller(
            service=service,
            environment=environment,
            auction_id=auction_id,
            confirmation=confirmation,
            feature_enabled=feature_enabled,
        )
        result["return_method"] = "inventory"
        return result
    if _transactional(engines, "auction_house", "delivery_box"):
        return execute_legacy_test_delivery_return(
            service=service,
            environment=environment,
            auction_id=auction_id,
            confirmation=confirmation,
            feature_enabled=feature_enabled,
        )
    raise LegacyTestExecutionBlocked(
        "No rollback-safe return path is available: Inventory and delivery-box strategies both require transactional tables"
    )
