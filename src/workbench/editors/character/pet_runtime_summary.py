"""Read-only companion and persisted runtime-state summaries for Character Editor.

These tables contain a mixture of relational IDs, opaque packed pet state, persisted status
effects, and recast restoration data.  This module deliberately enriches them for inspection
without implying that raw row editing is safe.
"""
from __future__ import annotations

from typing import Any

from .schema import discover_character_schema


def _dict_row(cursor) -> dict[str, Any] | None:
    row = cursor.fetchone()
    if row is None:
        return None
    names = [str(d[0]) for d in cursor.description or ()]
    return dict(zip(names, row))


def _table_exists(connection, name: str) -> bool:
    cursor = connection.cursor()
    try:
        cursor.execute("SHOW TABLES LIKE %s", (str(name),))
        return cursor.fetchone() is not None
    finally:
        cursor.close()


def _pet_name(connection, pet_id: int) -> str | None:
    if int(pet_id or 0) <= 0 or not _table_exists(connection, "pet_name"):
        return None
    cursor = connection.cursor()
    try:
        cursor.execute("SELECT `name` FROM `pet_name` WHERE `id` = %s LIMIT 1", (int(pet_id),))
        row = cursor.fetchone()
        return str(row[0]) if row and row[0] is not None else None
    finally:
        cursor.close()


def _rows(connection, table: str, char_id: int, limit: int = 500) -> list[dict[str, Any]]:
    cursor = connection.cursor()
    try:
        cursor.execute(f"SELECT * FROM `{table}` WHERE `charid` = %s LIMIT %s", (int(char_id), int(limit)))
        names = [str(d[0]) for d in cursor.description or ()]
        return [dict(zip(names, row)) for row in (cursor.fetchall() or [])]
    finally:
        cursor.close()


def _blob_size(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, memoryview):
        value = value.tobytes()
    if isinstance(value, (bytes, bytearray)):
        return len(value)
    return None


def build_pet_runtime_summary(connection, char_id: int, *, adapter_family: str) -> dict[str, Any]:
    char_id = int(char_id)
    schema = discover_character_schema(connection)
    family = str(adapter_family or "unknown").lower()
    pet_rows = _rows(connection, "char_pet", char_id, 1) if schema.table("char_pet") else []
    pet = pet_rows[0] if pet_rows else None

    companion: dict[str, Any] | None = None
    if pet:
        wyvern_id = int(pet.get("wyvernid") or 0)
        automaton_id = int(pet.get("automatonid") or 0)
        companion = {
            "wyvern": {"id": wyvern_id, "name": _pet_name(connection, wyvern_id)},
            "automaton": {"id": automaton_id, "name": _pet_name(connection, automaton_id)},
            "adventuring_fellow_id": int(pet.get("adventuringfellowid") or 0),
            "chocobo_id": int(pet.get("chocoboid") or 0),
            "opaque": {
                "unlocked_attachments_bytes": _blob_size(pet.get("unlocked_attachments")),
                "equipped_attachments_bytes": _blob_size(pet.get("equipped_attachments")),
                "chocobo_user_data_bytes": _blob_size(pet.get("chocobo_user_data")),
            },
        }

    chocobo = None
    chocobo_table = schema.table("char_chocobos")
    if chocobo_table and chocobo_table.character_key == "charid":
        rows = _rows(connection, "char_chocobos", char_id, 1)
        if rows:
            raw = rows[0]
            visible = (
                "first_name", "last_name", "sex", "created", "last_update_age", "stage", "location", "color",
                "strength", "endurance", "discernment", "receptivity", "affection", "energy", "satisfaction",
                "ability1", "ability2", "personality", "weather_preference", "hunger", "care_plan", "held_item",
                "locked_plan", "appearance", "walk_progress",
            )
            chocobo = {name: raw.get(name) for name in visible if name in raw}

    effects = _rows(connection, "char_effects", char_id) if schema.table("char_effects") else []
    recasts = _rows(connection, "char_recast", char_id) if schema.table("char_recast") else []

    return {
        "char_id": char_id,
        "adapter_family": family,
        "companion": companion,
        "chocobo": chocobo,
        "effects": effects,
        "recasts": recasts,
        "safety": {
            "pet": "read_only_relational_and_packed_state",
            "effects": "read_only_persisted_runtime_state",
            "recasts": "read_only_persisted_runtime_state",
            "reason": "These rows are loaded into live character/runtime objects and include relational or opaque semantics; raw direct editing is not enabled.",
        },
    }
