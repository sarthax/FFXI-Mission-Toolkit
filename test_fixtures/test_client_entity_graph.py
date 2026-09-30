#!/usr/bin/env python3
"""Regression for snapshot-aware client ENTITY -> canonical Feature Trace graph mirroring."""
from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path

import feature_trace
from workbench.core import graph
from workbench.core.services.client_entity_graph import (
    CLIENT_IDENTIFIER_PREFIX,
    sync_client_entity_graph,
)
from workbench.core.services.identity_resolver import (
    IdentityRecord,
    IdentitySnapshot,
    ingest_entity_identity_records,
    register_snapshot,
    semantic_entity_key,
    upsert_record,
)
from workbench.core.services.server_catalog_identity import sync_server_catalog_entities


ZONE = "NORTH_GUSTABERG_S"


def main():
    with tempfile.TemporaryDirectory() as td:
        root=Path(td)
        db=root/"workbench.db"
        con=graph.init_db(db)

        register_snapshot(con,IdentitySnapshot("client:new","CLIENT","RETAIL","new"))
        register_snapshot(con,IdentitySnapshot("client:old","CLIENT","RETAIL","old"))

        # Existing server/evidence root for the current representation must win.
        con.execute(
            "INSERT INTO entities(entity_id,entity_type,display_name,metadata_json) VALUES(?,?,?,?)",
            ("npc:supply-officer","NPC","Supply Officer","{}"),
        )
        con.execute(
            """INSERT INTO entity_identifiers(
                   entity_id,identifier_type,identifier_value,source_snapshot_id
               ) VALUES(?,?,?,?)""",
            ("npc:supply-officer","npcid","2002","server-catalog"),
        )

        ingest_entity_identity_records(
            con,snapshot_id="client:new",zone_key=ZONE,
            entities={2002:"NPC:SUPPLY_OFFICER"},
            evidence_id_prefix="client:new",confidence="HIGH",
        )
        ingest_entity_identity_records(
            con,snapshot_id="client:old",zone_key=ZONE,
            entities={1001:"NPC:SUPPLY_OFFICER"},
            evidence_id_prefix="client:old",confidence="HIGH",
        )

        # A duplicate semantic entity in one snapshot remains ambiguous and must not be mirrored.
        ambiguous_key=semantic_entity_key(zone_key=ZONE,semantic_identity="NPC:DUPLICATE")
        for numeric in (3001,3002):
            upsert_record(con,IdentityRecord(
                record_id=f"identity:client:new:ENTITY:{ZONE}:{numeric}",
                snapshot_id="client:new",namespace="ENTITY",
                semantic_key=ambiguous_key,numeric_id=numeric,zone_key=ZONE,
                confidence="HIGH",metadata={"semantic_identity":"NPC:DUPLICATE"},
            ))
        con.commit()

        result=sync_client_entity_graph(con)
        assert result["status"]=="OK",result
        assert result["semantic_entities"]==1,result
        assert result["reused_roots"]==1,result
        assert result["ambiguous_semantics"]==1,result

        rows=con.execute(
            """SELECT entity_id,identifier_type,identifier_value,source_snapshot_id
               FROM entity_identifiers
               WHERE identifier_type LIKE ?
               ORDER BY identifier_value""",
            (CLIENT_IDENTIFIER_PREFIX+"%",),
        ).fetchall()
        assert rows==[
            ("npc:supply-officer",CLIENT_IDENTIFIER_PREFIX+"client:old","1001","client:old"),
            ("npc:supply-officer",CLIENT_IDENTIFIER_PREFIX+"client:new","2002","client:new"),
        ],rows

        # Both client generations now resolve to the same canonical Feature Trace root.
        assert feature_trace.canonical_entity_root(con,2002)=="npc:supply-officer"
        assert feature_trace.canonical_entity_root(con,1001)=="npc:supply-officer"

        # A later server-catalog sync must reuse the client-mirrored root for the historical ID.
        source=sqlite3.connect(":memory:")
        source.execute("CREATE TABLE dsp_npc_list(npcid INTEGER,name TEXT)")
        source.execute("INSERT INTO dsp_npc_list VALUES(1001,'Supply Officer')")
        server=sync_server_catalog_entities(source,db)
        assert server["reused_roots"]>=1,server
        roots=con.execute(
            """SELECT DISTINCT entity_id FROM entity_identifiers
               WHERE identifier_value IN ('1001','2002')
                 AND (
                   identifier_type IN ('npcid','mobid','entity_id','numeric_entity_id')
                   OR identifier_type LIKE ?
                 )""",
            (CLIENT_IDENTIFIER_PREFIX+"%",),
        ).fetchall()
        assert roots==[("npc:supply-officer",)],roots

        # Remove the old snapshot representation and reconcile: only mirror-owned stale ID goes.
        con.execute(
            "DELETE FROM identity_records WHERE snapshot_id='client:old' AND namespace='ENTITY'"
        )
        con.commit()
        second=sync_client_entity_graph(con)
        assert second["removed_stale_identifiers"]>=2,second
        assert con.execute(
            "SELECT COUNT(*) FROM entity_identifiers WHERE identifier_type=?",
            (CLIENT_IDENTIFIER_PREFIX+"client:old",),
        ).fetchone()[0]==0
        assert con.execute(
            """SELECT COUNT(*) FROM entity_identifiers
               WHERE entity_id='npc:supply-officer'
                 AND identifier_type='npcid' AND identifier_value='2002'"""
        ).fetchone()[0]==1

        source.close(); con.close()

    print("client entity canonical graph mirror self-test: PASS")


if __name__=="__main__":
    main()
