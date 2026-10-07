#!/usr/bin/env python3
"""Regression for snapshot-aware client ENTITY -> canonical Feature Trace graph mirroring."""
from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path

from workbench.devtools.features import trace as feature_trace
from workbench.core import graph
from workbench.core.services.client_entity_graph import (
    CLIENT_IDENTIFIER_PREFIX,
    CLIENT_REPRESENTATION_RELATIONSHIP,
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
            ("npc:supply-officer","npcid","2002","entity-profile"),
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

        # A single snapshot-local numeric id claimed by two different semantic identities is
        # independently ambiguous and must also be withheld.
        for suffix in ("A","B"):
            upsert_record(con,IdentityRecord(
                record_id=f"identity:client:new:ENTITY:{ZONE}:4001:{suffix}",
                snapshot_id="client:new",namespace="ENTITY",
                semantic_key=semantic_entity_key(
                    zone_key=ZONE,semantic_identity=f"NPC:NUMERIC_COLLISION_{suffix}"
                ),
                numeric_id=4001,zone_key=ZONE,confidence="HIGH",
                metadata={"semantic_identity":f"NPC:NUMERIC_COLLISION_{suffix}"},
            ))
        con.commit()

        result=sync_client_entity_graph(con)
        assert result["status"]=="OK",result
        assert result["semantic_entities"]==1,result
        assert result["reused_roots"]==1,result
        assert result["ambiguous_semantics"]==1,result
        assert result["ambiguous_numeric_representations"]==2,result
        assert con.execute(
            "SELECT COUNT(*) FROM entity_identifiers WHERE identifier_value='4001'"
        ).fetchone()[0]==0

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

        # Drifted client IDs are still one name-addressable Implementation Path when every
        # representation maps to the same explicit canonical root.
        named_path=feature_trace.entity_implementation_path(con,con,"SUPPLY_OFFICER")
        assert named_path is not None,named_path
        assert named_path["canonical_root"]=="npc:supply-officer",named_path
        assert named_path["numeric_ids"]==[1001,2002],named_path

        # The canonical root has evidence-bearing graph edges back to the exact client identity
        # records, so Feature Trace can drill into snapshot provenance instead of stopping at IDs.
        rep_edges=con.execute(
            """SELECT target_node,evidence_id,source_snapshot_id
               FROM entity_relationships
               WHERE source_node='npc:supply-officer' AND relationship=?
               ORDER BY source_snapshot_id""",
            (CLIENT_REPRESENTATION_RELATIONSHIP,),
        ).fetchall()
        assert len(rep_edges)==2,rep_edges
        assert all(row[0].startswith("catalog:identity_records:") for row in rep_edges),rep_edges
        assert all(row[1] for row in rep_edges),rep_edges
        traced=feature_trace.trace(con,"npc:supply-officer",1,"out",con)
        assert sum(
            1 for edge in traced["edges"]
            if edge["relationship"]==CLIENT_REPRESENTATION_RELATIONSHIP
        )==2,traced

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
            """SELECT COUNT(*) FROM entity_relationships
               WHERE relationship=? AND source_snapshot_id='client:old'""",
            (CLIENT_REPRESENTATION_RELATIONSHIP,),
        ).fetchone()[0]==0
        assert con.execute(
            """SELECT COUNT(*) FROM entity_relationships
               WHERE relationship=? AND source_snapshot_id='client:new'""",
            (CLIENT_REPRESENTATION_RELATIONSHIP,),
        ).fetchone()[0]==1
        assert con.execute(
            """SELECT COUNT(*) FROM entity_identifiers
               WHERE entity_id='npc:supply-officer'
                 AND identifier_type='npcid' AND identifier_value='2002'"""
        ).fetchone()[0]==1

        source.close(); con.close()

    print("client entity canonical graph mirror self-test: PASS")


if __name__=="__main__":
    main()
