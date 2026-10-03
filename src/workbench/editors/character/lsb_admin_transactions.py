"""Guarded LSB-only edits for persistent administrative flags and history counters.

``char_flags`` and ``char_history`` are LSB-era tables and are not treated as a portable
DSP/Topaz contract.  Runtime-only ``disconnecting`` is deliberately excluded.  Effects, recasts,
and pet BLOB/relationship state remain read-only in this slice.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from .audit import attach_committed_audit
from .schema import discover_character_schema
from .session_state import detect_online_state

_FLAG_COLUMNS = {"gmModeEnabled", "gmHiddenEnabled", "muted", "rename"}
_HISTORY_COLUMNS = {
    "enemies_defeated", "times_knocked_out", "mh_entrances", "joined_parties", "joined_alliances",
    "spells_cast", "abilities_used", "ws_used", "items_used", "chats_sent", "npc_interactions",
    "battles_fought", "gm_calls", "distance_travelled",
}
_ALLOWED = {"char_flags": _FLAG_COLUMNS, "char_history": _HISTORY_COLUMNS}
_REQUIRED = {
    "char_flags": {"charid", "disconnecting", "gmModeEnabled", "gmHiddenEnabled", "muted", "rename"},
    "char_history": {"charid", *_HISTORY_COLUMNS},
}


@dataclass(frozen=True)
class LsbAdminIssue:
    code: str
    message: str
    blocking: bool = True


@dataclass
class LsbAdminPlan:
    char_id: int
    table: str
    changes: dict[str, int]
    before: dict[str, Any] | None
    after: dict[str, Any] | None
    online: bool | None
    adapter_family: str
    issues: list[LsbAdminIssue] = field(default_factory=list)

    @property
    def ready(self) -> bool:
        return self.before is not None and self.after is not None and bool(self.changes) and not any(i.blocking for i in self.issues)

    def as_dict(self) -> dict[str, Any]:
        return {
            "char_id": self.char_id, "table": self.table, "changes": self.changes,
            "before": self.before, "after": self.after, "online": self.online,
            "adapter_family": self.adapter_family, "issues": [asdict(i) for i in self.issues],
            "ready": self.ready,
        }


def _row(connection, char_id: int, table: str) -> dict[str, Any] | None:
    cursor = connection.cursor()
    try:
        cursor.execute(f"SELECT * FROM `{table}` WHERE `charid` = %s LIMIT 1", (int(char_id),))
        row = cursor.fetchone()
        if row is None:
            return None
        names = [str(d[0]) for d in cursor.description or ()]
        return dict(zip(names, row))
    finally:
        cursor.close()


def build_lsb_admin_plan(connection, *, char_id: int, table: str, changes: dict[str, Any] | None,
                         adapter_family: str) -> LsbAdminPlan:
    char_id = int(char_id)
    table = str(table or "").strip()
    family = str(adapter_family or "unknown").strip().lower()
    requested = dict(changes or {})
    issues: list[LsbAdminIssue] = []
    schema = discover_character_schema(connection)

    if family != "lsb":
        issues.append(LsbAdminIssue("lsb_only", "Administrative flags/history editing is verified only for LandSandBoat."))
    if table not in _ALLOWED:
        issues.append(LsbAdminIssue("table_not_enabled", "Only char_flags and char_history are enabled by this LSB admin editor."))
    table_info = schema.table(table) if table in _ALLOWED else None
    if table_info is None or not _REQUIRED.get(table, set()).issubset(table_info.column_names):
        issues.append(LsbAdminIssue("schema_unverified", f"{table} does not match the verified LSB schema."))

    state = detect_online_state(connection, schema, char_id)
    if state.online is True:
        issues.append(LsbAdminIssue("character_online", "Character is online; administrative DB writes are blocked."))
    elif state.online is None:
        issues.append(LsbAdminIssue("online_state_unknown", "Character online state could not be verified."))

    before = _row(connection, char_id, table) if table_info is not None else None
    if before is None and table_info is not None:
        issues.append(LsbAdminIssue("row_missing", f"Character has no {table} row."))

    normalized: dict[str, int] = {}
    allowed = _ALLOWED.get(table, set())
    for key, raw in requested.items():
        if key not in allowed:
            issues.append(LsbAdminIssue("column_not_editable", f"{table}.{key} is read-only or unsupported."))
            continue
        try:
            value = int(raw)
        except (TypeError, ValueError):
            issues.append(LsbAdminIssue("invalid_value", f"{key} must be an integer."))
            continue
        if table == "char_flags" and value not in (0, 1):
            issues.append(LsbAdminIssue("invalid_flag", f"{key} must be 0 or 1."))
            continue
        if table == "char_history" and not 0 <= value <= 0xFFFFFFFF:
            issues.append(LsbAdminIssue("history_range", f"{key} must be between 0 and 4294967295."))
            continue
        if before is not None and int(before.get(key) or 0) == value:
            continue
        normalized[key] = value

    if requested and not normalized and not any(i.blocking for i in issues):
        issues.append(LsbAdminIssue("no_change", "Requested values match the current row."))
    after = dict(before) if before is not None else None
    if after is not None:
        after.update(normalized)
    return LsbAdminPlan(char_id, table, normalized, before, after, state.online, family, issues)


def apply_lsb_admin_plan(connection, plan: LsbAdminPlan, *, approved: bool = False) -> dict[str, Any]:
    if not approved:
        raise PermissionError("Explicit approval is required to apply LSB administrative changes")
    if not plan.ready:
        raise RuntimeError("LSB administrative edit plan is not write-ready")
    try:
        if hasattr(connection, "start_transaction"):
            connection.start_transaction()
        else:
            cur = connection.cursor(); cur.execute("START TRANSACTION"); cur.close()
        schema = discover_character_schema(connection)
        if plan.adapter_family != "lsb":
            raise RuntimeError("Connected adapter is no longer verified as LandSandBoat")
        table_info = schema.table(plan.table)
        if table_info is None or not _REQUIRED[plan.table].issubset(table_info.column_names):
            raise RuntimeError("LSB administrative table schema changed since preview")
        if detect_online_state(connection, schema, plan.char_id).online is not False:
            raise RuntimeError("Character online state changed or cannot be verified")
        current = _row(connection, plan.char_id, plan.table)
        if current != plan.before:
            raise RuntimeError("Administrative state changed since preview; preview the edit again")
        assignments = ", ".join(f"`{name}` = %s" for name in plan.changes)
        params = [plan.changes[name] for name in plan.changes] + [plan.char_id]
        cursor = connection.cursor()
        try:
            cursor.execute(f"UPDATE `{plan.table}` SET {assignments} WHERE `charid` = %s LIMIT 1", tuple(params))
            if getattr(cursor, "rowcount", 1) not in (0, 1):
                raise RuntimeError("Unexpected number of administrative rows updated")
        finally:
            cursor.close()
        connection.commit()
        result = {"status": "committed", "char_id": plan.char_id, "table": plan.table, "changes": plan.changes}
        return attach_committed_audit(
            result,
            operation="lsb_admin.update",
            char_id=plan.char_id,
            adapter_family=plan.adapter_family,
            target={"table": plan.table},
            before=plan.before,
            after=plan.after,
            metadata={"changes": dict(plan.changes)},
            undo_supported=False,
        )
    except Exception:
        try:
            connection.rollback()
        finally:
            raise
