"""EXPERIMENTAL DSP TEST-only delivery of one augmented item to one recipient.

The ordinary rewards endpoint must never decode custom fields as plain items.
This separate path requires source-verified mailbox extra behavior, an opt-in
flag, the standard named Test gate, preview binding, replay claim, and a durable
per-recipient journal. In-game pickup still requires operator acceptance.
"""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from uuid import uuid4

from .audit_ledger import ReplayAlreadyConsumed, claim_replay_once
from .augmented_rewards import inspect_augmented_reward
from .legacy_test_executor import LegacyTestExecutionBlocked, evaluate_legacy_test_write_gate
from .reward_attempt_journal import begin_attempt, mark_recipient, finish_attempt
from .reward_delivery import (
    _resolve_recipients, _validate_delivery_write_path, RewardDeliveryUncertain,
)

_FLAG = "FFXI_MISSION_TOOLKIT_AH_AUGMENTED_REWARD_TEST_WRITES"
_SENDER = "AH-Aug Reward"  # delivery_box.sender is varchar(15) on DSP


def augmented_test_writes_enabled() -> bool:
    from workbench.runtime import settings_store
    return settings_store.get_ah_flag("ah_augmented_reward_test_writes").strip().lower() in {"1", "true", "yes", "on"}


def _verify_dsp_mail_source(server_root) -> None:
    """Check this *selected* DSP source tree for the relevant exact item-extra route."""
    file = Path(server_root) / "src" / "map" / "packet_system.cpp"
    try:
        source = file.read_text(encoding="utf-8", errors="replace")
    except (OSError, TypeError) as exc:
        raise LegacyTestExecutionBlocked("DSP mailbox source is unavailable; augmented writes disabled") from exc
    markers = (
        "FROM delivery_box WHERE charid",
        "memcpy(PItem->m_extra, extra",
        "charutils::AddItem(PChar, LOC_INVENTORY, itemutils::GetItem(PItem)",
    )
    if any(marker not in source for marker in markers):
        raise LegacyTestExecutionBlocked("DSP mailbox extra-to-inventory transfer is not source verified")


def preview_augmented_delivery(*, service, environment: dict,
                               server_root, character_id: int, item_id: int,
                               augments: list[dict]) -> dict:
    if str(environment.get("family") or "").lower() != "dsp":
        raise LegacyTestExecutionBlocked("Experimental augmented Mog delivery is DSP-only")
    _verify_dsp_mail_source(server_root)
    recipients = _resolve_recipients(service, mode="selected", character_ids=[int(character_id)])
    if len(recipients) != 1:
        raise LegacyTestExecutionBlocked("Exactly one recipient is required")
    item = service.item_snapshot(int(item_id))
    if not item:
        raise LegacyTestExecutionBlocked("Selected augmented item does not exist")
    if int(item.get("stack_size") or 1) != 1:
        raise LegacyTestExecutionBlocked("Augmented delivery requires a nonstacking item")
    encoded = inspect_augmented_reward(
        family="dsp", server_root=server_root, item_id=int(item_id), augments=augments,
    )
    # Bind EXACT byte payload and exact recipient identity; ordinary preview
    # tokens are not interchangeable with augmented preview tokens.
    material = (
        str(recipients[0]["char_id"]) + ":" + recipients[0]["char_name"] + ":" +
        str(int(item_id)) + ":" + encoded["encoded_inventory_extra_hex"]
    )
    return {
        "status": "preview",
        "test_only": True,
        "write_feature_enabled": augmented_test_writes_enabled(),
        "recipient": recipients[0],
        "item_id": int(item_id),
        "item_name": str(item.get("name") or ""),
        "quantity": 1,
        "augments": encoded["requested_augments"],
        "encoded_extra_hex": encoded["encoded_inventory_extra_hex"],
        "preview_token": sha256(material.encode("utf-8")).hexdigest(),
        "preview_id": str(uuid4()),
        "replay_id": str(uuid4()),
        "note": "DSP Test only. Mailbox pickup persistence still requires in-game verification.",
    }


