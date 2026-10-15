"""Read-only source-qualified lookup for reported live FFXI server entity IDs.

This adapter does not interpret Ashita client slots as IDs and does not assert
that an indexed server row was actually spawned in the observed session.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

SOURCES = ("dsp", "lsb")


def reconcile_reported_id(db: Path, *, zone: int, server_entity_id: int | None,
                          source: str = "dsp") -> dict:
    """Classify an exact reported ID against one indexed server source in a zone.

    States: unavailable (missing coverage or ID), no_match (index has no match),
    exact (one typed record), ambiguous (multiple typed records).
    """
    if source not in SOURCES:
        raise ValueError("Unsupported indexed server source")
    if not isinstance(zone, int) or not 0 <= zone <= 65535:
        raise ValueError("Invalid zone")
    result = {
        "source": source, "zone": zone, "server_entity_id": server_entity_id,
        "status": "unavailable", "matches": [],
        "note": "Source coverage or reported server ID unavailable",
    }
    # Never accept the transient client_index as a substitute for this argument.
    if server_entity_id is None:
        return result
    if not isinstance(server_entity_id, int) or not 0 <= server_entity_id <= 0xFFFFFFFF:
        raise ValueError("Invalid reported server entity ID")
    con = sqlite3.connect(f"file:{Path(db).resolve().as_posix()}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    try:
        table_npc = source + "_npc_list"
        table_mob = source + "_mob_spawn_points"
        present = {row[0] for row in con.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name IN (?,?)",
            (table_npc, table_mob))}
        if present != {table_npc, table_mob}:
            result["note"] = "Required source NPC/mob index tables unavailable"
            return result
        matches = []
        for row in con.execute(
            f"SELECT npcid AS id, name FROM {table_npc} WHERE zoneid=? AND npcid=?",
            (zone, server_entity_id)):
            matches.append({"kind": "npc", "id": row["id"], "name": row["name"]})
        # The indexed mob spawn table derives zone from the encoded mob ID.
        # The bit check is an index convention, not proof of instance identity.
        for row in con.execute(
            f"SELECT mobid AS id, mobname AS name FROM {table_mob} "
            "WHERE ((mobid >> 12) & 4095)=? AND mobid=?",
            (zone, server_entity_id)):
            matches.append({"kind": "mob", "id": row["id"], "name": row["name"]})
        result["matches"] = matches
        if len(matches) > 1:
            result.update(status="ambiguous",
                          note="Multiple indexed rows share this exact zone/source ID")
        elif len(matches) == 1:
            result.update(status="exact",
                          note="Exact index ID match; runtime identity not independently verified")
        else:
            result.update(status="no_match",
                          note="No exact ID in available index; not proof of missing runtime entity")
        return result
    except sqlite3.OperationalError as exc:
        # Index layouts can be partial/stale; do not promote schema errors to absence.
        result.update(status="unavailable", matches=[],
                      note=f"Index schema/query unavailable: {exc}")
        return result
    finally:
        con.close()
