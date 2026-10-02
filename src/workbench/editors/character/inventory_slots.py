"""Inventory container and free-slot discovery for Character Editor."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# Human-facing FFXI container names keyed by the stable runtime location id.
CONTAINERS = {
    0: "Inventory",
    1: "Mog Safe",
    2: "Storage",
    3: "Temporary Items",
    4: "Mog Locker",
    5: "Mog Satchel",
    6: "Mog Sack",
    7: "Mog Case",
    8: "Mog Wardrobe",
    9: "Mog Safe 2",
    10: "Mog Wardrobe 2",
    11: "Mog Wardrobe 3",
    12: "Mog Wardrobe 4",
    13: "Mog Wardrobe 5",
    14: "Mog Wardrobe 6",
    15: "Mog Wardrobe 7",
    16: "Mog Wardrobe 8",
}

# Stable database/runtime short names, kept separately from display labels.
CONTAINER_KEYS = {
    0: "inventory",
    1: "safe",
    2: "storage",
    3: "temporary",
    4: "locker",
    5: "satchel",
    6: "sack",
    7: "case",
    8: "wardrobe",
    9: "safe2",
    10: "wardrobe2",
    11: "wardrobe3",
    12: "wardrobe4",
    13: "wardrobe5",
    14: "wardrobe6",
    15: "wardrobe7",
    16: "wardrobe8",
}

# Compatibility alias for callers that want an explicit label map.
CONTAINER_LABELS = CONTAINERS

# char_storage columns that directly carry capacity. Storage (2) is furnishing-derived and
# Temporary Items (3) is runtime state, so neither is offered for direct DB injection here.
CAPACITY_COLUMNS = {
    0: "inventory",
    1: "safe",
    4: "locker",
    5: "satchel",
    6: "sack",
    7: "case",
    8: "wardrobe",
    9: "safe2",
    10: "wardrobe2",
    11: "wardrobe3",
    12: "wardrobe4",
    13: "wardrobe5",
    14: "wardrobe6",
    15: "wardrobe7",
    16: "wardrobe8",
}


@dataclass(frozen=True)
class SlotState:
    location: int
    name: str
    capacity: int
    occupied_slots: tuple[int, ...]
    first_free_slot: int | None

    @property
    def full(self) -> bool:
        return self.first_free_slot is None


def _storage_row(connection, char_id: int) -> tuple[dict[str, Any], set[str]]:
    cursor = connection.cursor()
    try:
        cursor.execute("DESCRIBE `char_storage`")
        columns = [str(row[0]) for row in cursor.fetchall() or []]
        if "charid" not in columns:
            raise RuntimeError("char_storage has no charid column")
        cursor.execute("SELECT * FROM `char_storage` WHERE `charid` = %s LIMIT 1", (int(char_id),))
        row = cursor.fetchone()
        if row is None:
            raise RuntimeError(f"Character {char_id} has no char_storage row")
        return dict(zip(columns, row)), set(columns)
    finally:
        cursor.close()


def resolve_container_capacity(connection, char_id: int, location: int) -> int:
    location = int(location)
    column = CAPACITY_COLUMNS.get(location)
    if not column:
        raise ValueError(f"Container {location} is not safe for direct DB injection")
    row, columns = _storage_row(connection, char_id)
    if column not in columns:
        raise ValueError(f"Connected server does not support container {location} ({column})")
    return max(0, int(row.get(column) or 0))


def inspect_slots(connection, char_id: int, location: int = 0) -> SlotState:
    location = int(location)
    capacity = resolve_container_capacity(connection, char_id, location)
    cursor = connection.cursor()
    try:
        cursor.execute(
            "SELECT `slot` FROM `char_inventory` WHERE `charid` = %s AND `location` = %s ORDER BY `slot`",
            (int(char_id), location),
        )
        occupied = tuple(sorted({int(row[0]) for row in cursor.fetchall() or []}))
    finally:
        cursor.close()

    occupied_set = set(occupied)
    first_free = next((slot for slot in range(1, capacity + 1) if slot not in occupied_set), None)
    return SlotState(
        location=location,
        name=CONTAINERS.get(location, f"Container {location}"),
        capacity=capacity,
        occupied_slots=occupied,
        first_free_slot=first_free,
    )
