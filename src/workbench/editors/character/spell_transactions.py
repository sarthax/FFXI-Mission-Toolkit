"""Guarded learn/unlearn transactions for Character Editor spells.

DSP, Topaz, and LSB share the same ``char_spells(charid, spellid)`` row contract.  Writes are
allowed only for an offline character, a verified table shape, and a spell that exists in the
connected server's live ``spell_list`` table.  Apply rechecks all mutable state inside the
transaction so a stale preview cannot be committed.
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
    spell: dict[str, Any] | None
    learned_before: bool | None
    learned_after: bool | None
    online: bool | None
    adapter_family: str
    issues: list[SpellIssue] = field(default_factory=list)

    @property
    def ready(self) -> bool:
        return (
            self.spell is not None
            and self.learned_before is not None
            and self.learned_after is not None
            and self.learned_before != self.learned_after
            and not any(issue.blocking for issue in self.issues)
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "char_id": self.char_id,
            "spell_id": self.spell_id,
            "action": self.action,
            "spell": self.spell,
            "learned_before": self.learned_before,
            "learned_after": self.learned_after,
            "online": self.online,
            "adapter_family": self.adapter_family,
            "issues": [asdict(issue) for issue in self.issues],
            "ready": self.ready,
        }


def _table_columns(connection, table_name: str) -> set[str]:
    cursor = connection.cursor()
    try:
        cursor.execute(f"SHOW COLUMNS FROM `{table_name}`")
        return {str(row[0]) for row in (cursor.fetchall() or [])}
    finally:
        cursor.close()


def _spell_row(connection, spell_id: int) -> dict[str, Any] | None:
    try:
        columns = _table_columns(connection, "spell_list")
    except Exception:
        return None
    if not {"spellid", "name"}.issubset(columns):
        return None
    optional = [name for name in ("group", "family", "element", "skill", "mpCost", "castTime", "recastTime") if name in columns]
    selected = ["spellid", "name", *optional]
    cursor = connection.cursor()
    try:
        cursor.execute(
            "SELECT " + ", ".join(f"`{name}`" for name in selected) + " FROM `spell_list` WHERE `spellid` = %s LIMIT 1",
            (int(spell_id),),
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return dict(zip(selected, row))
    finally:
        cursor.close()


def search_spell_catalog(connection, query: str = "", *, limit: int = 200) -> list[dict[str, Any]]:
    columns = _table_columns(connection, "spell_list")
    if not {"spellid", "name"}.issubset(columns):
        raise RuntimeError("spell_list is missing required spellid/name columns")
    optional = [name for name in ("group", "family", "element", "skill", "mpCost", "castTime", "recastTime") if name in columns]
    selected = ["spellid", "name", *optional]
    safe_limit = max(1, min(int(limit), 1000))
    q = str(query or "").strip()
    sql = "SELECT " + ", ".join(f"`{name}`" for name in selected) + " FROM `spell_list`"
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
        return [dict(zip(selected, row)) for row in (cursor.fetchall() or [])]
    finally:
        cursor.close()


def learned_spell_ids(connection, char_id: int) -> list[int]:
    schema = discover_character_schema(connection)
    table = schema.table("char_spells")
    if table is None or table.character_key is None or "spellid" not in table.column_names:
        return []
    cursor = connection.cursor()
    try:
        cursor.execute(
            f"SELECT `spellid` FROM `char_spells` WHERE `{table.character_key}` = %s ORDER BY `spellid`",
            (int(char_id),),
        )
        return [int(row[0]) for row in (cursor.fetchall() or [])]
    finally:
        cursor.close()


def _is_learned(connection, table, char_id: int, spell_id: int) -> bool:
    cursor = connection.cursor()
    try:
        cursor.execute(
            f"SELECT 1 FROM `char_spells` WHERE `{table.character_key}` = %s AND `spellid` = %s LIMIT 1",
            (int(char_id), int(spell_id)),
        )
        return cursor.fetchone() is not None
    finally:
        cursor.close()


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
    table = schema.table("char_spells")

    if family not in _VERIFIED_FAMILIES:
        issues.append(SpellIssue("adapter_unverified", "A detected DSP/Topaz/LSB adapter is required for spell writes."))
    if action not in {"learn", "unlearn"}:
        issues.append(SpellIssue("action_invalid", "action must be 'learn' or 'unlearn'"))
    if not 0 <= spell_id <= 0xFFFF:
        issues.append(SpellIssue("spell_id_invalid", "spell_id must be between 0 and 65535"))
    if table is None or table.character_key is None or "spellid" not in table.column_names:
        issues.append(SpellIssue("schema_unverified", "char_spells(charid, spellid) is not available in the connected schema."))

    state = detect_online_state(connection, schema, char_id)
    if state.online is True:
        issues.append(SpellIssue("character_online", "Character is online; spell writes are blocked."))
    elif state.online is None:
        issues.append(SpellIssue("online_state_unknown", "Character online state could not be verified."))

    spell = _spell_row(connection, spell_id) if 0 <= spell_id <= 0xFFFF else None
    if spell is None:
        issues.append(SpellIssue("spell_unknown", f"Spell ID {spell_id} was not found in the connected spell_list."))

    learned_before: bool | None = None
    learned_after: bool | None = None
    if table is not None and table.character_key is not None and "spellid" in table.column_names and spell is not None:
        learned_before = _is_learned(connection, table, char_id, spell_id)
        learned_after = action == "learn" if action in {"learn", "unlearn"} else None
        if learned_after == learned_before and action in {"learn", "unlearn"}:
            issues.append(SpellIssue("no_change", f"Spell {spell_id} is already {'learned' if learned_before else 'unlearned'}."))

    return SpellEditPlan(
        char_id=char_id,
        spell_id=spell_id,
        action=action,
        spell=spell,
        learned_before=learned_before,
        learned_after=learned_after,
        online=state.online,
        adapter_family=family,
        issues=issues,
    )


def apply_spell_edit(connection, plan: SpellEditPlan, *, approved: bool = False) -> dict[str, Any]:
    if not approved:
        raise PermissionError("Explicit approval is required to apply spell changes")
    if not plan.ready:
        raise RuntimeError("Spell edit plan is not write-ready")

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
        table = schema.table("char_spells")
        if table is None or table.character_key is None or "spellid" not in table.column_names:
            raise RuntimeError("char_spells schema changed since preview")
        state = detect_online_state(connection, schema, plan.char_id)
        if state.online is not False:
            raise RuntimeError("Character online state changed or cannot be verified")
        if _spell_row(connection, plan.spell_id) is None:
            raise RuntimeError("Spell no longer exists in spell_list")
        learned_now = _is_learned(connection, table, plan.char_id, plan.spell_id)
        if learned_now != plan.learned_before:
            raise RuntimeError("Character spell state changed since preview; preview the edit again")

        cursor = connection.cursor()
        try:
            if plan.action == "learn":
                cursor.execute(
                    f"INSERT INTO `char_spells` (`{table.character_key}`, `spellid`) VALUES (%s, %s)",
                    (plan.char_id, plan.spell_id),
                )
            else:
                cursor.execute(
                    f"DELETE FROM `char_spells` WHERE `{table.character_key}` = %s AND `spellid` = %s LIMIT 1",
                    (plan.char_id, plan.spell_id),
                )
            if getattr(cursor, "rowcount", 1) not in (0, 1):
                raise RuntimeError("Unexpected number of char_spells rows changed")
        finally:
            cursor.close()

        connection.commit()
        return {
            "status": "committed",
            "char_id": plan.char_id,
            "spell_id": plan.spell_id,
            "action": plan.action,
            "spell": plan.spell,
            "learned_before": plan.learned_before,
            "learned_after": plan.learned_after,
        }
    except Exception:
        try:
            connection.rollback()
        finally:
            raise
