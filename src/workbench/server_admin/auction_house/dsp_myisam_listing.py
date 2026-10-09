"""DSP TEST-only stock-MyISAM player listing fallback.

This mirrors Darkstar's native sequential listing semantics while adding table locks,
pre-state capture, post-state verification, and best-effort compensation. It is
intentionally non-atomic and must never be exposed outside named DSP Test profiles.
"""
from __future__ import annotations

import os
import time
from typing import Any

from workbench.editors.character.schema import discover_character_schema
from workbench.runtime import settings_store
from workbench.editors.character.session_state import detect_online_state

from .config_policy import load_active_legacy_policy
from .invariants import legacy_listing_fee
from .legacy_test_executor import LegacyTestExecutionBlocked, evaluate_legacy_test_write_gate
from .recovery_guidance import myisam_recovery_guidance
from .recovery_journal import begin_case, set_case_status
from .player_listing import _GIL_ITEM_ID, probe_player_listing_engines

_MYISAM_FLAG = "FFXI_MISSION_TOOLKIT_AH_DSP_MYISAM_TEST_WRITES"


def dsp_myisam_test_writes_enabled() -> bool:
    env = str(os.getenv(_MYISAM_FLAG, "")).strip()
    if env:
        return env.lower() in {"1", "true", "yes", "on"}
    try:
        return settings_store.get_ah_flag("ah_dsp_myisam_test_writes").lower() in {"1", "true", "yes", "on"}
    except Exception:
        return False


def dsp_myisam_listing_readiness(*, service, environment: dict[str, Any]) -> dict[str, Any]:
    probe = probe_player_listing_engines(service.connection)
    family = str(environment.get("family") or "").strip().lower()
    blockers: list[str] = []
    if family != "dsp":
        blockers.append("dsp_only")
    if not dsp_myisam_test_writes_enabled():
        blockers.append("myisam_feature_flag_disabled")
    if probe.transactional:
        blockers.append("transactional_path_available")
    return {
        "test_only": True,
        "mode": "dsp_myisam_compensating",
        "feature_flag": _MYISAM_FLAG,
        "feature_enabled": dsp_myisam_test_writes_enabled(),
        "engine_probe": probe.as_dict(),
        "ready": not blockers,
        "blockers": blockers,
        "atomic": False,
        "crash_window": True,
        "recovery_guidance": myisam_recovery_guidance("player_listing"),
        "note": (
            "Uses explicit table locks and best-effort compensation to mirror stock DSP MyISAM listing semantics. "
            "A process/database crash between sequential writes can still require manual recovery."
        ),
    }


