#!/usr/bin/env python3
"""Stress/regression guards for high-volume capture, trace, and package paths."""
from __future__ import annotations

import sqlite3
from workbench.captures.ingestion import build_index as bci
from workbench.devtools.features import trace as feature_trace
from workbench.core import graph
from workbench.core.schema import DependencyEdge, MigrationAction
from workbench.core.services import packet_correlation
from workbench.core.services import raw_packet_ingest
from workbench.migrations.package_plan import build_package_plan


def test_raw_packet_sequence_bypass():
    con = sqlite3.connect(":memory:")
    bci.init_db(con)
    original = raw_packet_ingest._existing_seq
    try:
        def fail_lookup(*_args, **_kwargs):
            raise AssertionError("existing-seq lookup should not run when seq is supplied")
        raw_packet_ingest._existing_seq = fail_lookup
        raw_packet_ingest.insert_raw_packet(
            con, 1,
            ts=None,
            direction="incoming",
            opcode=0x00E,
            raw_hex="0E083412AABBCCDD",
            source_format="fixture",
            source_native_id="fixture:1",
            filename="fixture.log",
            source_sha256="0" * 64,
            locator_basis="block",
            seq=0,
        )
    finally:
        raw_packet_ingest._existing_seq = original
    assert con.execute("SELECT COUNT(*) FROM capture_raw_packets").fetchone()[0] == 1
    indexes = {row[1] for row in con.execute("PRAGMA index_list(capture_raw_packets)")}
    assert "idx_capture_raw_packet_source" in indexes
    con.close()


def test_packeteer_offset_helper():
    text = "Aé中B\nsecond line\n"
    positions = [0, 1, 2, 3, 4, len(text)]
    offsets = raw_packet_ingest._utf8_offsets_for_positions(text, positions)
    for pos in positions:
        assert offsets[pos] == len(text[:pos].encode("utf-8")), (pos, offsets[pos])


def test_same_source_correlation_does_not_pairwise_expand():
    # This is intentionally large enough that the former nested same-source comparison loop
    # would perform tens of millions of rejected comparisons.
    items = []
    for i in range(8000):
        items.append({
            "kind": packet_correlation.RAW,
            "ref": f"raw-packet:{i}",
            "raw_hex": "0E083412AABBCCDD",
            "source_format": "packetviewer",
            "source_native_id": f"pv:{i}",
            "opcode_norm": "0x00E",
            "direction_norm": "incoming",
        })
    rows = {
        packet_correlation.RAW: items,
        packet_correlation.EVENTVIEW: [],
        packet_correlation.IDVIEW: [],
        packet_correlation.VIDEO: [],
    }
    packet_correlation._raw_equivalence(None, 1, rows)


def _action(i: int):
    return MigrationAction(
        action_id=f"a:{i:05d}",
        migration_id="migration:scale",
        action="IMPLEMENT",
        artifact_id=f"artifact:{i:05d}",
        status="AUTO_MIGRATABLE",
    )


def test_large_package_chain():
    count = 3000
    actions = [_action(i) for i in range(count)]
    deps = [
        DependencyEdge(
            edge_id=f"e:{i:05d}",
            source_node=f"artifact:{i:05d}",
            target_node=f"artifact:{i-1:05d}",
            relationship="REQUIRES",
            confidence="VERIFIED",
        )
        for i in range(1, count)
    ]
    plan = build_package_plan(actions, deps)
    assert len(plan.ordered_actions) == count
    assert plan.ordered_actions[0].action_id == "a:00000"
    assert plan.ordered_actions[-1].action_id == f"a:{count-1:05d}"
    assert not plan.cycle_action_ids


def test_feature_trace_node_budget():
    con = sqlite3.connect(":memory:")
    con.executescript(graph.SCHEMA)
    con.execute(
        "INSERT OR REPLACE INTO entities(entity_id,entity_type,display_name,metadata_json) VALUES(?,?,?,?)",
        ("root", "FEATURE", "root", "{}"),
    )
    for i in range(20):
        node = f"n:{i}"
        con.execute(
            "INSERT OR REPLACE INTO entities(entity_id,entity_type,display_name,metadata_json) VALUES(?,?,?,?)",
            (node, "TEST", node, "{}"),
        )
        con.execute(
            "INSERT OR REPLACE INTO entity_relationships VALUES(?,?,?,?,?,?,?,?,?)",
            (f"edge:{i}", "root", node, "REFERENCES", None, "VERIFIED", "DISCOVERED", "{}", None),
        )
    con.commit()
    traced = feature_trace.trace(con, "root", 3, "out", max_nodes=5)
    assert traced["truncated"] is True
    assert traced["max_nodes"] == 5
    assert len(traced["nodes"]) == 5
    con.close()


def main():
    test_raw_packet_sequence_bypass()
    test_packeteer_offset_helper()
    test_same_source_correlation_does_not_pairwise_expand()
    test_large_package_chain()
    test_feature_trace_node_budget()
    print("High-volume scaling guards: PASS")


if __name__ == "__main__":
    main()
