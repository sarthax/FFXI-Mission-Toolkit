"""Guarded audit restore for LSB administrative/history edits.

This is intentionally separate from the portable Character Editor undo dispatcher because
``char_flags`` and ``char_history`` are LSB-specific contracts.  Restore only the columns changed
by the original edit; unrelated counters/flags are never overwritten by an undo.
"""
from __future__ import annotations

from typing import Any

from .audit import attach_committed_audit, get_audit_event, load_audit_backup
from .audit_undo import UndoIssue, UndoPlan, _already_undone, _plain
from .lsb_admin_transactions import _ALLOWED, _REQUIRED, _row
from .schema import discover_character_schema
from .session_state import detect_online_state


def _invalid(event_id: str, adapter_family: str, code: str, message: str) -> UndoPlan:
    return UndoPlan(str(event_id or ""), 0, "", str(adapter_family or "unknown"), {}, None, None, None,
                    [UndoIssue(code, message)])


def build_lsb_admin_undo_plan(connection, *, event_id: str, adapter_family: str) -> UndoPlan:
    event = get_audit_event(event_id)
    if event is None:
        return _invalid(event_id, adapter_family, "event_missing", "Audit event was not found.")

    char_id = int(event.get("char_id") or 0)
    operation = str(event.get("operation") or "")
    event_family = str(event.get("adapter_family") or "unknown").lower()
    current_family = str(adapter_family or "unknown").lower()
    target = dict(event.get("target") or {})
    after = _plain(event.get("after"))
    issues: list[UndoIssue] = []
    try:
        before = _plain(load_audit_backup(event))
    except Exception as exc:
        before = None
        issues.append(UndoIssue("backup_unavailable", str(exc)))

    if operation != "lsb_admin.update":
        issues.append(UndoIssue("operation_not_supported", f"LSB admin undo cannot restore {operation or 'this operation'}."))
    if not bool(event.get("undo_supported")):
        issues.append(UndoIssue("undo_not_supported", "This audit event is history-only and is not marked undo-capable."))
    if event_family != "lsb" or current_family != "lsb":
        issues.append(UndoIssue("lsb_only", "LSB administrative audit restore requires an active LandSandBoat environment."))
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

    table = str(target.get("table") or "")
    changes = dict((event.get("metadata") or {}).get("changes") or {})
    table_info = schema.table(table) if table in _ALLOWED else None
    if table not in _ALLOWED or table_info is None or not _REQUIRED.get(table, set()).issubset(table_info.column_names):
        issues.append(UndoIssue("schema_unverified", "The audited LSB administrative table no longer matches the verified schema."))
    elif not isinstance(before, dict) or not isinstance(after, dict) or not changes:
        issues.append(UndoIssue("audit_shape_invalid", "LSB administrative audit backup or change metadata is incomplete."))
    elif any(name not in _ALLOWED[table] for name in changes):
        issues.append(UndoIssue("audit_shape_invalid", "LSB administrative audit contains a field outside the verified edit allowlist."))
    elif not any(issue.blocking for issue in issues):
        current = _row(connection, char_id, table)
        if _plain(current) != after:
            issues.append(UndoIssue("after_state_drift", "Administrative state no longer matches the audited after-state."))

    return UndoPlan(str(event.get("event_id") or ""), char_id, operation, event_family, target, before, after, state.online, issues)


def _restore_lsb_admin(connection, plan: UndoPlan) -> None:
    event = get_audit_event(plan.event_id) or {}
    table = str(plan.target.get("table") or "")
    changes = dict((event.get("metadata") or {}).get("changes") or {})
    schema = discover_character_schema(connection)
    table_info = schema.table(table) if table in _ALLOWED else None
    if (
        table not in _ALLOWED
        or table_info is None
        or not _REQUIRED.get(table, set()).issubset(table_info.column_names)
        or not isinstance(plan.before, dict)
        or not changes
        or any(name not in _ALLOWED[table] for name in changes)
    ):
        raise RuntimeError("LSB administrative audit metadata is incomplete or no longer schema-safe")

    assignments = ", ".join(f"`{name}` = %s" for name in changes)
    params = [plan.before.get(name) for name in changes] + [plan.char_id]
    cursor = connection.cursor()
    try:
        cursor.execute(f"UPDATE `{table}` SET {assignments} WHERE `charid` = %s LIMIT 1", tuple(params))
        if getattr(cursor, "rowcount", 1) not in (0, 1):
            raise RuntimeError("LSB administrative undo changed an unexpected number of rows")
    finally:
        cursor.close()


def apply_lsb_admin_undo(connection, *, event_id: str, adapter_family: str, approved: bool = False) -> dict[str, Any]:
    if not approved:
        raise PermissionError("Explicit approval is required to undo an LSB administrative audit event")
    try:
        if hasattr(connection, "start_transaction"):
            connection.start_transaction()
        else:
            cursor = connection.cursor(); cursor.execute("START TRANSACTION"); cursor.close()

        plan = build_lsb_admin_undo_plan(connection, event_id=event_id, adapter_family=adapter_family)
        if not plan.ready:
            messages = "; ".join(issue.message for issue in plan.issues if issue.blocking)
            raise RuntimeError(messages or "LSB administrative audit event is not undo-ready")
        _restore_lsb_admin(connection, plan)
        connection.commit()
        result = {"status": "committed", "event_id": plan.event_id, "char_id": plan.char_id, "undid_operation": plan.operation}
        return attach_committed_audit(
            result,
            operation="undo.lsb_admin.update",
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
