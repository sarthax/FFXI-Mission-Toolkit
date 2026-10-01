"""Deterministic cross-module capture entity identity relationships."""
from __future__ import annotations

import json
import sqlite3
from workbench.core.services import capture_integrity


def entity_identity_matches(
    con: sqlite3.Connection, capture_id: int, target_table: str, row_key: str
) -> list[dict]:
    """Return normalized rows linked by captured numeric entity identity.

    Event/EventView rows require the same capture + zone + numeric entity id. Actions have no zone
    column, so an actor id is linked only when that id resolves to exactly one captured entity
    snapshot in the capture. Names and timestamps are never identity keys.
    """
    try:
        key = json.loads(capture_integrity.canonical_row_key(row_key))
    except (TypeError, json.JSONDecodeError):
        return []

    seed_entity = None
    seed_zone = None
    if target_table == "capture_events":
        row = con.execute(
            """SELECT zone_db,entity_id FROM capture_events
               WHERE capture_id=? AND zone_db=? AND seq=?""",
            (capture_id, key.get("zone_db"), key.get("seq")),
        ).fetchone()
        if row:
            seed_zone, seed_entity = row["zone_db"], row["entity_id"]
    elif target_table == "capture_eventview":
        row = con.execute(
            """SELECT zone_db,entity_id FROM capture_eventview
               WHERE capture_id=? AND zone_db=? AND seq=?""",
            (capture_id, key.get("zone_db"), key.get("seq")),
        ).fetchone()
        if row:
            seed_zone, seed_entity = row["zone_db"], row["entity_id"]
    elif target_table == "capture_actions":
        row = con.execute(
            "SELECT actor FROM capture_actions WHERE capture_id=? AND action_key=?",
            (capture_id, key.get("action_key")),
        ).fetchone()
        if row:
            seed_entity = row["actor"]
    elif target_table == "capture_npc_entries":
        seed_zone = key.get("zone_db")
        seed_entity = key.get("entity_id")
    else:
        return []

    if seed_entity is None:
        return []
    try:
        entity_id = int(seed_entity)
    except (TypeError, ValueError):
        return []

    npc_rows = [
        dict(r) for r in con.execute(
            """SELECT zone_db,entity_id,name FROM capture_npc_entries
               WHERE capture_id=? AND entity_id=? ORDER BY zone_db""",
            (capture_id, entity_id),
        ).fetchall()
    ]
    if target_table == "capture_actions":
        if len(npc_rows) != 1:
            return []
        seed_zone = npc_rows[0]["zone_db"]
    elif seed_zone is not None:
        npc_rows = [r for r in npc_rows if r["zone_db"] == seed_zone]

    matches: list[dict] = []
    seen: set[tuple[str, str]] = set()
    anchor_identity = (target_table, capture_integrity.canonical_row_key(row_key))

    def add_match(peer_table: str, peer_key: dict, *, relation: str, title: str | None = None):
        canonical = capture_integrity.canonical_row_key(peer_key)
        identity = (peer_table, canonical)
        if identity == anchor_identity or identity in seen:
            return
        seen.add(identity)
        matches.append({
            "target_table": peer_table,
            "row_key": canonical,
            "relation": relation,
            "basis": "same captured numeric entity id",
            "entity_id": entity_id,
            "zone_db": seed_zone,
            "title": title,
        })

    for npc in npc_rows:
        add_match(
            "capture_npc_entries",
            {"zone_db": npc["zone_db"], "entity_id": entity_id},
            relation="captured entity identity",
            title=npc.get("name"),
        )

    if target_table == "capture_npc_entries" and seed_zone is not None:
        for row in con.execute(
            """SELECT seq,entity_name FROM capture_events
               WHERE capture_id=? AND zone_db=? AND entity_id=?
               ORDER BY seq LIMIT 50""",
            (capture_id, seed_zone, entity_id),
        ).fetchall():
            add_match(
                "capture_events", {"zone_db": seed_zone, "seq": row["seq"]},
                relation="event observed for captured entity", title=row["entity_name"],
            )
        for row in con.execute(
            """SELECT seq FROM capture_eventview
               WHERE capture_id=? AND zone_db=? AND entity_id=?
               ORDER BY seq LIMIT 50""",
            (capture_id, seed_zone, entity_id),
        ).fetchall():
            add_match(
                "capture_eventview", {"zone_db": seed_zone, "seq": row["seq"]},
                relation="EventView observed for captured entity",
            )

        unique_snapshots = con.execute(
            "SELECT COUNT(*) FROM capture_npc_entries WHERE capture_id=? AND entity_id=?",
            (capture_id, entity_id),
        ).fetchone()[0]
        if unique_snapshots == 1:
            for row in con.execute(
                """SELECT action_key,name FROM capture_actions
                   WHERE capture_id=? AND actor=? ORDER BY ts,action_key LIMIT 50""",
                (capture_id, entity_id),
            ).fetchall():
                add_match(
                    "capture_actions", {"action_key": row["action_key"]},
                    relation="battle action by captured entity", title=row["name"],
                )

    return matches


def item_identity_matches(
    con: sqlite3.Connection, capture_id: int, target_table: str, row_key: str
) -> list[dict]:
    """Return structured item/vendor/crafting rows linked by explicit ordinary item_id.

    Key-item ids are a separate namespace and are intentionally not joined here. Names, prices,
    timestamps, and nearby record order are never identity keys.
    """
    if target_table != "capture_structured_records":
        return []
    try:
        key = json.loads(capture_integrity.canonical_row_key(row_key))
        source_file = str(key["source_file"])
        family = str(key["family"])
        record_key = str(key["record_key"])
    except (TypeError, ValueError, KeyError, json.JSONDecodeError):
        return []

    anchor = con.execute(
        """SELECT item_id,item_name,family FROM capture_structured_records
           WHERE capture_id=? AND source_file=? AND family=? AND record_key=?""",
        (capture_id, source_file, family, record_key),
    ).fetchone()
    if not anchor or anchor["item_id"] is None:
        return []

    item_id = int(anchor["item_id"])
    rows = con.execute(
        """SELECT source_file,family,record_key,record_type,zone,entity_id,entity_name,
                  item_id,item_name,price
           FROM capture_structured_records
           WHERE capture_id=? AND item_id=?
             AND NOT (source_file=? AND family=? AND record_key=?)
           ORDER BY family,source_file,record_key LIMIT 100""",
        (capture_id, item_id, source_file, family, record_key),
    ).fetchall()

    vendor_families = {
        "shopstock_buy_db", "shopstock_sell_db", "guildstock_db",
        "pricelog_simple", "pricelog_lua",
    }
    out = []
    for row in rows:
        peer_family = str(row["family"])
        if peer_family == "crafttrack_csv":
            relation = "crafting evidence for captured item"
        elif peer_family in vendor_families:
            relation = "vendor/pricing evidence for captured item"
        else:
            relation = "captured observation for item"
        out.append({
            "target_table": "capture_structured_records",
            "row_key": capture_integrity.canonical_row_key({
                "source_file": row["source_file"],
                "family": peer_family,
                "record_key": row["record_key"],
            }),
            "relation": relation,
            "basis": "same captured ordinary item id",
            "item_id": item_id,
            "item_name": row["item_name"],
            "family": peer_family,
            "record_type": row["record_type"],
            "zone": row["zone"],
            "entity_id": row["entity_id"],
            "entity_name": row["entity_name"],
            "price": row["price"],
        })
    return out
