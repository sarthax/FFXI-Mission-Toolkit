"""Live, read-only Auction House write-readiness probing.

This module inspects table/trigger availability only. It never mutates the database and does not
enable Auction House execution.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class WriteReadinessProbe:
    database: str
    tables: tuple[str, ...]
    triggers: tuple[str, ...]
    lsb_listing_ready: bool
    lsb_purchase_ready: bool
    notes: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _database_name(connection) -> str:
    cursor = connection.cursor()
    try:
        cursor.execute("SELECT DATABASE()")
        row = cursor.fetchone()
        return str(row[0] or "") if row else ""
    finally:
        cursor.close()


def _tables(connection) -> tuple[str, ...]:
    cursor = connection.cursor()
    try:
        cursor.execute("SHOW TABLES")
        return tuple(sorted(str(row[0]) for row in (cursor.fetchall() or [])))
    finally:
        cursor.close()


def _triggers(connection, database: str) -> tuple[str, ...]:
    if not database:
        return ()
    cursor = connection.cursor()
    try:
        cursor.execute(
            "SELECT `TRIGGER_NAME` FROM `information_schema`.`TRIGGERS` "
            "WHERE `TRIGGER_SCHEMA`=%s ORDER BY `TRIGGER_NAME`",
            (database,),
        )
        return tuple(str(row[0]) for row in (cursor.fetchall() or []))
    finally:
        cursor.close()


def probe_write_readiness(connection) -> WriteReadinessProbe:
    """Inspect live schema objects required by the current LSB AH write contract."""
    database = _database_name(connection)
    tables = _tables(connection)
    triggers = _triggers(connection, database)
    table_set = set(tables)
    trigger_set = set(triggers)

    listing_tables = {"auction_house", "item_basic", "chars"}
    purchase_tables = {"auction_house", "chars", "delivery_box"}
    listing_triggers = {"auction_house_list"}
    purchase_triggers = {"auction_house_buy", "delivery_box_insert"}

    listing_ready = listing_tables <= table_set and listing_triggers <= trigger_set
    purchase_ready = purchase_tables <= table_set and purchase_triggers <= trigger_set

    notes: list[str] = []
    for name in sorted(listing_tables - table_set):
        notes.append(f"listing missing table: {name}")
    for name in sorted(listing_triggers - trigger_set):
        notes.append(f"listing missing trigger: {name}")
    for name in sorted(purchase_tables - table_set):
        notes.append(f"purchase missing table: {name}")
    for name in sorted(purchase_triggers - trigger_set):
        notes.append(f"purchase missing trigger: {name}")
    if listing_ready and purchase_ready:
        notes.append("LSB table/trigger prerequisites are present; execution remains disabled pending semantic adapter verification.")

    return WriteReadinessProbe(
        database=database,
        tables=tables,
        triggers=triggers,
        lsb_listing_ready=listing_ready,
        lsb_purchase_ready=purchase_ready,
        notes=tuple(notes),
    )
