"""DSP TEST-only stock-MyISAM player purchase fallback.

On stock DSP only ``char_inventory`` is MyISAM; ``auction_house`` and ``delivery_box`` are InnoDB.
This executor therefore claims the exact AH row (and lets the ``auction_house_buy`` /
``delivery_box_insert`` triggers queue the seller settlement) inside a real InnoDB transaction, performs
the two non-transactional buyer writes (gil debit, item grant) with guarded statements, verifies the
whole post-state, and only then commits. On any ordinary failure the transaction is rolled back and the
buyer's gil/item writes are compensated. A crash between the MyISAM writes and the commit can still leave
the buyer charged without the AH row being claimed, so the result reports ``atomic=false``.
"""
from __future__ import annotations

import time
from typing import Any

from workbench.editors.character.adapters.inventory import build_basic_insert_plan, inspect_inventory_contract
from workbench.editors.character.inventory_slots import inspect_slots
from workbench.editors.character.schema import discover_character_schema
from workbench.editors.character.session_state import detect_online_state

from .dsp_myisam_listing import _MYISAM_FLAG, dsp_myisam_test_writes_enabled
from .legacy_test_executor import LegacyTestExecutionBlocked, evaluate_legacy_test_write_gate
from .player_purchase import _GIL_ITEM_ID, _delivery_columns, probe_player_purchase_engines
from .write_probe import probe_write_readiness


def dsp_myisam_purchase_readiness(*, service, environment: dict[str, Any]) -> dict[str, Any]:
    probe = probe_player_purchase_engines(service.connection)
    family = str(environment.get("family") or "").strip().lower()
    blockers: list[str] = []
    if family != "dsp":
        blockers.append("dsp_only")
    if not dsp_myisam_test_writes_enabled():
        blockers.append("myisam_feature_flag_disabled")
    if probe.transactional:
        blockers.append("transactional_path_available")
    if set(probe.blocking_tables) - {"char_inventory"}:
        blockers.append("unexpected_non_transactional_tables")
    return {
        "test_only": True,
        "mode": "dsp_myisam_compensating_purchase",
        "feature_flag": _MYISAM_FLAG,
        "feature_enabled": dsp_myisam_test_writes_enabled(),
        "engine_probe": probe.as_dict(),
        "ready": not blockers,
        "blockers": blockers,
        "atomic": False,
        "crash_window": True,
    }


