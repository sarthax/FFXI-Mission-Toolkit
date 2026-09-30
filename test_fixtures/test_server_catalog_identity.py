#!/usr/bin/env python3
"""Regression for automatic server-catalog -> canonical entity identity ingestion."""
from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path

import feature_trace
from workbench.core import graph
from workbench.core.services.server_catalog_identity import (
    SOURCE_MARKER,
    sync_server_catalog_entities,
)


def main():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        graph_db = root / "workbench.db"
        source = sqlite3.connect(":memory:")

        source.execute("CREATE TABLE sql_npc_list(npcid INTEGER, name TEXT)")
        source.execute("CREATE TABLE lsb_npc_list(npcid INTEGER, name TEXT)")
        source.execute("CREATE TABLE topaz_npc_list(npcid INTEGER, name TEXT)")
        source.execute("CREATE TABLE dsp_npc_list(npcid INTEGER, name TEXT)")
        source.execute("CREATE TABLE lsb_mob_spawn_points(mobid INTEGER, mobname TEXT)")
        source.executemany(
            "INSERT INTO sql_npc_list VALUES(?,?)",
            [(100, "Shared NPC"), (300, "Ambiguous NPC")],
        )
        for table in ("lsb_npc_list", "topaz_npc_list", "dsp_npc_list"):
            source.execute(f"INSERT INTO {table} VALUES(?,?)", (100, "Shared NPC"))
        source.execute(
            "INSERT INTO lsb_mob_spawn_points VALUES(?,?)",
            (200, "Catalog Mob"),
        )

        g = graph.init_db(graph_db)
        # Existing evidence-backed root must be reused rather than replaced.
        g.execute(
            "INSERT INTO entities(entity_id,entity_type,display_name,metadata_json) VALUES(?,?,?,?)",
            ("npc:existing", "NPC", "Shared NPC", "{}"),
        )
        g.execute(
            """INSERT INTO entity_identifiers(
                   entity_id,identifier_type,identifier_value,source_snapshot_id
               ) VALUES(?,?,?,?)""",
            ("npc:existing", "npcid", "100", "entity-profile"),
        )

        # Two independent existing roots for the same numeric id are a real ambiguity;
        # catalog ingestion must not choose between them.
        for node in ("npc:ambiguous-a", "npc:ambiguous-b"):
            g.execute(
                "INSERT INTO entities(entity_id,entity_type,display_name,metadata_json) VALUES(?,?,?,?)",
                (node, "NPC", node, "{}"),
            )
            g.execute(
                """INSERT INTO entity_identifiers(
                       entity_id,identifier_type,identifier_value,source_snapshot_id
                   ) VALUES(?,?,?,?)""",
                (node, "npcid", "300", "fixture"),
            )
        g.commit()
        g.close()

        first = sync_server_catalog_entities(source, graph_db)
        assert first["status"] == "OK", first
        assert first["numeric_ids"] == 3, first
        assert first["reused_roots"] == 1, first
        assert first["created_roots"] == 1, first
        assert first["ambiguous_existing_roots"] == 1, first

        g = sqlite3.connect(graph_db)
        roots_100 = g.execute(
            "SELECT DISTINCT entity_id FROM entity_identifiers WHERE identifier_value='100'"
        ).fetchall()
        assert roots_100 == [("npc:existing",)], roots_100

        generated = g.execute(
            """SELECT entity_id,identifier_type,source_snapshot_id
               FROM entity_identifiers
               WHERE identifier_value='200'
               ORDER BY identifier_type"""
        ).fetchall()
        assert generated == [
            ("entity:server-id:200", "mobid", SOURCE_MARKER),
            ("entity:server-id:200", "numeric_entity_id", SOURCE_MARKER),
        ], generated

        # Feature Trace now gains a canonical root from ingestion, not a page-time identity guess.
        path = feature_trace.entity_implementation_path(g, source, "200")
        assert path and path["canonical_mapped"] is True, path
        assert path["canonical_root"] == "entity:server-id:200", path
        g.close()

        # Rebuild reconciliation removes bridge-owned stale IDs while retaining unrelated roots.
        source.execute("DELETE FROM lsb_mob_spawn_points WHERE mobid=200")
        second = sync_server_catalog_entities(source, graph_db)
        assert second["removed_stale_identifiers"] >= 2, second
        g = sqlite3.connect(graph_db)
        assert g.execute(
            "SELECT COUNT(*) FROM entity_identifiers WHERE identifier_value='200'"
        ).fetchone()[0] == 0
        assert g.execute(
            """SELECT COUNT(*) FROM entity_identifiers
               WHERE entity_id='npc:existing' AND identifier_type='npcid'
                 AND identifier_value='100' AND source_snapshot_id='entity-profile'"""
        ).fetchone()[0] == 1
        g.close()
        source.close()

    print("server catalog canonical identity sync self-test: PASS")


if __name__ == "__main__":
    main()
