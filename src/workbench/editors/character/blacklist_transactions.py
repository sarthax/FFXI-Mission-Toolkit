"""Guarded add/remove transactions for Character Editor blacklist state."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from .schema import discover_character_schema
from .session_state import detect_online_state

_VERIFIED_FAMILIES = {"dsp", "topaz", "lsb"}


@dataclass(frozen=True)
class BlacklistIssue:
    code: str
    message: str
    blocking: bool = True


@dataclass
class BlacklistEditPlan:
    char_id: int
    target_id: int
    action: str
    target: dict[str, Any] | None
    present_before: bool | None
    present_after: bool | None
    online: bool | None
    adapter_family: str
    issues: list[BlacklistIssue] = field(default_factory=list)

    @property
    def ready(self) -> bool:
        return self.target is not None and self.present_before is not None and self.present_after is not None and self.present_before != self.present_after and not any(i.blocking for i in self.issues)

    def as_dict(self) -> dict[str, Any]:
        return {"char_id": self.char_id, "target_id": self.target_id, "action": self.action, "target": self.target,
                "present_before": self.present_before, "present_after": self.present_after, "online": self.online,
                "adapter_family": self.adapter_family, "issues": [asdict(i) for i in self.issues], "ready": self.ready}


def _verified_table(schema):
    table = schema.table("char_blacklist")
    if table is None or not {"charid_owner", "charid_target"}.issubset(table.column_names):
        return None
    return table


def _target_row(connection, target_id: int) -> dict[str, Any] | None:
    cursor = connection.cursor()
    try:
        cursor.execute("SELECT `charid`, `charname` FROM `chars` WHERE `charid` = %s LIMIT 1", (int(target_id),))
        row = cursor.fetchone()
        return {"charid": int(row[0]), "charname": str(row[1])} if row else None
    finally:
        cursor.close()


def blacklist_rows(connection, char_id: int) -> list[dict[str, Any]]:
    schema = discover_character_schema(connection)
    if _verified_table(schema) is None:
        return []
    cursor = connection.cursor()
    try:
        cursor.execute("SELECT b.`charid_target`, c.`charname` FROM `char_blacklist` b LEFT JOIN `chars` c ON c.`charid` = b.`charid_target` WHERE b.`charid_owner` = %s ORDER BY c.`charname`, b.`charid_target`", (int(char_id),))
        return [{"charid_target": int(r[0]), "charname": str(r[1]) if r[1] is not None else None} for r in (cursor.fetchall() or [])]
    finally:
        cursor.close()


def _present(connection, char_id: int, target_id: int) -> bool:
    cursor = connection.cursor()
    try:
        cursor.execute("SELECT 1 FROM `char_blacklist` WHERE `charid_owner` = %s AND `charid_target` = %s LIMIT 1", (int(char_id), int(target_id)))
        return cursor.fetchone() is not None
    finally:
        cursor.close()


def build_blacklist_edit_plan(connection, *, char_id: int, target_id: int, action: str, adapter_family: str = "unknown") -> BlacklistEditPlan:
    char_id, target_id = int(char_id), int(target_id)
    family, action = str(adapter_family or "unknown").lower(), str(action or "").lower()
    issues: list[BlacklistIssue] = []
    schema = discover_character_schema(connection)
    table = _verified_table(schema)
    if family not in _VERIFIED_FAMILIES:
        issues.append(BlacklistIssue("adapter_unverified", "A detected DSP/Topaz/LSB adapter is required for blacklist writes."))
    if action not in {"add", "remove"}:
        issues.append(BlacklistIssue("action_invalid", "action must be 'add' or 'remove'"))
    if table is None:
        issues.append(BlacklistIssue("schema_unverified", "char_blacklist(charid_owner, charid_target) is not available."))
    if char_id == target_id:
        issues.append(BlacklistIssue("self_target", "A character cannot blacklist itself."))
    state = detect_online_state(connection, schema, char_id)
    if state.online is True:
        issues.append(BlacklistIssue("character_online", "Character is online; blacklist writes are blocked."))
    elif state.online is None:
        issues.append(BlacklistIssue("online_state_unknown", "Character online state could not be verified."))
    target = _target_row(connection, target_id) if target_id > 0 else None
    if target is None:
        issues.append(BlacklistIssue("target_unknown", f"Target character ID {target_id} was not found."))
    present_before = _present(connection, char_id, target_id) if table is not None and target is not None else None
    present_after = action == "add" if action in {"add", "remove"} else None
    if present_before is not None and present_after == present_before:
        issues.append(BlacklistIssue("no_change", f"Target is already {'blacklisted' if present_before else 'not blacklisted'}."))
    return BlacklistEditPlan(char_id, target_id, action, target, present_before, present_after, state.online, family, issues)


def apply_blacklist_edit(connection, plan: BlacklistEditPlan, *, approved: bool = False) -> dict[str, Any]:
    if not approved:
        raise PermissionError("Explicit approval is required to apply blacklist changes")
    if not plan.ready:
        raise RuntimeError("Blacklist edit plan is not write-ready")
    try:
        if hasattr(connection, "start_transaction"):
            connection.start_transaction()
        else:
            cur = connection.cursor(); cur.execute("START TRANSACTION"); cur.close()
        schema = discover_character_schema(connection)
        if _verified_table(schema) is None:
            raise RuntimeError("char_blacklist schema changed since preview")
        if detect_online_state(connection, schema, plan.char_id).online is not False:
            raise RuntimeError("Character online state changed or cannot be verified")
        if _target_row(connection, plan.target_id) is None:
            raise RuntimeError("Target character no longer exists")
        present_now = _present(connection, plan.char_id, plan.target_id)
        if present_now != plan.present_before:
            raise RuntimeError("Blacklist state changed since preview; preview the edit again")
        cursor = connection.cursor()
        try:
            if plan.action == "add":
                cursor.execute("INSERT INTO `char_blacklist` (`charid_owner`, `charid_target`) VALUES (%s, %s)", (plan.char_id, plan.target_id))
            else:
                cursor.execute("DELETE FROM `char_blacklist` WHERE `charid_owner` = %s AND `charid_target` = %s LIMIT 1", (plan.char_id, plan.target_id))
        finally:
            cursor.close()
        connection.commit()
        return {"status": "committed", "char_id": plan.char_id, "target_id": plan.target_id, "action": plan.action,
                "target": plan.target, "present_before": plan.present_before, "present_after": plan.present_after}
    except Exception:
        try:
            connection.rollback()
        finally:
            raise
