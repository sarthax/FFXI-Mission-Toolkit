"""Guarded restore transactions for Character Editor audit events.

Undo is deliberately operation-aware.  The live target must still match the audited after-state,
the character must be verifiably offline, and the connected server lineage must match the event.
Undo actions are themselves appended to audit history but are not automatically redo-capable.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from .audit import attach_committed_audit, get_audit_event, load_audit_backup, read_audit_events
from .inventory_management import _equipped_refs, _inventory_row
from .inventory_slots import CAPACITY_COLUMNS, inspect_slots
from .packed_transactions import _chars_blob
from .scalar_transactions import _row
from .schema import discover_character_schema
from .session_state import detect_online_state

_SUPPORTED_PREFIXES = ("inventory.", "spell.", "blacklist.", "scalar.", "packed.")
_INVENTORY_COLUMNS = ("charid", "location", "slot", "itemId", "quantity", "bazaar", "signature", "extra")


@dataclass(frozen=True)
class UndoIssue:
    code: str
    message: str
    blocking: bool = True


@dataclass
class UndoPlan:
    event_id: str
    char_id: int
    operation: str
    adapter_family: str
    target: dict[str, Any]
    before: Any
    after: Any
    online: bool | None
    issues: list[UndoIssue] = field(default_factory=list)

    @property
    def ready(self) -> bool:
        return bool(self.event_id and self.operation) and not any(issue.blocking for issue in self.issues)

    def as_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "char_id": self.char_id,
            "operation": self.operation,
            "adapter_family": self.adapter_family,
            "target": self.target,
            "before": self.before,
            "after": self.after,
            "online": self.online,
            "issues": [asdict(issue) for issue in self.issues],
            "ready": self.ready,
        }


def _plain(value: Any) -> Any:
    if isinstance(value, memoryview):
        return value.tobytes()
    if isinstance(value, bytearray):
        return bytes(value)
    if isinstance(value, dict):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    return value


def _already_undone(event_id: str, char_id: int) -> bool:
    for row in read_audit_events(char_id=char_id, limit=5000):
        if not str(row.get("operation") or "").startswith("undo."):
            continue
        metadata = row.get("metadata") or {}
        if str(metadata.get("original_event_id") or "") == event_id:
            return True
    return False


def _inventory_checks(connection, schema, event: dict[str, Any], before: Any, after: Any, issues: list[UndoIssue]) -> None:
    operation = str(event.get("operation") or "")
    char_id = int(event["char_id"])
    before = _plain(before)
    after = _plain(after)
    current = None
    if isinstance(after, dict):
        current = _inventory_row(connection, char_id, int(after.get("location") or 0), int(after.get("slot") or 0))
        if _plain(current) != after:
            issues.append(UndoIssue("after_state_drift", "Inventory row no longer matches the audited after-state."))
            return
    elif operation != "inventory.remove":
        issues.append(UndoIssue("audit_shape_invalid", "Inventory audit after-state is invalid."))
        return

    if operation == "inventory.remove":
        if not isinstance(before, dict):
            issues.append(UndoIssue("backup_missing", "Removed inventory row has no restorable before-state."))
            return
        location, slot = int(before.get("location") or 0), int(before.get("slot") or 0)
        if _inventory_row(connection, char_id, location, slot) is not None:
            issues.append(UndoIssue("restore_slot_occupied", "The original inventory slot is now occupied."))
            return
        if location not in CAPACITY_COLUMNS:
            issues.append(UndoIssue("restore_capacity_unverified", "The original container does not expose directly verifiable capacity; automatic restore is blocked."))
            return
        try:
            state = inspect_slots(connection, char_id, location)
        except Exception as exc:
            issues.append(UndoIssue("restore_container_unverified", f"Original container could not be verified: {exc}"))
            return
        if slot < 1 or slot > state.capacity:
            issues.append(UndoIssue("restore_slot_out_of_range", "The original slot is outside the container's current capacity."))
        return

    if not isinstance(after, dict):
        return
    after_location, after_slot = int(after.get("location") or 0), int(after.get("slot") or 0)
    if operation in {"inventory.add", "inventory.move"} and _equipped_refs(connection, schema, char_id, after_location, after_slot):
        issues.append(UndoIssue("item_equipped", "The audited inventory row is currently equipped; unequip it before undo."))
    if operation == "inventory.move" and isinstance(before, dict):
        before_location, before_slot = int(before.get("location") or 0), int(before.get("slot") or 0)
        if (before_location, before_slot) != (after_location, after_slot):
            if _inventory_row(connection, char_id, before_location, before_slot) is not None:
                issues.append(UndoIssue("restore_slot_occupied", "The original inventory slot is now occupied."))
            elif before_location not in CAPACITY_COLUMNS:
                issues.append(UndoIssue("restore_capacity_unverified", "The original container does not expose directly verifiable capacity; automatic restore is blocked."))
            else:
                try:
                    state = inspect_slots(connection, char_id, before_location)
                    if before_slot < 1 or before_slot > state.capacity:
                        issues.append(UndoIssue("restore_slot_out_of_range", "The original slot is outside the container's current capacity."))
                except Exception as exc:
                    issues.append(UndoIssue("restore_container_unverified", f"Original container could not be verified: {exc}"))


def _spell_present(connection, char_id: int, spell_id: int) -> bool:
    cursor = connection.cursor()
    try:
        cursor.execute("SELECT 1 FROM `char_spells` WHERE `charid` = %s AND `spellid` = %s LIMIT 1", (char_id, spell_id))
        return cursor.fetchone() is not None
    finally:
        cursor.close()


def _blacklist_present(connection, char_id: int, target_id: int) -> bool:
    cursor = connection.cursor()
    try:
        cursor.execute("SELECT 1 FROM `char_blacklist` WHERE `charid_owner` = %s AND `charid_target` = %s LIMIT 1", (char_id, target_id))
        return cursor.fetchone() is not None
    finally:
        cursor.close()


def build_undo_plan(connection, *, event_id: str, adapter_family: str) -> UndoPlan:
    event = get_audit_event(event_id)
    issues: list[UndoIssue] = []
    if event is None:
        return UndoPlan(str(event_id or ""), 0, "", str(adapter_family or "unknown"), {}, None, None, None,
                        [UndoIssue("event_missing", "Audit event was not found.")])

    char_id = int(event.get("char_id") or 0)
    operation = str(event.get("operation") or "")
    event_family = str(event.get("adapter_family") or "unknown").lower()
    current_family = str(adapter_family or "unknown").lower()
    target = dict(event.get("target") or {})
    after = _plain(event.get("after"))
    try:
        before = _plain(load_audit_backup(event))
    except Exception as exc:
        before = None
        issues.append(UndoIssue("backup_unavailable", str(exc)))

    if not bool(event.get("undo_supported")):
        issues.append(UndoIssue("undo_not_supported", "This audit event is history-only and is not marked undo-capable."))
    if operation.startswith("undo.") or not operation.startswith(_SUPPORTED_PREFIXES):
        issues.append(UndoIssue("operation_not_supported", f"Undo is not implemented for {operation or 'this operation'}."))
    if event_family != current_family:
        issues.append(UndoIssue("adapter_mismatch", f"Audit event is {event_family}; connected server is {current_family}."))
    if _already_undone(str(event.get("event_id") or ""), char_id):
        issues.append(UndoIssue("already_undone", "This audit event has already been undone."))

    schema = discover_character_schema(connection)
    state = detect_online_state(connection, schema, char_id)
    if state.online is True:
        issues.append(UndoIssue("character_online", "Character is online; audit restore is blocked."))
    elif state.online is None:
        issues.append(UndoIssue("online_state_unknown", "Character online state could not be verified."))

    if not any(issue.blocking for issue in issues):
        if operation.startswith("inventory."):
            _inventory_checks(connection, schema, event, before, after, issues)
        elif operation.startswith("spell."):
            spell_id = int(target.get("spell_id") or (event.get("after") or {}).get("spell_id") or 0)
            expected = bool((event.get("after") or {}).get("learned")) if isinstance(event.get("after"), dict) else None
            if spell_id <= 0 or expected is None:
                issues.append(UndoIssue("audit_shape_invalid", "Spell audit target is incomplete."))
            elif _spell_present(connection, char_id, spell_id) != expected:
                issues.append(UndoIssue("after_state_drift", "Spell learned state no longer matches the audited after-state."))
        elif operation.startswith("blacklist."):
            target_id = int(target.get("target_id") or 0)
            expected = bool((event.get("after") or {}).get("present")) if isinstance(event.get("after"), dict) else None
            if target_id <= 0 or expected is None:
                issues.append(UndoIssue("audit_shape_invalid", "Blacklist audit target is incomplete."))
            elif _blacklist_present(connection, char_id, target_id) != expected:
                issues.append(UndoIssue("after_state_drift", "Blacklist state no longer matches the audited after-state."))
        elif operation == "scalar.update":
            table_name = str(target.get("table") or "")
            selector = dict(target.get("selector") or {})
            current = _row(connection, schema, char_id, table_name, selector)
            if _plain(current) != after:
                issues.append(UndoIssue("after_state_drift", "Scalar row no longer matches the audited after-state."))
        elif operation.startswith("packed."):
            column = str(target.get("column") or "")
            expected_blob = after.get("blob") if isinstance(after, dict) else None
            current = _chars_blob(connection, schema, char_id, column) if column else None
            if not isinstance(expected_blob, bytes) or current != expected_blob:
                issues.append(UndoIssue("after_state_drift", "Packed BLOB no longer matches the audited after-state."))

    return UndoPlan(str(event.get("event_id") or ""), char_id, operation, event_family, target, before, after, state.online, issues)


def _restore_inventory(connection, plan: UndoPlan) -> None:
    before, after = _plain(plan.before), _plain(plan.after)
    cursor = connection.cursor()
    try:
        if before is None and isinstance(after, dict):
            cursor.execute("DELETE FROM `char_inventory` WHERE `charid`=%s AND `location`=%s AND `slot`=%s LIMIT 1",
                           (plan.char_id, int(after["location"]), int(after["slot"])))
        elif isinstance(before, dict) and after is None:
            cursor.execute(
                "INSERT INTO `char_inventory` (`charid`,`location`,`slot`,`itemId`,`quantity`,`bazaar`,`signature`,`extra`) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                tuple(before.get(name) for name in _INVENTORY_COLUMNS),
            )
        elif isinstance(before, dict) and isinstance(after, dict):
            cursor.execute(
                "UPDATE `char_inventory` SET `location`=%s,`slot`=%s,`itemId`=%s,`quantity`=%s,`bazaar`=%s,`signature`=%s,`extra`=%s WHERE `charid`=%s AND `location`=%s AND `slot`=%s LIMIT 1",
                (before["location"], before["slot"], before["itemId"], before["quantity"], before["bazaar"], before["signature"], before["extra"],
                 plan.char_id, after["location"], after["slot"]),
            )
        else:
            raise RuntimeError("Inventory audit state cannot be restored")
        if getattr(cursor, "rowcount", 1) != 1:
            raise RuntimeError("Inventory undo did not change exactly one row")
    finally:
        cursor.close()


def _restore_spell(connection, plan: UndoPlan) -> None:
    spell_id = int(plan.target.get("spell_id") or (plan.after or {}).get("spell_id") or 0)
    before_learned = bool((plan.before or {}).get("learned"))
    cursor = connection.cursor()
    try:
        if before_learned:
            cursor.execute("INSERT INTO `char_spells` (`charid`,`spellid`) VALUES (%s,%s)", (plan.char_id, spell_id))
        else:
            cursor.execute("DELETE FROM `char_spells` WHERE `charid`=%s AND `spellid`=%s LIMIT 1", (plan.char_id, spell_id))
    finally:
        cursor.close()


def _restore_blacklist(connection, plan: UndoPlan) -> None:
    target_id = int(plan.target.get("target_id") or 0)
    before_present = bool((plan.before or {}).get("present"))
    cursor = connection.cursor()
    try:
        if before_present:
            cursor.execute("INSERT INTO `char_blacklist` (`charid_owner`,`charid_target`) VALUES (%s,%s)", (plan.char_id, target_id))
        else:
            cursor.execute("DELETE FROM `char_blacklist` WHERE `charid_owner`=%s AND `charid_target`=%s LIMIT 1", (plan.char_id, target_id))
    finally:
        cursor.close()


def _restore_scalar(connection, plan: UndoPlan, schema) -> None:
    table_name = str(plan.target.get("table") or "")
    selector = dict(plan.target.get("selector") or {})
    event = get_audit_event(plan.event_id) or {}
    changes = dict(event.get("metadata", {}).get("changes") or {})
    table = schema.table(table_name)
    if table is None or table.character_key is None or not changes or not isinstance(plan.before, dict):
        raise RuntimeError("Scalar audit metadata is incomplete")
    assignments = ", ".join(f"`{name}`=%s" for name in changes)
    clauses = [f"`{table.character_key}`=%s"]
    params = [plan.before.get(name) for name in changes] + [plan.char_id]
    for key, value in selector.items():
        clauses.append(f"`{key}`=%s")
        params.append(value)
    cursor = connection.cursor()
    try:
        cursor.execute(f"UPDATE `{table_name}` SET {assignments} WHERE {' AND '.join(clauses)} LIMIT 1", tuple(params))
        if getattr(cursor, "rowcount", 1) not in (0, 1):
            raise RuntimeError("Scalar undo changed an unexpected number of rows")
    finally:
        cursor.close()


def _restore_packed(connection, plan: UndoPlan, schema) -> None:
    column = str(plan.target.get("column") or "")
    before_blob = plan.before.get("blob") if isinstance(plan.before, dict) else None
    table = schema.table("chars")
    if not column or not isinstance(before_blob, bytes) or table is None or table.character_key is None:
        raise RuntimeError("Packed audit backup is incomplete")
    cursor = connection.cursor()
    try:
        cursor.execute(f"UPDATE `chars` SET `{column}`=%s WHERE `{table.character_key}`=%s LIMIT 1", (before_blob, plan.char_id))
        if getattr(cursor, "rowcount", 1) not in (0, 1):
            raise RuntimeError("Packed undo changed an unexpected number of rows")
    finally:
        cursor.close()


def apply_undo(connection, *, event_id: str, adapter_family: str, approved: bool = False) -> dict[str, Any]:
    if not approved:
        raise PermissionError("Explicit approval is required to undo an audit event")
    try:
        if hasattr(connection, "start_transaction"):
            connection.start_transaction()
        else:
            cursor = connection.cursor(); cursor.execute("START TRANSACTION"); cursor.close()

        plan = build_undo_plan(connection, event_id=event_id, adapter_family=adapter_family)
        if not plan.ready:
            messages = "; ".join(issue.message for issue in plan.issues if issue.blocking)
            raise RuntimeError(messages or "Audit event is not undo-ready")
        schema = discover_character_schema(connection)
        if plan.operation.startswith("inventory."):
            _restore_inventory(connection, plan)
        elif plan.operation.startswith("spell."):
            _restore_spell(connection, plan)
        elif plan.operation.startswith("blacklist."):
            _restore_blacklist(connection, plan)
        elif plan.operation == "scalar.update":
            _restore_scalar(connection, plan, schema)
        elif plan.operation.startswith("packed."):
            _restore_packed(connection, plan, schema)
        else:
            raise RuntimeError(f"Undo is not implemented for {plan.operation}")
        connection.commit()
        result = {"status": "committed", "event_id": plan.event_id, "char_id": plan.char_id, "undid_operation": plan.operation}
        return attach_committed_audit(
            result,
            operation=f"undo.{plan.operation}",
            char_id=plan.char_id,
            adapter_family=plan.adapter_family,
            target={"original_event_id": plan.event_id, **plan.target},
            before=plan.after,
            after=plan.before,
            metadata={"original_event_id": plan.event_id},
            undo_supported=False,
        )
    except Exception:
        try:
            connection.rollback()
        finally:
            raise
