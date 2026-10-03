"""Guarded learned-spell add/remove operations for Character Editor.

DSP, Topaz and LSB share the same ``char_spells(charid, spellid)`` ownership model. The connected
server's live ``spell_list`` table is authoritative for valid spell IDs/names.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from .schema import discover_character_schema
from .session_state import detect_online_state

_VERIFIED_FAMILIES = {"dsp", "topaz", "lsb"}


@dataclass(frozen=True)
class SpellIssue:
    code: str
    message: str
    blocking: bool = True


@dataclass
class SpellEditPlan:
    char_id: int
    spell_id: int
    action: str
    spell_name: str | None
    before_learned: bool | None
    after_learned: bool | None
    online: bool | None
    adapter_family: str
    issues: list[SpellIssue] = field(default_factory=list)

    @property
    def ready(self) -> bool:
        return (
            self.before_learned is not None
            and self.after_learned is not None
            and self.before_learned != self.after_learned
            and not any(issue.blocking for issue in self.issues)
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "char_id": self.char_id,
            "spell_id": self.spell_id,
            "action": self.action,
            "spell_name": self.spell_name,
            "before_learned": self.before_learned,
            "after_learned": self.after_learned,
            "online": self.online,
            "adapter_family": self.adapter_family,
            "issues": [asdict(issue) for issue in self.issues],
            "ready": self.ready,
        }


def _columns(connection, table_name: str) -> set[str]:
    cursor = connection.cursor()
    try:
        cursor.execute(f"DESCRIBE `{table_name}`")
        return {str(row[0]) for row in (cursor.fetchall() or [])}
    finally:
        cursor.close()


def _spell_name(connection, spell_id: int) -> str | None:
    try:
        columns = _columns(connection, "spell_list")
    except Exception:
        return None
    if not {"spellid", "name"}.issubset(columns):
        return None
    cursor = connection.cursor()
    try:
        cursor.execute("SELECT `name` FROM `spell_list` WHERE `spellid` = %s LIMIT 1", (int(spell_id),))
        row = cursor.fetchone()
        return str(row[0]) if row is not None else None
    finally:
        cursor.close()


def _learned(connection, char_id: int, spell_id: int) -> bool:
    cursor = connection.cursor()
    try:
        cursor.execute(
            "SELECT 1 FROM `char_spells` WHERE `charid` = %s AND `spellid` = %s LIMIT 1",
            (int(char_id), int(spell_id)),
        )
        return cursor.fetchone() is not None
    finally:
        cursor.close()


def list_spells(connection, *, char_id: int | None = None, query: str = "", limit: int = 500) -> list[dict[str, Any]]:
    """Return live server spell catalog rows, optionally annotated with learned state."""
    columns = _columns(connection, "spell_list")
    if not {"spellid", "name"}.issubset(columns):
        raise RuntimeError("spell_list is missing required spellid/name columns")
    safe_limit = max(1, min(int(limit), 2000))
    q = str(query or "").strip()
    sql = "SELECT `spellid`, `name` FROM `spell_list`"
    params: list[Any] = []
    if q:
        if q.isdigit():
            sql += " WHERE `spellid` = %s OR `name` LIKE %s"
            params.extend([int(q), f"%{q}%"])
        else:
            sql += " WHERE `name` LIKE %s"
            params.append(f"%{q}%")
    sql += " ORDER BY `spellid` LIMIT %s"
    params.append(safe_limit)
    cursor = connection.cursor()
    try:
        cursor.execute(sql, tuple(params))
        rows = [
            {"spell_id": int(row[0]), "name": str(row[1])}
            for row in (cursor.fetchall() or [])
        ]
    finally:
        cursor.close()
    if char_id is not None:
        learned_cursor = connection.cursor()
        try:
            learned_cursor.execute("SELECT `spellid` FROM `char_spells` WHERE `charid` = %s", (int(char_id),))
            learned_ids = {int(row[0]) for row in (learned_cursor.fetchall() or [])}
        finally:
            learned_cursor.close()
        for row in rows:
            row["learned"] = row["spell_id"] in learned_ids
    return rows


def build_spell_edit_plan(
    connection,
    *,
    char_id: int,
    spell_id: int,
    action: str,
    adapter_family: str = "unknown",
) -> SpellEditPlan:
    char_id = int(char_id)
    spell_id = int(spell_id)
    family = str(adapter_family or "unknown").strip().lower()
    action = str(action or "").strip().lower()
    issues: list[SpellIssue] = []
    schema = discover_character_schema(connection)

    if family not in _VERIFIED_FAMILIES:
        issues.append(SpellIssue("adapter_unverified", "A detected DSP/Topaz/LSB adapter is required for learned-spell writes."))
    table = schema.table("char_spells")
    if table is None or not {"charid", "spellid"}.issubset(table.column_names):
        issues.append(SpellIssue("schema_unverified", "Expected char_spells(charid, spellid) was not detected."))
    if action not in {"learn", "forget"}:
        issues.append(SpellIssue("invalid_action", "action must be either 'learn' or 'forget'."))
    if not 0 <= spell_id <= 0xFFFF:
        issues.append(SpellIssue("invalid_spell_id", "spell_id must be between 0 and 65535."))

    state = detect_online_state(connection, schema, char_id)
    if state.online is True:
        issues.append(SpellIssue("character_online", "Character is online; learned-spell writes are blocked."))
    elif state.online is None:
        issues.append(SpellIssue("online_state_unknown", "Character online state could not be verified."))

    spell_name = _spell_name(connection, spell_id) if 0 <= spell_id <= 0xFFFF else None
    if spell_name is None:
        issues.append(SpellIssue("spell_not_found", "Spell ID is not present in the connected server's spell_list."))

    before: bool | None = None
    after: bool | None = None
    if table is not None and {"charid", "spellid"}.issubset(table.column_names) and spell_name is not None:
        before = _learned(connection, char_id, spell_id)
        after = action == "learn"
        if action == "learn" and before:
            issues.append(SpellIssue("already_learned", "Character already knows this spell."))
        elif action == "forget" and not before:
            issues.append(SpellIssue("not_learned", "Character does not currently know this spell."))

    return SpellEditPlan(
        char_id=char_id,
        spell_id=spell_id,
        action=action,
        spell_name=spell_name,
        before_learned=before,
        after_learned=after,
        online=state.online,
        adapter_family=family,
        issues=issues,
    )


def apply_spell_edit(connection, plan: SpellEditPlan, *, approved: bool = False) -> dict[str, Any]:
    if not approved:
        raise PermissionError("Explicit approval is required to apply learned-spell changes")
    if not plan.ready:
        raise RuntimeError("Learned-spell edit plan is not write-ready")

    try:
        if hasattr(connection, "start_transaction"):
            connection.start_transaction()
        else:
            cursor = connection.cursor()
            try:
                cursor.execute("START TRANSACTION")
            finally:
                cursor.close()

        schema = discover_character_schema(connection)
        state = detect_online_state(connection, schema, plan.char_id)
        if state.online is not False:
            raise RuntimeError("Character online state changed or cannot be verified")
        table = schema.table("char_spells")
        if table is None or not {"charid", "spellid"}.issubset(table.column_names):
            raise RuntimeError("char_spells schema changed since preview")
        if _spell_name(connection, plan.spell_id) is None:
            raise RuntimeError("Spell disappeared from spell_list since preview")
        current = _learned(connection, plan.char_id, plan.spell_id)
        if current != plan.before_learned:
            raise RuntimeError("Learned-spell state changed since preview; preview the edit again")

        cursor = connection.cursor()
        try:
            if plan.action == "learn":
                cursor.execute(
                    "INSERT INTO `char_spells` (`charid`, `spellid`) VALUES (%s, %s)",
                    (plan.char_id, plan.spell_id),
                )
            else:
                cursor.execute(
                    "DELETE FROM `char_spells` WHERE `charid` = %s AND `spellid` = %s LIMIT 1",
                    (plan.char_id, plan.spell_id),
                )
            if getattr(cursor, "rowcount", 1) != 1:
                raise RuntimeError("Expected exactly one learned-spell row to change")
        finally:
            cursor.close()
        connection.commit()
        return {
            "status": "committed",
            "char_id": plan.char_id,
            "spell_id": plan.spell_id,
            "spell_name": plan.spell_name,
            "action": plan.action,
            "before_learned": plan.before_learned,
            "after_learned": plan.after_learned,
        }
    except Exception:
        try:
            connection.rollback()
        finally:
            raise
