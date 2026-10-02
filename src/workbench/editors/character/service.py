"""Read-only Character Editor service foundation.

Writes are intentionally not enabled in this first slice. The service first discovers the live
schema and exposes exactly what can be administered on the connected server generation.
"""
from __future__ import annotations

from dataclasses import asdict
from typing import Any

from .schema import CharacterSchema, discover_character_schema


class CharacterEditorService:
    def __init__(self, connection):
        self.connection = connection
        self.schema: CharacterSchema = discover_character_schema(connection)

    @staticmethod
    def _dict_rows(cursor) -> list[dict[str, Any]]:
        names = [str(d[0]) for d in cursor.description or ()]
        return [dict(zip(names, row)) for row in cursor.fetchall()]

    def _chars_table(self):
        table = self.schema.table("chars")
        if table is None:
            raise RuntimeError("Connected database has no recognized chars table")
        return table

    def search_characters(self, query: str = "", limit: int = 50) -> list[dict[str, Any]]:
        table = self._chars_table()
        cols = table.column_names
        id_col = "charid" if "charid" in cols else ("char_id" if "char_id" in cols else None)
        name_col = "charname" if "charname" in cols else ("name" if "name" in cols else None)
        if not id_col or not name_col:
            raise RuntimeError("chars table is missing a recognized character id/name column")

        optional = [
            c for c in ("accid", "gmlevel", "pos_zone", "nation", "mjob", "sjob", "lastonline")
            if c in cols
        ]
        selected = [id_col, name_col, *optional]
        sql = "SELECT " + ", ".join(f"`{c}`" for c in selected) + " FROM `chars`"
        params: list[Any] = []
        q = (query or "").strip()
        if q:
            if q.isdigit():
                sql += f" WHERE `{id_col}` = %s OR `{name_col}` LIKE %s"
                params.extend([int(q), f"%{q}%"])
            else:
                sql += f" WHERE `{name_col}` LIKE %s"
                params.append(f"%{q}%")
        sql += f" ORDER BY `{name_col}` LIMIT %s"
        params.append(max(1, min(int(limit), 500)))

        cursor = self.connection.cursor()
        try:
            cursor.execute(sql, tuple(params))
            return self._dict_rows(cursor)
        finally:
            cursor.close()

    def _identity(self, char_id: int) -> dict[str, Any] | None:
        table = self._chars_table()
        cols = table.column_names
        id_col = "charid" if "charid" in cols else "char_id"
        cursor = self.connection.cursor()
        try:
            cursor.execute(f"SELECT * FROM `chars` WHERE `{id_col}` = %s LIMIT 1", (int(char_id),))
            rows = self._dict_rows(cursor)
            return rows[0] if rows else None
        finally:
            cursor.close()

    def load_table(self, char_id: int, table_name: str, limit: int = 5000) -> list[dict[str, Any]]:
        table = self.schema.table(table_name)
        if table is None:
            raise KeyError(f"Unknown or non-character table: {table_name}")
        if table_name == "chars":
            identity = self._identity(char_id)
            return [identity] if identity else []
        if table.character_key is None:
            return []
        safe_limit = max(1, min(int(limit), 20000))
        cursor = self.connection.cursor()
        try:
            cursor.execute(
                f"SELECT * FROM `{table_name}` WHERE `{table.character_key}` = %s LIMIT %s",
                (int(char_id), safe_limit),
            )
            return self._dict_rows(cursor)
        finally:
            cursor.close()

    def load_character(self, char_id: int, include_rows: bool = False) -> dict[str, Any]:
        identity = self._identity(char_id)
        if identity is None:
            raise KeyError(f"Character {char_id} was not found")

        sections: dict[str, Any] = {}
        for capability, table_names in sorted(self.schema.capabilities.items()):
            section = {
                "tables": table_names,
                "available": bool(table_names),
            }
            if include_rows:
                section["rows"] = {
                    table_name: self.load_table(char_id, table_name)
                    for table_name in table_names
                }
            sections[capability] = section

        return {
            "character": identity,
            "sections": sections,
            "packed_profile_fields": dict(self.schema.packed_profile_fields),
            "schema": self.schema.summary(),
            "write_enabled": False,
        }

    def capability_manifest(self) -> dict[str, Any]:
        """Stable JSON-friendly manifest for the future GUI and decoder worklist."""
        return self.schema.summary()