def execute_augmented_delivery(*, service, environment: dict, server_root,
                               character_id: int, item_id: int, augments: list[dict],
                               preview_token: str, preview_id: str, replay_id: str,
                               confirmation: str) -> dict:
    gate = evaluate_legacy_test_write_gate(
        environment=environment,
        schema_family_hint=service.schema.family_hint,
        confirmation=confirmation,
    )
    if not gate.ready or not augmented_test_writes_enabled():
        raise LegacyTestExecutionBlocked(
            "Augmented reward delivery requires the named DSP Test write gate and explicit experimental opt-in"
        )
    _validate_delivery_write_path(service)
    fresh = preview_augmented_delivery(
        service=service, environment=environment, server_root=server_root,
        character_id=character_id, item_id=item_id, augments=augments,
    )
    if not preview_token or preview_token != fresh["preview_token"]:
        raise LegacyTestExecutionBlocked("Augmented item or recipient changed; preview again")
    if not str(preview_id or "").strip() or not str(replay_id or "").strip():
        raise LegacyTestExecutionBlocked("Fresh preview and replay IDs are required")
    blob = bytes.fromhex(fresh["encoded_extra_hex"])
    if len(blob) != 24:
        raise LegacyTestExecutionBlocked("Invalid augmented item-extra length")
    char = fresh["recipient"]
    connection = service.connection
    try:
        claim_replay_once(
            replay_id=str(replay_id), audit_id=f"augmented-reward:{preview_id}",
            preview_id=str(preview_id), executor_ref="auction_house.augmented_delivery",
        )
    except ReplayAlreadyConsumed as exc:
        raise LegacyTestExecutionBlocked("Augmented reward replay already used") from exc
    begin_attempt(
        replay_id=str(replay_id), preview_id=str(preview_id),
        environment=environment,
        items=[{"item_id": int(item_id), "quantity": 1, "augments": augments}],
        recipients=[char],
    )
    mark_recipient(str(replay_id), int(char["char_id"]), "in_flight")
    cursor = connection.cursor()
    committed = False
    try:
        cursor.execute("START TRANSACTION")
        sql = (
            "SELECT COUNT(*) FROM delivery_box WHERE charid=%s AND box=1 "
            "AND itemid=%s AND sender=%s AND extra=%s"
        )
        params = (int(char["char_id"]), int(item_id), _SENDER, blob)
        cursor.execute(sql, params)
        before = int((cursor.fetchone() or (0,))[0] or 0)
        cursor.execute(
            "INSERT INTO delivery_box "
            "(charid,charname,box,slot,itemid,itemsubid,quantity,extra,senderid,sender,received,sent) "
            "VALUES (%s,%s,1,0,%s,0,1,%s,0,%s,0,0)",
            (int(char["char_id"]), str(char["char_name"]), int(item_id), blob, _SENDER),
        )
        if int(cursor.rowcount or 0) != 1:
            raise LegacyTestExecutionBlocked("Augmented delivery did not insert one mail row")
        cursor.execute(sql, params)
        after = int((cursor.fetchone() or (0,))[0] or 0)
        if after != before + 1:
            raise LegacyTestExecutionBlocked("Encoded item-extra readback did not match")
        connection.commit()
        committed = True
        # This can fail after the game commit; leave in_flight for human review,
        # never compensate a successful game write from the local SQLite error.
        mark_recipient(str(replay_id), int(char["char_id"]), "committed")
        finish_attempt(str(replay_id))
        return {
            "status": "completed", "test_only": True,
            "operation": "augmented_reward_delivery",
            "recipient": char, "item_id": int(item_id),
            "encoded_extra_hex": blob.hex(),
            "replay_id": str(replay_id),
            "pickup_verified": False,
            "warning": "Inspect actual DSP Mog pickup and character Inventory augments before wider use.",
        }
    except Exception as exc:
        if committed:
            raise RewardDeliveryUncertain(
                "Game mail committed but local journal completion is unverified; inspect replay " + str(replay_id)
            ) from exc
        try:
            connection.rollback()
        except Exception as rollback_exc:
            raise RewardDeliveryUncertain(
                "Augmented mail rollback failed; inspect the in-flight delivery case"
            ) from rollback_exc
        mark_recipient(str(replay_id), int(char["char_id"]), "failed", str(exc))
        finish_attempt(str(replay_id))
        raise
    finally:
        cursor.close()