def execute_dsp_myisam_test_player_listing(
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
    listed_at: int | None = None,
) -> dict[str, Any]:
    gate = evaluate_legacy_test_write_gate(
        environment=environment,
        schema_family_hint=service.schema.family_hint,
        confirmation=confirmation,
    )
    if not gate.ready:
        codes = ", ".join(issue.code for issue in gate.issues if issue.blocking)
        raise LegacyTestExecutionBlocked(f"Auction House legacy TEST execution blocked: {codes}")

    family = str(environment.get("family") or "").strip().lower()
    if family != "dsp":
        raise LegacyTestExecutionBlocked("DSP MyISAM listing fallback is DSP Test-only")
    if not dsp_myisam_test_writes_enabled():
        raise LegacyTestExecutionBlocked(f"Set {_MYISAM_FLAG}=1 to enable the DSP MyISAM Test fallback")

    seller_id = int(seller_id)
    inventory_slot = int(inventory_slot)
    item_id = int(item_id)
    price = int(price)
    stack = bool(stack)
    if seller_id <= 0 or inventory_slot <= 0 or item_id <= 0 or price <= 0:
        raise LegacyTestExecutionBlocked("seller_id, inventory_slot, item_id, and price must be positive")

    probe = probe_player_listing_engines(service.connection)
    if probe.transactional:
        raise LegacyTestExecutionBlocked("Transactional tables are available; use the normal player-listing executor")
    if "char_inventory" not in probe.blocking_tables:
        raise LegacyTestExecutionBlocked("DSP MyISAM fallback is only intended for non-transactional char_inventory")

    policy_load = load_active_legacy_policy(server_root=server_root, family=family)
    if not policy_load.policy_ready or policy_load.policy is None:
        issues = ", ".join(issue.code for issue in policy_load.issues if issue.blocking)
        raise LegacyTestExecutionBlocked(f"Active Auction House policy is not ready: {issues or 'unknown policy error'}")
    policy = policy_load.policy

    seller = service.character_snapshot(seller_id)
    item = service.item_snapshot(item_id)
    if not seller:
        raise LegacyTestExecutionBlocked("Seller character does not exist")
    if not item:
        raise LegacyTestExecutionBlocked("Item metadata could not be verified")
    if int(item.get("category_id") or 0) <= 0:
        raise LegacyTestExecutionBlocked("Item is not assigned to an Auction House category")

    char_schema = discover_character_schema(service.connection)
    session = detect_online_state(service.connection, char_schema, seller_id)
    if session.online is not False:
        raise LegacyTestExecutionBlocked("Seller must be offline before DSP MyISAM administrative listing")

    stack_size = max(1, int(item.get("stack_size") or 1))
    if stack and stack_size <= 1:
        raise LegacyTestExecutionBlocked("Item cannot be listed as a stack")
    required_quantity = stack_size if stack else 1
    fee = legacy_listing_fee(price, stack=stack, policy=policy)

    a = service.schema.auction_columns
    required_columns = ("id", "item_id", "stack", "seller_id", "listed_at", "asking_price", "sale_price", "sold_at")
    if any(not a.get(name) for name in required_columns):
        raise LegacyTestExecutionBlocked("Legacy Auction House schema is missing player-listing columns")

    timestamp = int(listed_at if listed_at is not None else time.time())
    if timestamp <= 0:
        raise LegacyTestExecutionBlocked("listed_at must be positive")

    connection = service.connection
    cursor = connection.cursor()
    journal_case_id: str | None = None
    auction_id: int | None = None
    item_before: tuple[int, int] | None = None
    gil_before: int | None = None
    compensation_attempted = False
    compensation_ok = False
    locked = False
    try:
        cursor.execute("LOCK TABLES `auction_house` WRITE, `char_inventory` WRITE")
        locked = True

        cursor.execute(
            "SELECT `itemId`,`quantity` FROM `char_inventory` WHERE `charid`=%s AND `location`=0 AND `slot`=%s",
            (seller_id, inventory_slot),
        )
        row = cursor.fetchone()
        if not row:
            raise LegacyTestExecutionBlocked("Selected seller Inventory slot is empty")
        item_before = (int(row[0] or 0), int(row[1] or 0))
        if item_before[0] != item_id:
            raise LegacyTestExecutionBlocked("Selected Inventory slot no longer contains the requested item")
        if stack and item_before[1] != stack_size:
            raise LegacyTestExecutionBlocked(f"Stack listing requires exactly one full stack of {stack_size}")
        if not stack and item_before[1] < 1:
            raise LegacyTestExecutionBlocked("Selected Inventory slot has no item quantity available")

        cursor.execute(
            "SELECT `itemId`,`quantity` FROM `char_inventory` WHERE `charid`=%s AND `location`=0 AND `slot`=0",
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

        # Persist a diagnostic case BEFORE the first non-atomic write.
        journal_case_id = begin_case(operation="player_listing", environment=environment, evidence={
            "seller_id": seller_id, "inventory_slot": inventory_slot, "item_id": item_id,
            "item_quantity_before": item_before[1], "gil_before": gil_before,
            "listing_fee": fee, "asking_price": price, "stack": stack,
        })
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

        remaining = item_before[1] - required_quantity
        if remaining == 0:
            cursor.execute(
                "DELETE FROM `char_inventory` WHERE `charid`=%s AND `location`=0 AND `slot`=%s AND `itemId`=%s AND `quantity`=%s",
                (seller_id, inventory_slot, item_id, item_before[1]),
            )
        else:
            cursor.execute(
                "UPDATE `char_inventory` SET `quantity`=%s WHERE `charid`=%s AND `location`=0 AND `slot`=%s AND `itemId`=%s AND `quantity`=%s",
                (remaining, seller_id, inventory_slot, item_id, item_before[1]),
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
            f"SELECT `{a['item_id']}`,`{a['stack']}`,`{a['seller_id']}`,`{a['asking_price']}`,`{a['sale_price']}`,`{a['sold_at']}` FROM `auction_house` WHERE `{a['id']}`=%s",
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

        cursor.execute("UNLOCK TABLES")
        locked = False
        if journal_case_id:
            set_case_status(journal_case_id, "completed_non_atomic", details={"auction_id": auction_id})
        return {
            "status": "committed_non_atomic",
            "operation": "player_listing",
            "execution_mode": "dsp_myisam_compensating",
            "test_only": True,
            "atomic": False,
            "crash_window": True,
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
            "engine_probe": probe.as_dict(),
            "warning": "MyISAM path is not crash-atomic; use on a disposable Test server only.",
        }
    except Exception as original_exc:
        if locked and (auction_id is not None or item_before is not None or gil_before is not None):
            compensation_attempted = True
            try:
                if auction_id is not None:
                    cursor.execute(f"DELETE FROM `auction_house` WHERE `{a['id']}`=%s AND `{a['seller_id']}`=%s", (auction_id, seller_id))
                if item_before is not None:
                    cursor.execute(
                        "SELECT `itemId`,`quantity` FROM `char_inventory` WHERE `charid`=%s AND `location`=0 AND `slot`=%s",
                        (seller_id, inventory_slot),
                    )
                    current = cursor.fetchone()
                    if current is None:
                        cursor.execute(
                            "INSERT INTO `char_inventory`(`charid`,`location`,`slot`,`itemId`,`quantity`) VALUES(%s,0,%s,%s,%s)",
                            (seller_id, inventory_slot, item_before[0], item_before[1]),
                        )
                    else:
                        cursor.execute(
                            "UPDATE `char_inventory` SET `itemId`=%s,`quantity`=%s WHERE `charid`=%s AND `location`=0 AND `slot`=%s",
                            (item_before[0], item_before[1], seller_id, inventory_slot),
                        )
                if gil_before is not None:
                    cursor.execute(
                        "UPDATE `char_inventory` SET `quantity`=%s WHERE `charid`=%s AND `location`=0 AND `slot`=0 AND `itemId`=%s",
                        (gil_before, seller_id, _GIL_ITEM_ID),
                    )
                compensation_ok = True
            except Exception:
                compensation_ok = False
        if journal_case_id:
            try:
                set_case_status(
                    journal_case_id,
                    "compensated" if compensation_attempted and compensation_ok else "recovery_required",
                    details={"auction_id": auction_id, "compensation_attempted": compensation_attempted,
                             "compensation_ok": compensation_ok, "error": str(original_exc)[:500]},
                )
            except Exception:
                # Leave the persistent case unresolved for operator inspection.
                pass
        if compensation_attempted and not compensation_ok:
            raise LegacyTestExecutionBlocked(
                f"DSP MyISAM listing failed and automatic compensation also failed; inspect seller {seller_id} and auction row {auction_id}: {original_exc}"
            ) from original_exc
        raise
    finally:
        if locked:
            try:
                cursor.execute("UNLOCK TABLES")
            except Exception:
                pass
        cursor.close()
