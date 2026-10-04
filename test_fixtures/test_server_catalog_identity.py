#!/usr/bin/env python3
"""Regression for automatic server-catalog -> canonical entity identity ingestion."""
from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path

import feature_trace
from workbench.core import graph
from workbench.core.services.feature_trace_catalog import provider_relationships
from workbench.core.services.server_catalog_identity import (
    SOURCE_MARKER,
    sync_server_catalog_entities,
)
from test_fixtures.test_feature_trace_drop_chain_benchmarks import (
    test_drop_row_composite_identity_is_stable_and_navigable,
    test_generic_nm_trace_reaches_drop_rows_and_items,
)


def _assert_wiki_mapping_target_closure() -> None:
    con=sqlite3.connect(":memory:")
    con.execute("CREATE TABLE lsb_item_basic(itemid INTEGER, name TEXT)")
    con.execute("INSERT INTO lsb_item_basic VALUES(2413,'Coiler')")
    con.execute("""CREATE TABLE reference_wiki_mappings(
        mapping_id TEXT, claim_id TEXT, target_domain TEXT, target_table TEXT,
        target_key TEXT, target_label TEXT, mapping_method TEXT,
        mapping_status TEXT, confidence TEXT
    )""")
    con.executemany(
        "INSERT INTO reference_wiki_mappings VALUES(?,?,?,?,?,?,?,?,?)",
        [
            ("map-ok","claim-1","item","lsb_item_basic","2413","Coiler","NORMALIZED_NAME_EXACT","MAPPED","HIGH"),
            ("map-ambiguous","claim-2","item","lsb_item_basic","2413","Coiler","NORMALIZED_NAME_EXACT","AMBIGUOUS","LOW"),
        ],
    )
    links=provider_relationships(con,"catalog:reference_wiki_mappings:map-ok")
    target_links=[row for row in links if row.get("relationship")=="REFERENCE_MAPPING_TARGET"]
    assert len(target_links)==1,target_links
    assert target_links[0]["target_node"]=="catalog:lsb_item_basic:2413",target_links
    assert target_links[0]["adapter"]=="server",target_links
    assert "MAPPED target_table + target_key" in str(target_links[0].get("basis")),target_links

    ambiguous=provider_relationships(con,"catalog:reference_wiki_mappings:map-ambiguous")
    assert not [row for row in ambiguous if row.get("relationship")=="REFERENCE_MAPPING_TARGET"],ambiguous

    con.execute("INSERT INTO lsb_item_basic VALUES(2413,'Duplicate Coiler')")
    duplicate=provider_relationships(con,"catalog:reference_wiki_mappings:map-ok")
    assert not [row for row in duplicate if row.get("relationship")=="REFERENCE_MAPPING_TARGET"],duplicate
    con.close()


def _assert_capture_client_build_closure() -> None:
    con=sqlite3.connect(":memory:")
    con.execute("CREATE TABLE identity_snapshots(snapshot_id TEXT, version TEXT)")
    con.execute("CREATE TABLE captures(capture_id INTEGER, capture_label TEXT, client_build TEXT)")
    con.execute("INSERT INTO identity_snapshots VALUES('client:2022','30120222_1')")
    con.execute("INSERT INTO captures VALUES(17,'Ancient Vows retail','30120222_1')")

    links=provider_relationships(con,"catalog:captures:17")
    build_links=[row for row in links if row.get("relationship")=="CAPTURE_CLIENT_BUILD"]
    assert len(build_links)==1,build_links
    assert build_links[0]["target_node"]=="catalog:identity_snapshots:client:2022",build_links
    assert build_links[0]["target_type"]=="CLIENT_SNAPSHOT",build_links
    assert build_links[0]["provider_native"] is True,build_links

    # A build string shared by more than one client snapshot is not a unique identity bridge.
    con.execute("INSERT INTO identity_snapshots VALUES('client:2022-copy','30120222_1')")
    ambiguous=provider_relationships(con,"catalog:captures:17")
    assert not [row for row in ambiguous if row.get("relationship")=="CAPTURE_CLIENT_BUILD"],ambiguous
    con.close()


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

        path = feature_trace.entity_implementation_path(g, source, "200")
        assert path and path["canonical_mapped"] is True, path
        assert path["canonical_root"] == "entity:server-id:200", path
        g.close()

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

    _assert_wiki_mapping_target_closure()
    _assert_capture_client_build_closure()
    test_generic_nm_trace_reaches_drop_rows_and_items()
    test_drop_row_composite_identity_is_stable_and_navigable()
    print("server catalog canonical identity sync + Feature Trace closure self-test: PASS")


if __name__ == "__main__":
    main()
