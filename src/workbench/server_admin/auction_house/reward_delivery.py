"""Preview-bound DSP/Topaz Test reward delivery through the legacy Mog delivery box."""
from __future__ import annotations

from hashlib import sha256
import json
from typing import Any
from uuid import uuid4

from .audit_ledger import ReplayAlreadyConsumed, claim_replay_once
from .legacy_test_executor import LegacyTestExecutionBlocked, evaluate_legacy_test_write_gate
from .reward_templates import normalize_items
from .safe_return import _delivery_columns, _table_engines, _transactional
from .write_probe import probe_write_readiness

_MAX_RECIPIENTS = 5000
_MAX_DELIVERY_ROWS = 50000
_SENDER = "AH-Admin Reward"
_REQUIRED_DELIVERY_COLUMNS = {
    "charid", "charname", "box", "slot", "itemid", "itemsubid", "quantity",
    "extra", "senderid", "sender", "received", "sent",
}


def _char_columns(connection) -> tuple[str, str]:
    cursor = connection.cursor()
    try:
        cursor.execute("DESCRIBE `chars`")
        columns = {str(row[0]) for row in (cursor.fetchall() or [])}
    finally:
        cursor.close()
    id_col = next((name for name in ("charid", "charId", "char_id", "id") if name in columns), None)
    name_col = next((name for name in ("charname", "charName", "char_name", "name") if name in columns), None)
    if not id_col or not name_col:
        raise LegacyTestExecutionBlocked("chars schema does not expose a verified character ID/name pair")
    return id_col, name_col


def _resolve_recipients(service, *, mode: str, character_ids: list[int] | None) -> list[dict[str, Any]]:
    mode = str(mode or "").strip().lower()
    if mode not in {"selected", "all", "account"}:
        raise LegacyTestExecutionBlocked("recipient mode must be selected, all, or account")
    id_col, name_col = _char_columns(service.connection)
    cursor = service.connection.cursor()
    try:
        if mode == "all":
            cursor.execute(
                f"SELECT `{id_col}`,`{name_col}` FROM `chars` WHERE `{id_col}`>0 "
                f"ORDER BY `{id_col}` ASC LIMIT %s",
                (_MAX_RECIPIENTS + 1,),
            )
        elif mode == "account":
            # One existing character is an account anchor; never accept a client-supplied
            # account ID without first verifying the database relationship.
            anchors = list(character_ids or [])
            if len(anchors) != 1 or int(anchors[0]) <= 0:
                raise LegacyTestExecutionBlocked("Account mode requires exactly one positive anchor character ID")
            cursor.execute("DESCRIBE `chars`")
            cols = {str(row[0]) for row in (cursor.fetchall() or [])}
            acc_col = next((name for name in ("accid", "account_id", "accountId") if name in cols), None)
            if not acc_col:
                raise LegacyTestExecutionBlocked("Account-linked recipient selection is not verified for this chars schema")
            cursor.execute(
                f"SELECT `{acc_col}` FROM `chars` WHERE `{id_col}`=%s",
                (int(anchors[0]),),
            )
            anchor = cursor.fetchone()
            if not anchor or anchor[0] is None or int(anchor[0]) <= 0:
                raise LegacyTestExecutionBlocked("Anchor character has no verified account linkage")
            cursor.execute(
                f"SELECT `{id_col}`,`{name_col}` FROM `chars` "
                f"WHERE `{acc_col}`=%s AND `{id_col}`>0 "
                f"ORDER BY `{id_col}` ASC LIMIT %s",
                (int(anchor[0]), _MAX_RECIPIENTS + 1),
            )
        else:
            ids = sorted({int(value) for value in (character_ids or []) if int(value) > 0})
            if not ids:
                raise LegacyTestExecutionBlocked("At least one recipient character ID is required")
            if len(ids) > _MAX_RECIPIENTS:
                raise LegacyTestExecutionBlocked(f"Recipient selection exceeds {_MAX_RECIPIENTS} characters")
            placeholders = ",".join(["%s"] * len(ids))
            cursor.execute(
                f"SELECT `{id_col}`,`{name_col}` FROM `chars` WHERE `{id_col}` IN ({placeholders}) "
                f"ORDER BY `{id_col}` ASC",
                tuple(ids),
            )
        rows = [{"char_id": int(row[0]), "char_name": str(row[1] or "")} for row in (cursor.fetchall() or [])]
    finally:
        cursor.close()
    if mode in {"all", "account"} and len(rows) > _MAX_RECIPIENTS:
        raise LegacyTestExecutionBlocked(
            f"All-character delivery exceeds the {_MAX_RECIPIENTS}-recipient safety limit; use selected batches"
        )
    if mode == "selected":
        expected = sorted({int(value) for value in (character_ids or []) if int(value) > 0})
        found = [row["char_id"] for row in rows]
        missing = sorted(set(expected) - set(found))
        if missing:
            raise LegacyTestExecutionBlocked(f"Recipient character IDs were not found: {missing[:20]}")
    if not rows:
        raise LegacyTestExecutionBlocked("No recipient characters matched the request")
    if any(not row["char_name"] for row in rows):
        raise LegacyTestExecutionBlocked("A recipient character has no resolvable name")
    return rows


