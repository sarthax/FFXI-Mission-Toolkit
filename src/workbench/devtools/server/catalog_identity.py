"""Synchronize stable server catalog entity IDs into the canonical Workbench graph.

This bridge runs at server-index rebuild boundaries. It never equates entities by display name.
Only explicit numeric IDs from known NPC/MOB provider tables participate.

Rows written by this bridge carry source_snapshot_id='server-catalog', allowing later rebuilds to
reconcile only bridge-owned identifiers without deleting identities produced by other evidence.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from workbench.core import graph

SOURCE_MARKER = "server-catalog"

ENTITY_TABLES = (
    ("sql_npc_list", "npcid", "name", "npcid", "NPC", "server-sql"),
    ("sql_mob_spawn_points", "mobid", "mobname", "mobid", "MOB", "server-sql"),
    ("lsb_npc_list", "npcid", "name", "npcid", "NPC", "landsandboat"),
    ("lsb_mob_spawn_points", "mobid", "mobname", "mobid", "MOB", "landsandboat"),
    ("topaz_npc_list", "npcid", "name", "npcid", "NPC", "topaz"),
    ("topaz_mob_spawn_points", "mobid", "mobname", "mobid", "MOB", "topaz"),
    ("dsp_npc_list", "npcid", "name", "npcid", "NPC", "dsp"),
    ("dsp_mob_spawn_points", "mobid", "mobname", "mobid", "MOB", "dsp"),
)

ENTITY_IDENTIFIER_TYPES = (
    "npcid", "mobid", "entity_id", "runtime_entity_id",
    "server_entity_id", "client_entity_id", "numeric_entity_id",
)


def _tables(con: sqlite3.Connection) -> set[str]:
    return {
        row[0] for row in con.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
    }


def _existing_root(con: sqlite3.Connection, numeric_id: int) -> tuple[str | None, bool]:
    placeholders = ",".join("?" for _ in ENTITY_IDENTIFIER_TYPES)
    rows = con.execute(
        f"""SELECT DISTINCT entity_id
            FROM entity_identifiers
            WHERE (
                    lower(identifier_type) IN ({placeholders})
                    OR lower(identifier_type) LIKE 'client_snapshot_entity_id:%'
                  )
              AND CAST(identifier_value AS TEXT)=?
            ORDER BY entity_id LIMIT 3""",
        (*ENTITY_IDENTIFIER_TYPES, str(numeric_id)),
    ).fetchall()
    roots = [row[0] for row in rows]
    if len(roots) == 1:
        return roots[0], False
    if len(roots) > 1:
        return None, True
    return None, False


def _display_name(observations: list[dict], numeric_id: int) -> str:
    names = []
    for row in observations:
        name = str(row.get("name") or "").strip()
        if name and name.casefold() not in {n.casefold() for n in names}:
            names.append(name)
    return names[0] if len(names) == 1 else str(numeric_id)


def sync_server_catalog_entities(
    source_con: sqlite3.Connection,
    graph_db: Path,
) -> dict:
    """Reconcile provider numeric entity identities into the canonical graph."""
    available = _tables(source_con)
    observations: dict[int, list[dict]] = {}

    for table, id_col, name_col, identifier_type, entity_type, provider in ENTITY_TABLES:
        if table not in available:
            continue
        cols = {row[1] for row in source_con.execute(f"PRAGMA table_info({table})")}
        if id_col not in cols:
            continue
        selected_name = name_col if name_col in cols else "NULL"
        for numeric_id, name in source_con.execute(
            f"SELECT {id_col},{selected_name} FROM {table} WHERE {id_col} IS NOT NULL"
        ):
            try:
                value = int(numeric_id)
            except (TypeError, ValueError):
                continue
            observations.setdefault(value, []).append({
                "table": table,
                "provider": provider,
                "identifier_type": identifier_type,
                "entity_type": entity_type,
                "name": name,
            })

    dst = graph.init_db(graph_db)
    counts = {
        "numeric_ids": len(observations),
        "created_roots": 0,
        "reused_roots": 0,
        "identifiers": 0,
        "ambiguous_existing_roots": 0,
        "removed_stale_identifiers": 0,
    }
    try:
        stale = dst.execute(
            "SELECT COUNT(*) FROM entity_identifiers WHERE source_snapshot_id=?",
            (SOURCE_MARKER,),
        ).fetchone()[0]
        counts["removed_stale_identifiers"] = int(stale or 0)
        dst.execute(
            "DELETE FROM entity_identifiers WHERE source_snapshot_id=?",
            (SOURCE_MARKER,),
        )

        for numeric_id in sorted(observations):
            rows = observations[numeric_id]
            root, ambiguous = _existing_root(dst, numeric_id)
            if ambiguous:
                counts["ambiguous_existing_roots"] += 1
                continue

            if root is None:
                root = f"entity:server-id:{numeric_id}"
                kinds = {row["entity_type"] for row in rows}
                entity_type = next(iter(kinds)) if len(kinds) == 1 else "ENTITY"
                metadata = {
                    "identity_source": SOURCE_MARKER,
                    "numeric_id": numeric_id,
                    "providers": sorted({row["provider"] for row in rows}),
                    "source_tables": sorted({row["table"] for row in rows}),
                    "observed_types": sorted(kinds),
                }
                dst.execute(
                    """INSERT OR IGNORE INTO entities(entity_id,entity_type,display_name,metadata_json)
                       VALUES(?,?,?,?)""",
                    (root, entity_type, _display_name(rows, numeric_id),
                     json.dumps(metadata, sort_keys=True)),
                )
                counts["created_roots"] += 1
            else:
                counts["reused_roots"] += 1

            types = {row["identifier_type"] for row in rows}
            types.add("numeric_entity_id")
            for identifier_type in sorted(types):
                dst.execute(
                    """INSERT OR IGNORE INTO entity_identifiers(
                           entity_id,identifier_type,identifier_value,source_snapshot_id
                       ) VALUES(?,?,?,?)""",
                    (root, identifier_type, str(numeric_id), SOURCE_MARKER),
                )
                if dst.execute("SELECT changes()").fetchone()[0]:
                    counts["identifiers"] += 1

        dst.commit()
        return {"status": "OK", **counts}
    finally:
        dst.close()
