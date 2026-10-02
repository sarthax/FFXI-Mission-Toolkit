"""Runtime discovery of character-owned SQL capabilities.

Do not assume one server generation. Known LSB/Topaz/DSP names seed classification, while
SHOW TABLES / DESCRIBE determine what the connected database actually supports.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

KNOWN_CAPABILITIES: dict[str, tuple[str, ...]] = {
    "identity": ("chars",),
    "profile": ("char_profile",),
    "jobs": ("char_jobs", "char_exp"),
    "job_points": ("char_job_points",),
    "skills": ("char_skills",),
    "inventory": ("char_inventory", "char_equip", "char_storage"),
    "appearance": ("char_look", "char_style"),
    "spells": ("char_spells",),
    "merits": ("char_merit",),
    "points": ("char_points",),
    "unlocks": ("char_unlocks",),
    "variables": ("char_vars",),
    "effects": ("char_effects",),
    "pets": ("char_pet",),
    "stats": ("char_stats",),
    "blacklist": ("char_blacklist",),
    "delivery": ("delivery_box",),
    "sessions": ("accounts_sessions",),
}

# Packed/logical state is historically stored on `chars` across DSP/Topaz and remains there
# in current LSB.  Some forks may relocate fields, so discovery checks both `chars` and
# `char_profile` and records the physical table.column location instead of assuming one table.
PACKED_LOG_HINTS = {
    "missions": "missions",
    "assault": "assaults",
    "campaign": "campaign",
    "eminence": "eminence",
    "quests": "quests",
    "keyitems": "key_items",
    "key_items": "key_items",
    "set_blue_spells": "blue_spells",
    "abilities": "abilities",
    "weaponskills": "weaponskills",
    "titles": "titles",
    "zones": "visited_zones",
    "unlocked_weapons": "unlocked_weapons",
}


@dataclass(frozen=True)
class ColumnInfo:
    name: str
    sql_type: str
    nullable: bool
    key: str
    default: Any
    extra: str

    @property
    def is_binary(self) -> bool:
        t = self.sql_type.lower()
        return any(token in t for token in ("blob", "binary", "varbinary", "bytea"))


@dataclass
class TableInfo:
    name: str
    columns: list[ColumnInfo] = field(default_factory=list)
    capability: str = "other"
    character_key: str | None = None

    @property
    def column_names(self) -> set[str]:
        return {c.name for c in self.columns}

    @property
    def binary_columns(self) -> list[str]:
        return [c.name for c in self.columns if c.is_binary]


@dataclass
class CharacterSchema:
    tables: dict[str, TableInfo]
    capabilities: dict[str, list[str]]
    packed_profile_fields: dict[str, str]

    @property
    def packed_fields(self) -> dict[str, str]:
        """Preferred name; packed_profile_fields remains for compatibility with early callers."""
        return self.packed_profile_fields

    def has(self, capability: str) -> bool:
        return bool(self.capabilities.get(capability))

    def table(self, name: str) -> TableInfo | None:
        return self.tables.get(name)

    def summary(self) -> dict[str, Any]:
        return {
            "capabilities": {k: list(v) for k, v in sorted(self.capabilities.items())},
            "packed_fields": dict(sorted(self.packed_profile_fields.items())),
            "packed_profile_fields": dict(sorted(self.packed_profile_fields.items())),
            "tables": {
                name: {
                    "capability": table.capability,
                    "character_key": table.character_key,
                    "columns": len(table.columns),
                    "binary_columns": table.binary_columns,
                }
                for name, table in sorted(self.tables.items())
            },
        }


def _rows(cursor) -> list[tuple]:
    return list(cursor.fetchall() or [])


def _show_tables(cursor) -> list[str]:
    cursor.execute("SHOW TABLES")
    return [str(row[0]) for row in _rows(cursor)]


def _describe(cursor, table: str) -> list[ColumnInfo]:
    safe = table.replace("`", "``")
    cursor.execute(f"DESCRIBE `{safe}`")
    out = []
    for row in _rows(cursor):
        name, sql_type, null, key, default, extra = (list(row) + [None] * 6)[:6]
        out.append(
            ColumnInfo(
                name=str(name),
                sql_type=str(sql_type),
                nullable=str(null).upper() == "YES",
                key=str(key or ""),
                default=default,
                extra=str(extra or ""),
            )
        )
    return out


def _capability_for_table(name: str) -> str:
    for capability, names in KNOWN_CAPABILITIES.items():
        if name in names:
            return capability
    if name.startswith("char_"):
        return "character_other"
    return "other"


def _character_key(columns: set[str]) -> str | None:
    for candidate in ("charid", "char_id", "character_id"):
        if candidate in columns:
            return candidate
    return None


def discover_character_schema(connection) -> CharacterSchema:
    cursor = connection.cursor()
    try:
        names = _show_tables(cursor)
        tables: dict[str, TableInfo] = {}
        capabilities: dict[str, list[str]] = {}
        for name in names:
            if (
                name != "chars"
                and not name.startswith("char_")
                and name not in ("delivery_box", "accounts_sessions")
            ):
                continue
            columns = _describe(cursor, name)
            table = TableInfo(
                name=name,
                columns=columns,
                capability=_capability_for_table(name),
                character_key=_character_key({c.name for c in columns}),
            )
            tables[name] = table
            capabilities.setdefault(table.capability, []).append(name)

        packed: dict[str, str] = {}
        for table_name in ("chars", "char_profile"):
            source = tables.get(table_name)
            if source is None:
                continue
            by_name = {c.name: c for c in source.columns}
            for field_name, logical in PACKED_LOG_HINTS.items():
                column = by_name.get(field_name)
                if column and column.is_binary and logical not in packed:
                    packed[logical] = f"{table_name}.{field_name}"

        for values in capabilities.values():
            values.sort()
        return CharacterSchema(tables=tables, capabilities=capabilities, packed_profile_fields=packed)
    finally:
        cursor.close()
