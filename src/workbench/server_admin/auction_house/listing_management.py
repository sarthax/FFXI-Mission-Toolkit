"""Granular DSP/Topaz Auction House listing browsing and TEST-only return-to-seller support."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from workbench.editors.character.adapters.inventory import build_basic_insert_plan, inspect_inventory_contract
from workbench.editors.character.inventory_slots import inspect_slots
from workbench.editors.character.schema import discover_character_schema
from workbench.editors.character.session_state import detect_online_state

from .categories import category_metadata
from .legacy_test_executor import LegacyTestExecutionBlocked, evaluate_legacy_test_write_gate


@dataclass(frozen=True)
class ListingFilter:
    seller_id: int | None = None
    seller_name: str | None = None
    category_id: int | None = None
    item_id: int | None = None
    q: str | None = None
    limit: int = 200

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def browse_active_listings(service, filters: ListingFilter) -> list[dict[str, Any]]:
    """Browse active Auction House rows by seller, category, item, or text."""
    a = service.schema.auction_columns
    i = service.schema.item_columns
    seller_name_expr = f"ah.`{a['seller_name']}`" if a.get("seller_name") else "NULL"
    clauses = [f"ah.`{a['sold_at']}`=0", f"ah.`{a['sale_price']}`=0"]
    params: list[Any] = []

    if filters.seller_id is not None:
        clauses.append(f"ah.`{a['seller_id']}`=%s")
        params.append(int(filters.seller_id))
    if filters.seller_name and a.get("seller_name"):
        clauses.append(f"ah.`{a['seller_name']}` LIKE %s")
        params.append(f"%{str(filters.seller_name).strip()}%")
    if filters.category_id is not None:
        clauses.append(f"ib.`{i['ah_category']}`=%s")
        params.append(int(filters.category_id))
    if filters.item_id is not None:
        clauses.append(f"ah.`{a['item_id']}`=%s")
        params.append(int(filters.item_id))
    if filters.q:
        term = str(filters.q).strip()
        if term.isdigit():
            clauses.append(f"(ah.`{a['item_id']}`=%s OR ah.`{a['id']}`=%s OR ib.`{i['name']}` LIKE %s)")
            params.extend([int(term), int(term), f"%{term}%"])
        else:
            name_parts = [f"ib.`{i['name']}` LIKE %s"]
            params.append(f"%{term}%")
            if a.get("seller_name"):
                name_parts.append(f"ah.`{a['seller_name']}` LIKE %s")
                params.append(f"%{term}%")
            clauses.append("(" + " OR ".join(name_parts) + ")")

    limit = max(1, min(int(filters.limit), 1000))
    params.append(limit)
    sql = (
        "SELECT "
        f"ah.`{a['id']}`,ah.`{a['item_id']}`,ib.`{i['name']}`,ib.`{i['stack_size']}`,ib.`{i['ah_category']}`,"
        f"ah.`{a['stack']}`,ah.`{a['seller_id']}`,{seller_name_expr},ah.`{a['listed_at']}`,ah.`{a['asking_price']}` "
        "FROM `auction_house` ah JOIN `item_basic` ib "
        f"ON ib.`{i['item_id']}`=ah.`{a['item_id']}` "
        "WHERE " + " AND ".join(clauses) +
        f" ORDER BY ah.`{a['listed_at']}` ASC, ah.`{a['id']}` ASC LIMIT %s"
    )
    cursor = service.connection.cursor()
    try:
        cursor.execute(sql, tuple(params))
        rows = []
        for r in cursor.fetchall() or []:
            category_id = int(r[4] or 0)
            meta = category_metadata(category_id)
            rows.append({
                "auction_id": int(r[0]),
                "item_id": int(r[1]),
                "item_name": str(r[2] or ""),
                "stack_size": max(1, int(r[3] or 1)),
                "category_id": category_id,
                "category_path": meta.path,
                "stack": bool(r[5]),
                "seller_id": int(r[6] or 0),
                "seller_name": r[7],
                "listed_at": int(r[8] or 0) or None,
                "asking_price": int(r[9] or 0),
                "quantity": max(1, int(r[3] or 1)) if bool(r[5]) else 1,
                "available_actions": ["preview_buy", "return_to_seller"],
            })
        return rows
    finally:
        cursor.close()


def execute_legacy_test_return_to_seller(
    *,
    service,
    environment: dict[str, Any],
    auction_id: int,
    confirmation: str,
    feature_enabled: bool | None = None,
) -> dict[str, Any]:
    """Cancel one active DSP/Topaz listing and return its item to seller Inventory atomically."""
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

    a = service.schema.auction_columns
    required = ("id", "item_id", "stack", "seller_id", "asking_price", "sale_price", "sold_at")
    if any(not a.get(name) for name in required):
        raise LegacyTestExecutionBlocked("The live legacy Auction House schema is missing required return columns")

    connection = service.connection
    cursor = connection.cursor()
    try:
        cursor.execute("START TRANSACTION")
        cursor.execute(
            f"SELECT `{a['id']}`,`{a['item_id']}`,`{a['stack']}`,`{a['seller_id']}`,`{a['asking_price']}`,`{a['sale_price']}`,`{a['sold_at']}` "
            f"FROM `auction_house` WHERE `{a['id']}`=%s FOR UPDATE",
            (auction_id,),
        )
        row = cursor.fetchone()
        if not row:
            raise LegacyTestExecutionBlocked("The target auction row does not exist")
        current = {
            "auction_id": int(row[0]),
            "item_id": int(row[1]),
            "stack": bool(row[2]),
            "seller_id": int(row[3] or 0),
            "asking_price": int(row[4] or 0),
            "sale_price": int(row[5] or 0),
            "sold_at": int(row[6] or 0),
        }
        if current["sale_price"] != 0 or current["sold_at"] != 0:
            raise LegacyTestExecutionBlocked("The target auction row is no longer active")

        item = service.item_snapshot(current["item_id"])
        seller = service.character_snapshot(current["seller_id"])
        if not item or not seller:
            raise LegacyTestExecutionBlocked("Item or seller state could not be verified")
        quantity = max(1, int(item.get("stack_size") or 1)) if current["stack"] else 1

        char_schema = discover_character_schema(connection)
        family = str(environment.get("family") or "").strip().lower()
        inventory_contract = inspect_inventory_contract(char_schema, family)
        if not inventory_contract.basic_insert_verified:
            raise LegacyTestExecutionBlocked("Seller inventory schema is not verified for direct return")
        session = detect_online_state(connection, char_schema, current["seller_id"])
        if session.online is not False:
            raise LegacyTestExecutionBlocked("Seller must be offline before an administrative AH return")
        slots = inspect_slots(connection, current["seller_id"], 0)
        if slots.first_free_slot is None:
            raise LegacyTestExecutionBlocked("Seller Inventory is full; listing was not removed")

        insert = build_basic_insert_plan(
            inventory_contract,
            char_id=current["seller_id"],
            item_id=current["item_id"],
            location=0,
            slot=slots.first_free_slot,
            quantity=quantity,
        )

        cursor.execute(
            f"DELETE FROM `auction_house` WHERE `{a['id']}`=%s AND `{a['sale_price']}`=0 AND `{a['sold_at']}`=0 LIMIT 1",
            (auction_id,),
        )
        if int(getattr(cursor, "rowcount", 0) or 0) != 1:
            raise LegacyTestExecutionBlocked("Return did not remove exactly one active listing")

        cursor.execute(insert["sql"], insert["params"])
        if int(getattr(cursor, "rowcount", 0) or 0) != 1:
            raise LegacyTestExecutionBlocked("Return did not create exactly one seller inventory row")

        cursor.execute(
            "SELECT `itemId`,`quantity` FROM `char_inventory` WHERE `charid`=%s AND `location`=0 AND `slot`=%s LIMIT 1",
            (current["seller_id"], slots.first_free_slot),
        )
        inv = cursor.fetchone()
        if not inv or int(inv[0]) != current["item_id"] or int(inv[1]) != quantity:
            raise LegacyTestExecutionBlocked("Returned inventory post-state verification failed")
        cursor.execute(f"SELECT 1 FROM `auction_house` WHERE `{a['id']}`=%s LIMIT 1", (auction_id,))
        if cursor.fetchone() is not None:
            raise LegacyTestExecutionBlocked("Auction row still exists after return")

        connection.commit()
        return {
            "status": "committed",
            "operation": "return_to_seller",
            "test_only": True,
            "auction_id": auction_id,
            "seller_id": current["seller_id"],
            "seller_name": seller.get("char_name"),
            "item_id": current["item_id"],
            "item_name": item.get("name"),
            "stack": current["stack"],
            "quantity": quantity,
            "asking_price": current["asking_price"],
            "return_location": 0,
            "return_slot": slots.first_free_slot,
            "listing_fee_refunded": 0,
            "note": "Native legacy cancellation returns the item but does not refund the original listing fee.",
        }
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
