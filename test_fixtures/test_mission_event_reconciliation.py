#!/usr/bin/env python3
"""Mission event reconciliation regression."""
from __future__ import annotations

import sqlite3
from pathlib import Path
from tempfile import NamedTemporaryFile

from workbench.core import graph as graph_store
from workbench.core.services.identity_resolver import (
    IdentityRecord,
    IdentitySnapshot,
    ensure_schema,
    register_snapshot,
    semantic_entity_key,
    upsert_record,
)
from workbench.plugins.domain.mission_event_reconcile import (
    persist_event_reconciliation,
    reconcile_feature_events,
)
from workbench.plugins.domain.mission_graph_emit import (
    persist_mission_graph,
    project_mission_graph,
)
from workbench.plugins.domain.mission_state_machine import (
    EventIdentity,
    MissionState,
    MissionStateMachine,
    MissionTransition,
)


def _machine():
    return MissionStateMachine(
        "machine:mission:test:event-reconcile",
        "mission:test:event-reconcile",
        (MissionState("source:any","Source state"),),
        (
            MissionTransition(
                "event-149","source:any","source:any","NPC_INTERACT",
                event=EventIdentity("SOUTHERN_SAN_DORIA_S",149,"Raustigne"),
                confidence="VERIFIED",
                metadata={"source_lines":(10,12)},
            ),
        ),
        ("source:any",),
        metadata={"extractor":"fixture"},
    )


def main():
    with NamedTemporaryFile(suffix=".db") as tmp:
        con=graph_store.init_db(Path(tmp.name))
        ensure_schema(con)
        projection=project_mission_graph(
            _machine(),
            source_path="scripts/missions/wotg/25_The_Will_of_the_World.lua",
            source_snapshot_id="server:lsb:test",
            source_family="LSB",
            feature_name="Event Reconciliation Fixture",
        )
        persist_mission_graph(con,projection)

        register_snapshot(con,IdentitySnapshot("client:retail:test","CLIENT","RETAIL","test"))
        upsert_record(con,IdentityRecord(
            "identity:client:retail:test:ENTITY:SOUTHERN_SAN_DORIA_S:16974347",
            "client:retail:test","ENTITY",
            semantic_entity_key(zone_key="SOUTHERN_SAN_DORIA_S",semantic_identity="Raustigne"),
            "16974347","SOUTHERN_SAN_DORIA_S",
            confidence="HIGH",
            metadata={"semantic_identity":"Raustigne","identity_basis":"client_entity_name_table"},
        ))
        upsert_record(con,IdentityRecord(
            "identity:client:retail:test:EVENT:SOUTHERN_SAN_DORIA_S:16974347:149",
            "client:retail:test","EVENT","EVENT|fixture","149",
            "SOUTHERN_SAN_DORIA_S","16974347",
            content_fingerprint="fixture",
            evidence_id="client-event:test:149",
            confidence="HIGH",
            metadata={"fingerprint_basis":"event_structure"},
        ))
        con.commit()

        catalog=sqlite3.connect(":memory:")
        catalog.execute("CREATE TABLE npc_event_refs (source TEXT, zone_name TEXT, npc_script TEXT, csid INTEGER)")
        catalog.execute(
            "INSERT INTO npc_event_refs VALUES (?,?,?,?)",
            ("lsb","SOUTHERN_SAN_DORIA_S","Raustigne",149),
        )

        result=reconcile_feature_events(con,projection.feature.feature_id,catalog_con=catalog)
        assert len(result)==1,result
        event=result[0]
        assert event.source_ref_status=="EXACT",event
        assert event.source_ref_node=="catalog:npc_event_refs:source=lsb&zone_name=SOUTHERN_SAN_DORIA_S&npc_script=Raustigne&csid=149"
        assert len(event.client_checks)==1,event.client_checks
        check=event.client_checks[0]
        assert check.status=="EXACT",check
        assert check.actor_numeric_id=="16974347",check
        assert check.event_record_id=="identity:client:retail:test:EVENT:SOUTHERN_SAN_DORIA_S:16974347:149"
        written=persist_event_reconciliation(con,result)
        assert written==2,written
        edges=con.execute(
            "SELECT relationship,target_node,confidence FROM entity_relationships WHERE source_node=? ORDER BY relationship",
            (event.event_node,),
        ).fetchall()
        assert ("SUPPORTED_BY_SOURCE_REF",event.source_ref_node,"VERIFIED") in edges,edges
        assert any(row[0]=="SUPPORTED_BY_CLIENT_EVENT" and row[2]=="HIGH" for row in edges),edges

        # A second independently claimed actor identity makes actor selection ambiguous.
        upsert_record(con,IdentityRecord(
            "identity:client:retail:test:ENTITY:SOUTHERN_SAN_DORIA_S:16979999",
            "client:retail:test","ENTITY",
            semantic_entity_key(zone_key="SOUTHERN_SAN_DORIA_S",semantic_identity="Raustigne"),
            "16979999","SOUTHERN_SAN_DORIA_S",
            confidence="HIGH",
            metadata={"semantic_identity":"Raustigne","identity_basis":"fixture_duplicate"},
        ))
        con.commit()
        ambiguous=reconcile_feature_events(con,projection.feature.feature_id,catalog_con=catalog)
        ambiguous_check=ambiguous[0].client_checks[0]
        assert ambiguous_check.status=="ACTOR_AMBIGUOUS",ambiguous_check
        assert ambiguous_check.event_record_id is None

        catalog.close()
        con.close()

    print("mission event reconciliation self-test: PASS")


if __name__=="__main__":
    main()
