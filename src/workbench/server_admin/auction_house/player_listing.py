"""DSP/Topaz TEST-only player-backed Auction House listing executor."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import time
from typing import Any

from workbench.editors.character.schema import discover_character_schema
from workbench.editors.character.session_state import detect_online_state

from .config_policy import load_active_legacy_policy
from .invariants import legacy_listing_fee
from .legacy_test_executor import LegacyTestExecutionBlocked, evaluate_legacy_test_write_gate

_GIL_ITEM_ID = 65535
_TRANSACTIONAL_ENGINES = {"innodb", "ndb", "ndbcluster"}


@dataclass(frozen=True)
class ListingEngineProbe:
    engines: dict[str, str]
    transactional: bool
    blocking_tables: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def probe_player_listing_engines(connection) -> ListingEngineProbe:
    tables = ("auction_house", "char_inventory")
    cursor = connection.cursor()
    try:
        cursor.execute(
            "SELECT `TABLE_NAME`,`ENGINE` FROM `information_schema`.`TABLES` "
            "WHERE `TABLE_SCHEMA`=DATABASE() AND `TABLE_NAME` IN (%s,%s)",
            tables,
        )
        engines = {str(row[0]): str(row[1] or "") for row in (cursor.fetchall() or [])}
    finally:
        cursor.close()
    blocking = tuple(
        table for table in tables
        if str(engines.get(table) or "").strip().lower() not in _TRANSACTIONAL_ENGINES
    )
    return ListingEngineProbe(engines=engines, transactional=not blocking, blocking_tables=blocking)


def execute_legacy_test_player_listing(
    *,
    service,
    server_root,
    environment: dict[str, Any],
    seller_id: int,
    inventory_slot: int,
    item_id: int,
    price: int,
    stack: bool,
    confirmation: str,
    feature_enabled: bool | None = None,
    listed_at: int | None = None,
) -> dict[str, Any]:
    gate = evaluate_legacy_test_write_gate(
        environment=environment,
        schema_family_hint=service.schema.family_hint,
        confirmation=confirmation,
        feature_enabled=feature_enabled,
    )
    if not gate.ready:
        codes = ", ".join(issue.code for issue in gate.issues if issue.blocking)
        raise LegacyTestExecutionBlocked(f"Auction House legacy TEST execution blocked: {codes}")

    seller_id = int(seller_id)
    inventory_slot = int(inventory_slot)
    item_id = int(item_id)
    price = int(price)
    stack = bool(stack)
    if seller_id <= 0 or inventory_slot <= 0 or item_id <= 0 or price <= 0:
        raise LegacyTestExecutionBlocked("seller_id, inventory_slot, item_id, and price must be positive")

    family = str(environment.get("family") or "").strip().lower()
    policy_load = load_active_legacy_policy(server_root=server_root, family=family)
    if not policy_load.policy_ready or policy_load.policy is None:
        issues = ", ".join(issue.code for issue in policy_load.issues if issue.blocking)
        raise LegacyTestExecutionBlocked(f"Active Auction House policy is not ready: {issues or 'unknown policy error'}")
    policy = policy_load.policy

    engine_probe = probe_player_listing_engines(service.connection)
    if not engine_probe.transactional:
        blocked = ", ".join(engine_probe.blocking_tables)
        raise LegacyTestExecutionBlocked(
            "Player-backed listing requires transactional auction_house and char_inventory tables; "
            f"non-transactional or unknown: {blocked}"
        )

    seller = service.character_snapshot(seller_id)
    item = service.item_snapshot(item_id)
    if not seller:
        raise LegacyTestExecutionBlocked("Seller character does not exist")
    if not item:
        raise LegacyTestExecutionBlocked("Item metadata could not be verified")
    if int(item.get("category_id") or 0) <= 0:
        raise LegacyTestExecutionBlocked("Item is not assigned to an Auction House category")
    stack_size = max(1, int(item.get("stack_size") or 1))
    if stack and stack_size <= 1:
        raise LegacyTestExecutionBlocked("Item cannot be listed as a stack")
    required_quantity = stack_size if stack else 1
    fee = legacy_listing_fee(price, stack=stack, policy=policy)

    char_schema = discover_character_schema(service.connection)
    session = detect_online_state(service.connection, char_schema, seller_id)
    if session.online is not False:
        raise LegacyTestExecutionBlocked("Seller must be offline before an administrative player listing")

    a = service.schema.auction_columns
    required_columns = ("id", "item_id", "stack", "seller_id", "listed_at", "asking_price", "sale_price", "sold_at")
    if any(not a.get(name) for name in required_columns):
        raise LegacyTestExecutionBlocked("Legacy Auction House schema is missing player-listing columns")

    timestamp = int(listed_at if listed_at is not None else time.time())
    if timestamp <= 0:
        raise LegacyTestExecutionBlocked("listed_at must be positive")

    connection = service.connection
    cursor = connection.cursor()
    auction_id: int | None = None
    try:
        cursor.execute("START TRANSACTION")
        cursor.execute(
            "SELECT `itemId`,`quantity` FROM `char_inventory` "
            "WHERE `charid`=%s AND `location`=0 AND `slot`=%s FOR UPDATE",
            (seller_id, inventory_slot),
        )
        inventory_row = cursor.fetchone()
        if not inventory_row:
            raise LegacyTestExecutionBlocked("Selected seller Inventory slot is empty")
        current_item_id, current_quantity = int(inventory_row[0] or 0), int(inventory_row[1] or 0)
        if current_item_id != item_id:
            raise LegacyTestExecutionBlocked("Selected Inventory slot no longer contains the requested item")
        if stack and current_quantity != stack_size:
            raise LegacyTestExecutionBlocked(f"Stack listing requires exactly one full stack of {stack_size}")
        if not stack and current_quantity < 1:
            raise LegacyTestExecutionBlocked("Selected Inventory slot has no item quantity available")

        cursor.execute(
            "SELECT `itemId`,`quantity` FROM `char_inventory` "
            "WHERE `charid`=%s AND `location`=0 AND `slot`=0 FOR UPDATE",
            (seller_id,),
        )
        gil_row = cursor.fetchone()
        if not gil_row or int(gil_row[0] or 0) != _GIL_ITEM_ID:
            raise LegacyTestExecutionBlocked("Seller gil row is missing or malformed")
        gil_before = int(gil_row[1] or 0)
        if gil_before < fee:
            raise LegacyTestExecutionBlocked(f"Seller has {gil_before} gil but listing fee is {fee}")

        cursor.execute(
            f"SELECT COUNT(*) FROM `auction_house` WHERE `{a['seller_id']}`=%s AND `{a['sale_price']}`=0 AND `{a['sold_at']}`=0",
            (seller_id,),
        )
        active_count = int((cursor.fetchone() or (0,))[0] or 0)
        if int(policy.list_limit) > 0 and active_count >= int(policy.list_limit):
            raise LegacyTestExecutionBlocked(
                f"Seller already has {active_count} active listings; configured limit is {policy.list_limit}"
            )

        insert_fields = [a["item_id"], a["stack"], a["seller_id"]]
        params: list[Any] = [item_id, 1 if stack else 0, seller_id]
        if a.get("seller_name"):
            insert_fields.append(a["seller_name"])
            params.append(str(seller.get("char_name") or ""))
        insert_fields.extend([a["listed_at"], a["asking_price"]])
        params.extend([timestamp, price])
        cursor.execute(
            "INSERT INTO `auction_house`(" + ",".join(f"`{name}`" for name in insert_fields) + ") VALUES(" + ",".join(["%s"] * len(insert_fields)) + ")",
            tuple(params),
        )
        if int(getattr(cursor, "rowcount", 0) or 0) != 1:
            raise LegacyTestExecutionBlocked("Player listing did not create exactly one auction row")
        auction_id = int(getattr(cursor, "lastrowid", 0) or 0)
        if auction_id <= 0:
            raise LegacyTestExecutionBlocked("Player listing did not return an auction ID")

        remaining = current_quantity - required_quantity
        if remaining == 0:
            cursor.execute(
                "DELETE FROM `char_inventory` WHERE `charid`=%s AND `location`=0 AND `slot`=%s AND `itemId`=%s AND `quantity`=%s",
                (seller_id, inventory_slot, item_id, current_quantity),
            )
        else:
            cursor.execute(
                "UPDATE `char_inventory` SET `quantity`=%s WHERE `charid`=%s AND `location`=0 AND `slot`=%s AND `itemId`=%s AND `quantity`=%s",
                (remaining, seller_id, inventory_slot, item_id, current_quantity),
            )
        if int(getattr(cursor, "rowcount", 0) or 0) != 1:
            raise LegacyTestExecutionBlocked("Seller inventory changed during listing")

        cursor.execute(
            "UPDATE `char_inventory` SET `quantity`=%s WHERE `charid`=%s AND `location`=0 AND `slot`=0 AND `itemId`=%s AND `quantity`=%s",
            (gil_before - fee, seller_id, _GIL_ITEM_ID, gil_before),
        )
        if int(getattr(cursor, "rowcount", 0) or 0) != 1:
            raise LegacyTestExecutionBlocked("Seller gil changed during listing")

        cursor.execute(
            f"SELECT `{a['item_id']}`,`{a['stack']}`,`{a['seller_id']}`,`{a['asking_price']}`,`{a['sale_price']}`,`{a['sold_at']}` "
            f"FROM `auction_house` WHERE `{a['id']}`=%s",
            (auction_id,),
        )
        posted = cursor.fetchone()
        if not posted or (
            int(posted[0]) != item_id or bool(posted[1]) != stack or int(posted[2]) != seller_id
            or int(posted[3]) != price or int(posted[4] or 0) != 0 or int(posted[5] or 0) != 0
        ):
            raise LegacyTestExecutionBlocked("Auction listing post-state verification failed")

        cursor.execute(
            "SELECT `quantity` FROM `char_inventory` WHERE `charid`=%s AND `location`=0 AND `slot`=0 AND `itemId`=%s",
            (seller_id, _GIL_ITEM_ID),
        )
        final_gil = cursor.fetchone()
        if not final_gil or int(final_gil[0] or 0) != gil_before - fee:
            raise LegacyTestExecutionBlocked("Seller gil post-state verification failed")

        cursor.execute(
            "SELECT `itemId`,`quantity` FROM `char_inventory` WHERE `charid`=%s AND `location`=0 AND `slot`=%s",
            (seller_id, inventory_slot),
        )
        remaining_row = cursor.fetchone()
        if remaining == 0 and remaining_row is not None:
            raise LegacyTestExecutionBlocked("Seller inventory item was not fully removed")
        if remaining > 0 and (not remaining_row or int(remaining_row[0]) != item_id or int(remaining_row[1]) != remaining):
            raise LegacyTestExecutionBlocked("Seller inventory post-state verification failed")

        connection.commit()
        return {
            "status": "committed",
            "operation": "player_listing",
            "test_only": True,
            "auction_id": auction_id,
            "seller_id": seller_id,
            "seller_name": seller.get("char_name"),
            "inventory_slot": inventory_slot,
            "item_id": item_id,
            "item_name": item.get("name"),
            "stack": stack,
            "quantity": required_quantity,
            "price": price,
            "listing_fee": fee,
            "seller_gil_before": gil_before,
            "seller_gil_after": gil_before - fee,
            "active_listings_before": active_count,
            "listed_at": timestamp,
            "policy_source": policy_load.source_path,
            "policy_fingerprint": policy_load.policy_fingerprint,
            "engine_probe": engine_probe.as_dict(),
        }
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