def execute_dsp_myisam_test_player_purchase(
    *,
    service,
    environment: dict[str, Any],
    auction_id: int,
    expected_price: int,
    buyer_id: int,
    confirmation: str,
    sold_at: int | None = None,
) -> dict[str, Any]:
    gate = evaluate_legacy_test_write_gate(
        environment=environment,
        schema_family_hint=service.schema.family_hint,
        confirmation=confirmation,
    )
    if not gate.ready:
        codes = ", ".join(issue.code for issue in gate.issues if issue.blocking)
        raise LegacyTestExecutionBlocked(f"Auction House legacy TEST execution blocked: {codes}")
    if str(environment.get("family") or "").strip().lower() != "dsp":
        raise LegacyTestExecutionBlocked("DSP MyISAM purchase fallback is DSP Test-only")
    if not dsp_myisam_test_writes_enabled():
        raise LegacyTestExecutionBlocked(f"Set {_MYISAM_FLAG}=1 to enable the DSP MyISAM Test fallback")

    auction_id, expected_price, buyer_id = int(auction_id), int(expected_price), int(buyer_id)
    if auction_id <= 0 or expected_price <= 0 or buyer_id <= 0:
        raise LegacyTestExecutionBlocked("auction_id, expected_price, and buyer_id must be positive")

    engine_probe = probe_player_purchase_engines(service.connection)
    if engine_probe.transactional:
        raise LegacyTestExecutionBlocked("Transactional tables are available; use the normal player-purchase executor")
    if set(engine_probe.blocking_tables) != {"char_inventory"}:
        raise LegacyTestExecutionBlocked(
            "DSP MyISAM purchase fallback requires auction_house and delivery_box to be transactional "
            f"and only char_inventory non-transactional; blocking: {', '.join(engine_probe.blocking_tables)}"
        )
    if not probe_write_readiness(service.connection).legacy_purchase_prerequisites_present:
        raise LegacyTestExecutionBlocked("Legacy purchase settlement prerequisites are missing")

    a = service.schema.auction_columns
    required = ("id", "item_id", "stack", "seller_id", "seller_name", "asking_price", "buyer_name", "sale_price", "sold_at")
    if any(not a.get(name) for name in required):
        raise LegacyTestExecutionBlocked("Legacy Auction House schema is missing player-purchase columns")

    char_schema = discover_character_schema(service.connection)
    contract = inspect_inventory_contract(char_schema, "dsp")
    if not contract.basic_insert_verified:
        raise LegacyTestExecutionBlocked("Buyer inventory schema is not verified for direct purchase")
    if detect_online_state(service.connection, char_schema, buyer_id).online is not False:
        raise LegacyTestExecutionBlocked("Buyer must be offline before an administrative player purchase")
    buyer = service.character_snapshot(buyer_id)
    if not buyer:
        raise LegacyTestExecutionBlocked("Buyer character does not exist")
    slots = inspect_slots(service.connection, buyer_id, 0)
    if slots.first_free_slot is None:
        raise LegacyTestExecutionBlocked("Buyer Inventory is full")
    if not {"charid", "box", "itemid", "quantity", "sender"}.issubset(_delivery_columns(service.connection)):
        raise LegacyTestExecutionBlocked("delivery_box schema cannot verify seller settlement")

    timestamp = int(sold_at if sold_at is not None else time.time())
    if timestamp <= 0:
        raise LegacyTestExecutionBlocked("sold_at must be positive")
    buyer_name = str(buyer.get("char_name") or "")
    free_slot = int(slots.first_free_slot)

    connection = service.connection
    cursor = connection.cursor()
    gil_before: int | None = None
    gil_debited = False
    item_inserted = False
    in_txn = False
    try:
        cursor.execute("START TRANSACTION")
        in_txn = True
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
        item_id, seller_id = int(item_id), int(seller_id or 0)
        asking_price, sale_price, old_sold_at = int(asking_price or 0), int(sale_price or 0), int(old_sold_at or 0)
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

        cursor.execute(
            "SELECT `itemId`,`quantity` FROM `char_inventory` WHERE `charid`=%s AND `location`=0 AND `slot`=0",
            (buyer_id,),
        )
        gil_row = cursor.fetchone()
        if not gil_row or int(gil_row[0] or 0) != _GIL_ITEM_ID:
            raise LegacyTestExecutionBlocked("Buyer gil row is missing or malformed")
        gil_before = int(gil_row[1] or 0)
        if gil_before < asking_price:
            raise LegacyTestExecutionBlocked("Buyer does not have enough gil")
        cursor.execute(
            "SELECT `itemId` FROM `char_inventory` WHERE `charid`=%s AND `location`=0 AND `slot`=%s",
            (buyer_id, free_slot),
        )
        if cursor.fetchone():
            raise LegacyTestExecutionBlocked("Buyer's free inventory slot was taken; retry")

        settlement_sql = (
            "SELECT COUNT(*) FROM `delivery_box` WHERE `charid`=%s AND `box`=1 "
            "AND `itemid`=%s AND `quantity`=%s AND `sender`='AH-Jeuno'"
        )
        cursor.execute(settlement_sql, (seller_id, item_id, asking_price))
        settlement_before = int((cursor.fetchone() or (0,))[0] or 0)

        # Claim the AH row first (InnoDB, still uncommitted); the buy trigger queues seller settlement.
        cursor.execute(
            f"UPDATE `auction_house` SET `{a['buyer_name']}`=%s,`{a['sale_price']}`=%s,`{a['sold_at']}`=%s "
            f"WHERE `{a['id']}`=%s AND `{a['asking_price']}`=%s AND `{a['sale_price']}`=0 AND `{a['sold_at']}`=0",
            (buyer_name, asking_price, timestamp, auction_id, expected_price),
        )
        if int(getattr(cursor, "rowcount", 0) or 0) != 1:
            raise LegacyTestExecutionBlocked("Player purchase did not claim exactly one active listing")
        cursor.execute(settlement_sql, (seller_id, item_id, asking_price))
        if int((cursor.fetchone() or (0,))[0] or 0) != settlement_before + 1:
            raise LegacyTestExecutionBlocked("Seller settlement was not queued exactly once")

        # Non-transactional buyer writes, each guarded by its expected pre-state.
        cursor.execute(
            "UPDATE `char_inventory` SET `quantity`=%s WHERE `charid`=%s AND `location`=0 AND `slot`=0 "
            "AND `itemId`=%s AND `quantity`=%s",
            (gil_before - asking_price, buyer_id, _GIL_ITEM_ID, gil_before),
        )
        if int(getattr(cursor, "rowcount", 0) or 0) != 1:
            raise LegacyTestExecutionBlocked("Buyer gil changed during purchase")
        gil_debited = True

        insert = build_basic_insert_plan(
            contract, char_id=buyer_id, item_id=item_id, location=0, slot=free_slot, quantity=quantity,
        )
        cursor.execute(insert["sql"], insert["params"])
        if int(getattr(cursor, "rowcount", 0) or 0) != 1:
            raise LegacyTestExecutionBlocked("Buyer item insertion did not affect exactly one row")
        item_inserted = True

        cursor.execute(
            "SELECT `quantity` FROM `char_inventory` WHERE `charid`=%s AND `location`=0 AND `slot`=0 AND `itemId`=%s",
            (buyer_id, _GIL_ITEM_ID),
        )
        final_gil = cursor.fetchone()
        if not final_gil or int(final_gil[0] or 0) != gil_before - asking_price:
            raise LegacyTestExecutionBlocked("Buyer gil post-state verification failed")
        cursor.execute(
            "SELECT `itemId`,`quantity` FROM `char_inventory` WHERE `charid`=%s AND `location`=0 AND `slot`=%s",
            (buyer_id, free_slot),
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
        in_txn = False
        return {
            "status": "committed_non_atomic",
            "operation": "player_purchase",
            "execution_mode": "dsp_myisam_compensating",
            "test_only": True,
            "atomic": False,
            "crash_window": True,
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
            "buyer_gil_after": gil_before - asking_price,
            "buyer_inventory_slot": free_slot,
            "seller_proceeds_queued": asking_price,
            "sold_at": timestamp,
            "engine_probe": engine_probe.as_dict(),
            "warning": "MyISAM path is not crash-atomic; use on a disposable Test server only.",
        }
    except Exception as original_exc:
        compensation_ok = True
        if in_txn:
            try:
                connection.rollback()
            except Exception:
                compensation_ok = False
        try:
            if item_inserted:
                cursor.execute(
                    "DELETE FROM `char_inventory` WHERE `charid`=%s AND `location`=0 AND `slot`=%s AND `itemId`=%s",
                    (buyer_id, free_slot, item_id),
                )
            if gil_debited and gil_before is not None:
                cursor.execute(
                    "UPDATE `char_inventory` SET `quantity`=%s WHERE `charid`=%s AND `location`=0 AND `slot`=0 AND `itemId`=%s",
                    (gil_before, buyer_id, _GIL_ITEM_ID),
                )
        except Exception:
            compensation_ok = False
        if not compensation_ok:
            raise LegacyTestExecutionBlocked(
                f"DSP MyISAM purchase failed and automatic compensation also failed; inspect buyer {buyer_id} "
                f"and auction row {auction_id}: {original_exc}"
            ) from original_exc
        raise
    finally:
        cursor.close()
