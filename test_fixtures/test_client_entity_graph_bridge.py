#!/usr/bin/env python3
"""Regression for snapshot-aware client ENTITY -> Feature Trace graph mirroring."""
from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path

import feature_trace
from workbench.core import graph
from workbench.core.services.client_entity_graph import (
    IDENTIFIER_TYPE,
    RELATIONSHIP,
    SEMANTIC_IDENTIFIER_TYPE,
    sync_client_entity_graph,
)
from workbench.core.services.identity_resolver import (
    IdentitySnapshot,
    ingest_entity_identity_records,
    register_snapshot,
)


def main() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "workbench.db"
        con = graph.init_db(db)

        for snapshot in ("client:new", "client:old", "client:reuse"):
            register_snapshot(
                con,
                IdentitySnapshot(snapshot, "CLIENT", family="RETAIL", version=snapshot),
            )

        ingest_entity_identity_records(
            con,
            snapshot_id="client:new",
            zone_key="TEST_ZONE",
            entities={2002: "NPC:SUPPLY_OFFICER"},
            evidence_id_prefix="client-entity:new",
            metadata={"identity_basis": "client_entity_name_table"},
        )
        ingest_entity_identity_records(
            con,
            snapshot_id="client:old",
            zone_key="TEST_ZONE",
            entities={1001: "NPC:SUPPLY_OFFICER"},
            evidence_id_prefix="client-entity:old",
            metadata={"identity_basis": "client_entity_name_table"},
        )

        new_sync = sync_client_entity_graph(con, snapshot_id="client:new")
        old_sync = sync_client_entity_graph(con, snapshot_id="client:old")
        assert new_sync["created_roots"] == 1, new_sync
        assert old_sync["reused_roots"] == 1, old_sync

        semantic_roots = con.execute(
            """SELECT entity_id FROM entity_identifiers
               WHERE identifier_type=?""",
            (SEMANTIC_IDENTIFIER_TYPE,),
        ).fetchall()
        assert len(semantic_roots) == 1, semantic_roots
        root = semantic_roots[0][0]

        ids = con.execute(
            """SELECT identifier_value,source_snapshot_id
               FROM entity_identifiers
               WHERE entity_id=? AND identifier_type=?
               ORDER BY identifier_value""",
            (root, IDENTIFIER_TYPE),
        ).fetchall()
        assert ids == [("1001", "client:old"), ("2002", "client:new")], ids

        assert feature_trace.canonical_entity_root(con, 1001) == root
        assert feature_trace.canonical_entity_root(con, 2002) == root

        trace = feature_trace.trace(con, root, 1, "both", con)
        rep_edges = [e for e in trace["edges"] if e["relationship"] == RELATIONSHIP]
        assert len(rep_edges) == 2, rep_edges
        assert all(e["target_node"].startswith("catalog:identity_records:") for e in rep_edges)

        path = feature_trace.entity_implementation_path(con, con, "2002")
        assert path and path["canonical_mapped"] is True, path
        assert path["canonical_root"] == root, path

        # Numeric reuse by a different semantic entity in another snapshot must not be guessed.
        ingest_entity_identity_records(
            con,
            snapshot_id="client:reuse",
            zone_key="TEST_ZONE",
            entities={2002: "NPC:DIFFERENT_ENTITY"},
            evidence_id_prefix="client-entity:reuse",
            metadata={"identity_basis": "client_entity_name_table"},
        )
        reuse_sync = sync_client_entity_graph(con, snapshot_id="client:reuse")
        assert reuse_sync["created_roots"] == 1, reuse_sync
        assert feature_trace.canonical_entity_root(con, 2002) is None

        # Reconciliation is snapshot-scoped: removing old snapshot ENTITY rows removes only its
        # numeric representation/edge while preserving the semantic root and the new snapshot.
        con.execute(
            "DELETE FROM identity_records WHERE snapshot_id='client:old' AND namespace='ENTITY'"
        )
        stale = sync_client_entity_graph(con, snapshot_id="client:old")
        assert stale["removed_identifiers"] == 1, stale
        assert stale["removed_relationships"] == 1, stale
        assert con.execute(
            """SELECT COUNT(*) FROM entity_identifiers
               WHERE identifier_type=? AND source_snapshot_id='client:old'""",
            (IDENTIFIER_TYPE,),
        ).fetchone()[0] == 0
        assert con.execute(
            """SELECT COUNT(*) FROM entity_identifiers
               WHERE identifier_type=? AND source_snapshot_id='client:new'""",
            (IDENTIFIER_TYPE,),
        ).fetchone()[0] == 1

        con.close()

    print("client entity graph bridge self-test: PASS")


if __name__ == "__main__":
    main()