GIL_ITEM_ID = 65535
GIL_MAX_PER_ROW = 999_999_999


def _resolve_items(service, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized = normalize_items(items)
    resolved: list[dict[str, Any]] = []
    for entry in normalized:
        if entry["item_id"] == GIL_ITEM_ID:
            # DSP maps itemid 65535 to CItemCurrency; charutils::AddItem credits it as gil on take.
            quantity = int(entry["quantity"])
            if quantity > GIL_MAX_PER_ROW:
                raise LegacyTestExecutionBlocked(f"Gil amount {quantity} exceeds the {GIL_MAX_PER_ROW} per-row limit")
            resolved.append({"item_id": GIL_ITEM_ID, "item_name": "Gil", "quantity": quantity,
                             "stack_size": GIL_MAX_PER_ROW})
            continue
        item = service.item_snapshot(entry["item_id"])
        if not item:
            raise LegacyTestExecutionBlocked(f"Reward item {entry['item_id']} does not exist")
        quantity = int(entry["quantity"])
        stack_size = max(1, int(item.get("stack_size") or 1))
        if quantity > stack_size:
            raise LegacyTestExecutionBlocked(
                f"Reward item {entry['item_id']} quantity {quantity} exceeds stack size {stack_size}"
            )
        resolved.append({
            "item_id": int(item["item_id"]),
            "item_name": str(item.get("name") or ""),
            "quantity": quantity,
            "stack_size": stack_size,
        })
    return resolved


def _fingerprint(*, mode: str, recipients: list[dict[str, Any]], items: list[dict[str, Any]]) -> str:
    material = {
        "mode": str(mode),
        "recipients": [{"char_id": r["char_id"], "char_name": r["char_name"]} for r in recipients],
        "items": [{"item_id": i["item_id"], "quantity": i["quantity"], "stack_size": i["stack_size"]} for i in items],
    }
    canonical = json.dumps(material, sort_keys=True, separators=(",", ":"), default=str)
    return sha256(canonical.encode("utf-8")).hexdigest()


def preview_reward_delivery(*, service, mode: str, character_ids: list[int] | None,
                            items: list[dict[str, Any]]) -> dict[str, Any]:
    recipients = _resolve_recipients(service, mode=mode, character_ids=character_ids)
    resolved_items = _resolve_items(service, items)
    total_rows = len(recipients) * len(resolved_items)
    if total_rows > _MAX_DELIVERY_ROWS:
        raise LegacyTestExecutionBlocked(
            f"Reward delivery would create {total_rows} rows, exceeding the {_MAX_DELIVERY_ROWS}-row safety limit"
        )
    preview_id = str(uuid4())
    replay_id = str(uuid4())
    return {
        "status": "preview",
        "operation": "reward_delivery",
        "recipient_mode": str(mode).strip().lower(),
        "recipient_count": len(recipients),
        "recipients": recipients,
        "item_count": len(resolved_items),
        "items": resolved_items,
        "delivery_rows": total_rows,
        "preview_id": preview_id,
        "replay_id": replay_id,
        "preview_token": _fingerprint(mode=mode, recipients=recipients, items=resolved_items),
        "max_recipients": _MAX_RECIPIENTS,
        "max_delivery_rows": _MAX_DELIVERY_ROWS,
        "note": "Preview only. Execution re-resolves recipients/items and consumes replay_id once before delivery.",
    }


def _validate_delivery_write_path(service) -> None:
    engines = _table_engines(service.connection, ("delivery_box",))
    if not _transactional(engines, "delivery_box"):
        raise LegacyTestExecutionBlocked("Reward delivery requires a transactional delivery_box table")
    readiness = probe_write_readiness(service.connection)
    if "delivery_box_insert" not in set(readiness.triggers):
        raise LegacyTestExecutionBlocked("delivery_box_insert trigger is required for reward delivery")
    if not _REQUIRED_DELIVERY_COLUMNS.issubset(_delivery_columns(service.connection)):
        raise LegacyTestExecutionBlocked("delivery_box schema does not match the verified DSP/Topaz delivery contract")


def _deliver_one(service, recipient: dict[str, Any], items: list[dict[str, Any]]) -> dict[str, Any]:
    connection = service.connection
    cursor = connection.cursor()
    char_id = int(recipient["char_id"])
    char_name = str(recipient["char_name"])
    try:
        cursor.execute("START TRANSACTION")
        cursor.execute(
            "SELECT COUNT(*) FROM `delivery_box` WHERE `charid`=%s AND `box`=1 AND `sender`=%s",
            (char_id, _SENDER),
        )
        before = int((cursor.fetchone() or (0,))[0] or 0)
        for item in items:
            cursor.execute(
                "INSERT INTO `delivery_box` "
                "(`charid`,`charname`,`box`,`slot`,`itemid`,`itemsubid`,`quantity`,`extra`,`senderid`,`sender`,`received`,`sent`) "
                "VALUES (%s,%s,1,0,%s,0,%s,NULL,0,%s,0,0)",
                (char_id, char_name, int(item["item_id"]), int(item["quantity"]), _SENDER),
            )
            if int(getattr(cursor, "rowcount", 0) or 0) != 1:
                raise LegacyTestExecutionBlocked("Reward delivery insert did not create exactly one delivery row")
        cursor.execute(
            "SELECT COUNT(*) FROM `delivery_box` WHERE `charid`=%s AND `box`=1 AND `sender`=%s",
            (char_id, _SENDER),
        )
        after = int((cursor.fetchone() or (0,))[0] or 0)
        if after != before + len(items):
            raise LegacyTestExecutionBlocked("Reward delivery post-state verification failed")
        connection.commit()
        return {"char_id": char_id, "char_name": char_name, "status": "committed", "rows": len(items)}
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()


def execute_reward_delivery(*, service, environment: dict[str, Any], mode: str,
                            character_ids: list[int] | None, items: list[dict[str, Any]],
                            preview_token: str, preview_id: str, replay_id: str,
                            confirmation: str, feature_enabled: bool | None = None) -> dict[str, Any]:
    gate = evaluate_legacy_test_write_gate(
        environment=environment,
        schema_family_hint=service.schema.family_hint,
        confirmation=confirmation,
        feature_enabled=feature_enabled,
    )
    if not gate.ready:
        codes = ", ".join(issue.code for issue in gate.issues if issue.blocking)
        raise LegacyTestExecutionBlocked(f"Auction House legacy TEST execution blocked: {codes}")
    _validate_delivery_write_path(service)
    recipients = _resolve_recipients(service, mode=mode, character_ids=character_ids)
    resolved_items = _resolve_items(service, items)
    total_rows = len(recipients) * len(resolved_items)
    if total_rows > _MAX_DELIVERY_ROWS:
        raise LegacyTestExecutionBlocked("Reward delivery exceeds the row safety limit")
    live_token = _fingerprint(mode=mode, recipients=recipients, items=resolved_items)
    if not preview_token or live_token != str(preview_token):
        raise LegacyTestExecutionBlocked("Reward preview is stale; preview the exact recipients and items again")
    if not str(preview_id or "").strip() or not str(replay_id or "").strip():
        raise LegacyTestExecutionBlocked("preview_id and replay_id from a fresh preview are required")
    try:
        claim_replay_once(
            replay_id=str(replay_id), audit_id=f"reward:{preview_id}", preview_id=str(preview_id),
            executor_ref="auction_house.reward_delivery",
        )
    except ReplayAlreadyConsumed as exc:
        raise LegacyTestExecutionBlocked("This reward preview has already been executed or claimed") from exc

    results: list[dict[str, Any]] = []
    committed = 0
    failed = 0
    for recipient in recipients:
        try:
            result = _deliver_one(service, recipient, resolved_items)
            committed += 1
            results.append(result)
        except Exception as exc:
            failed += 1
            results.append({
                "char_id": int(recipient["char_id"]), "char_name": str(recipient["char_name"]),
                "status": "failed", "error": str(exc),
            })
    return {
        "status": "completed" if failed == 0 else ("failed" if committed == 0 else "partial"),
        "operation": "reward_delivery",
        "test_only": True,
        "recipient_mode": str(mode).strip().lower(),
        "recipient_count": len(recipients),
        "item_count": len(resolved_items),
        "attempted_recipients": committed + failed,
        "committed_recipients": committed,
        "failed_recipients": failed,
        "committed_delivery_rows": committed * len(resolved_items),
        "preview_token": live_token,
        "preview_id": str(preview_id),
        "replay_id": str(replay_id),
        "partial_success_possible": True,
        "results": results,
    }
