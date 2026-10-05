"""DSP/Topaz TEST-only exact-row player purchase executor.

The executor only runs when all mutation-relevant tables use transactional engines. Historical
Topaz/DSP char_inventory may be MyISAM, in which case this path fails closed rather than claiming
rollback safety that the database cannot provide.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import time
from typing import Any

from workbench.editors.character.adapters.inventory import build_basic_insert_plan, inspect_inventory_contract
from workbench.editors.character.inventory_slots import inspect_slots
from workbench.editors.character.schema import discover_character_schema
from workbench.editors.character.session_state import detect_online_state

from .legacy_test_executor import LegacyTestExecutionBlocked, evaluate_legacy_test_write_gate
from .write_probe import probe_write_readiness

_GIL_ITEM_ID = 65535
_TRANSACTIONAL_ENGINES = {"innodb", "ndb", "ndbcluster"}


@dataclass(frozen=True)
class PurchaseEngineProbe:
    engines: dict[str, str]
    transactional: bool
    blocking_tables: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def probe_player_purchase_engines(connection) -> PurchaseEngineProbe:
    tables = ("auction_house", "char_inventory", "delivery_box")
    cursor = connection.cursor()
    try:
        cursor.execute(
            "SELECT `TABLE_NAME`,`ENGINE` FROM `information_schema`.`TABLES` "
            "WHERE `TABLE_SCHEMA`=DATABASE() AND `TABLE_NAME` IN (%s,%s,%s)",
            tables,
        )
        engines = {str(row[0]): str(row[1] or "") for row in (cursor.fetchall() or [])}
    finally:
        cursor.close()
    blocking = tuple(
        table for table in tables
        if str(engines.get(table) or "").strip().lower() not in _TRANSACTIONAL_ENGINES
    )
    return PurchaseEngineProbe(engines=engines, transactional=not blocking, blocking_tables=blocking)


def _delivery_columns(connection) -> set[str]:
    cursor = connection.cursor()
    try:
        cursor.execute("DESCRIBE `delivery_box`")
        return {str(row[0]) for row in (cursor.fetchall() or [])}
    finally:
        cursor.close()


def _buyer_gil_row(cursor, buyer_id: int) -> tuple[int, int] | None:
    cursor.execute(
        "SELECT `itemId`,`quantity` FROM `char_inventory` "
        "WHERE `charid`=%s AND `location`=0 AND `slot`=0 FOR UPDATE",
        (int(buyer_id),),
    )
    row = cursor.fetchone()
    return None if not row else (int(row[0] or 0), int(row[1] or 0))


def execute_legacy_test_player_purchase(
    *,
    service,
    environment: dict[str, Any],
    auction_id: int,
    expected_price: int,
    buyer_id: int,
    confirmation: str,
    feature_enabled: bool | None = None,
    sold_at: int | None = None,
) -> dict[str, Any]:
    """Purchase one exact active AH row for one offline DSP/Topaz Test character.

    No cheapest-row substitution is performed: the selected auction_id is the only eligible row.
    """
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
    expected_price = int(expected_price)
    buyer_id = int(buyer_id)
    if auction_id <= 0 or expected_price <= 0 or buyer_id <= 0:
        raise LegacyTestExecutionBlocked("auction_id, expected_price, and buyer_id must be positive")

    readiness = probe_write_readiness(service.connection)
    if not readiness.legacy_purchase_prerequisites_present:
        raise LegacyTestExecutionBlocked("Legacy purchase settlement prerequisites are missing")

    engine_probe = probe_player_purchase_engines(service.connection)
    if not engine_probe.transactional:
        blocked = ", ".join(engine_probe.blocking_tables)
        raise LegacyTestExecutionBlocked(
            "Player purchase requires transactional AH/inventory/delivery tables; "
            f"non-transactional or unknown: {blocked}"
        )

    a = service.schema.auction_columns
    required = ("id", "item_id", "stack", "seller_id", "seller_name", "asking_price", "buyer_name", "sale_price", "sold_at")
    if any(not a.get(name) for name in required):
        raise LegacyTestExecutionBlocked("Legacy Auction House schema is missing player-purchase columns")

    char_schema = discover_character_schema(service.connection)
    family = str(environment.get("family") or "").strip().lower()
    inventory_contract = inspect_inventory_contract(char_schema, family)
    if not inventory_contract.basic_insert_verified:
        raise LegacyTestExecutionBlocked("Buyer inventory schema is not verified for direct purchase")
    session = detect_online_state(service.connection, char_schema, buyer_id)
    if session.online is not False:
        raise LegacyTestExecutionBlocked("Buyer must be offline before an administrative player purchase")
    buyer = service.character_snapshot(buyer_id)
    if not buyer:
        raise LegacyTestExecutionBlocked("Buyer character does not exist")
    slots = inspect_slots(service.connection, buyer_id, 0)
    if slots.first_free_slot is None:
        raise LegacyTestExecutionBlocked("Buyer Inventory is full")

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
            f"SELECT `{a['item_id']}`,`{a['stack']}`,`{a['seller_id']}`,`{a['seller_name']}`,"
            f"`{a['asking_price']}`,`{a['sale_price']}`,`{a['sold_at']}` FROM `auction_house` "
            f"WHERE `{a['id']}`=%s FOR UPDATE",
            (auction_id,),
        )
        row = cursor.fetchone()
        if not row:
            raise LegacyTestExecutionBlocked("The target auction row does not exist")
        item_id, stack, seller_id, seller_name, asking_price, sale_price, old_sold_at = row
        item_id = int(item_id)
        seller_id = int(seller_id or 0)
        asking_price = int(asking_price or 0)
        sale_price = int(sale_price or 0)
        old_sold_at = int(old_sold_at or 0)
        if sale_price != 0 or old_sold_at != 0:
            raise LegacyTestExecutionBlocked("The target auction row is no longer active")
        if asking_price != expected_price:
            raise LegacyTestExecutionBlocked("The target auction price changed; refresh before buying")
        if seller_id == buyer_id:
            raise LegacyTestExecutionBlocked("Buyer and seller cannot be the same character")

        item = service.item_snapshot(item_id)
        if not item:
            raise LegacyTestExecutionBlocked("Auction item metadata could not be verified")
        quantity = max(1, int(item.get("stack_size") or 1)) if bool(stack) else 1

        gil_row = _buyer_gil_row(cursor, buyer_id)
        if not gil_row or gil_row[0] != _GIL_ITEM_ID:
            raise LegacyTestExecutionBlocked("Buyer gil row is missing or malformed")
        gil_before = gil_row[1]
        if gil_before < asking_price:
            raise LegacyTestExecutionBlocked("Buyer does not have enough gil")

        settlement_sql = (
            "SELECT COUNT(*) FROM `delivery_box` WHERE `charid`=%s AND `box`=1 "
            "AND `itemid`=%s AND `quantity`=%s AND `sender`='AH-Jeuno'"
        )
        cursor.execute(settlement_sql, (seller_id, item_id, asking_price))
        settlement_before = int((cursor.fetchone() or (0,))[0] or 0)

        cursor.execute(
            "UPDATE `char_inventory` SET `quantity`=`quantity`-%s "
            "WHERE `charid`=%s AND `location`=0 AND `slot`=0 AND `itemId`=%s AND `quantity`=%s",
            (asking_price, buyer_id, _GIL_ITEM_ID, gil_before),
        )
        if int(getattr(cursor, "rowcount", 0) or 0) != 1:
            raise LegacyTestExecutionBlocked("Buyer gil changed during purchase")

        insert = build_basic_insert_plan(
            inventory_contract,
            char_id=buyer_id,
            item_id=item_id,
            location=0,
            slot=slots.first_free_slot,
            quantity=quantity,
        )
        cursor.execute(insert["sql"], insert["params"])
        if int(getattr(cursor, "rowcount", 0) or 0) != 1:
            raise LegacyTestExecutionBlocked("Buyer item insertion did not affect exactly one row")

        buyer_name = str(buyer.get("char_name") or "")
        cursor.execute(
            f"UPDATE `auction_house` SET `{a['buyer_name']}`=%s,`{a['sale_price']}`=%s,`{a['sold_at']}`=%s "
            f"WHERE `{a['id']}`=%s AND `{a['asking_price']}`=%s AND `{a['sale_price']}`=0 AND `{a['sold_at']}`=0",
            (buyer_name, asking_price, timestamp, auction_id, expected_price),
        )
        if int(getattr(cursor, "rowcount", 0) or 0) != 1:
            raise LegacyTestExecutionBlocked("Player purchase did not claim exactly one active listing")

        cursor.execute(settlement_sql, (seller_id, item_id, asking_price))
        settlement_after = int((cursor.fetchone() or (0,))[0] or 0)
        if settlement_after != settlement_before + 1:
            raise LegacyTestExecutionBlocked("Seller settlement was not queued exactly once")

        cursor.execute(
            "SELECT `quantity` FROM `char_inventory` WHERE `charid`=%s AND `location`=0 AND `slot`=0 AND `itemId`=%s",
            (buyer_id, _GIL_ITEM_ID),
        )
        final_gil = cursor.fetchone()
        expected_gil = gil_before - asking_price
        if not final_gil or int(final_gil[0] or 0) != expected_gil:
            raise LegacyTestExecutionBlocked("Buyer gil post-state verification failed")
        cursor.execute(
            "SELECT `itemId`,`quantity` FROM `char_inventory` WHERE `charid`=%s AND `location`=0 AND `slot`=%s",
            (buyer_id, slots.first_free_slot),
        )
        inv = cursor.fetchone()
        if not inv or int(inv[0] or 0) != item_id or int(inv[1] or 0) != quantity:
            raise LegacyTestExecutionBlocked("Buyer inventory post-state verification failed")
        cursor.execute(
            f"SELECT `{a['buyer_name']}`,`{a['sale_price']}`,`{a['sold_at']}` FROM `auction_house` WHERE `{a['id']}`=%s",
            (auction_id,),
        )
        sold = cursor.fetchone()
        if not sold or str(sold[0] or "") != buyer_name or int(sold[1] or 0) != asking_price or int(sold[2] or 0) != timestamp:
            raise LegacyTestExecutionBlocked("Auction post-state verification failed")

        connection.commit()
        return {
            "status": "committed",
            "operation": "player_purchase",
            "test_only": True,
            "auction_id": auction_id,
            "buyer_id": buyer_id,
            "buyer_name": buyer_name,
            "seller_id": seller_id,
            "seller_name": str(seller_name or ""),
            "item_id": item_id,
            "item_name": item.get("name"),
            "stack": bool(stack),
            "quantity": quantity,
            "sale_price": asking_price,
            "buyer_gil_before": gil_before,
            "buyer_gil_after": expected_gil,
            "buyer_inventory_slot": slots.first_free_slot,
            "seller_proceeds_queued": asking_price,
            "sold_at": timestamp,
            "engine_probe": engine_probe.as_dict(),
        }
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
