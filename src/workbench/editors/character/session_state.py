"""Character online-session detection across DSP, Topaz, and LandSandBoat.

All three reference lineages use accounts_sessions with charid as the primary session key.
Custom forks are supported by validating the live table/column before querying.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any


@dataclass(frozen=True)
class SessionState:
    char_id: int
    online: bool | None
    source_table: str | None
    reason: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def detect_online_state(connection, schema, char_id: int) -> SessionState:
    char_id = int(char_id)
    if char_id <= 0:
        raise ValueError("char_id must be positive")

    table = schema.table("accounts_sessions") if hasattr(schema, "table") else None
    if table is None:
        return SessionState(char_id, None, None, "accounts_sessions_not_detected")

    columns = set(table.column_names)
    key = "charid" if "charid" in columns else ("char_id" if "char_id" in columns else None)
    if key is None:
        return SessionState(char_id, None, "accounts_sessions", "session_character_key_not_detected")

    cursor = connection.cursor()
    try:
        cursor.execute(
            f"SELECT 1 FROM `accounts_sessions` WHERE `{key}` = %s LIMIT 1",
            (char_id,),
        )
        return SessionState(char_id, cursor.fetchone() is not None, "accounts_sessions", "session_row_lookup")
    finally:
        cursor.close()
