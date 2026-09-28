#!/usr/bin/env python3
"""Mission source extraction -> canonical graph emission regression."""
from __future__ import annotations

from pathlib import Path
from tempfile import NamedTemporaryFile

import feature_trace
from workbench.core import graph as graph_store
from workbench.plugins.domain.mission_graph_emit import (
    extract_and_project_lsb_mission,
    persist_mission_graph,
)


LUA=r'''
return Mission:new(xi.mission.log_id.COP, xi.mission.id.cop.ANCIENT_VOWS, {
    [xi.zone.MISAREAUX_COAST] = {
        ['_0p2'] = {
            onTrigger = function(player, npc)
                if mission:getVar(player, 'Status') == 0 then
                    return mission:progressEvent(6)
                end
            end,

            onEventFinish = {
                [6] = function(player, csid, option, npc)
                    mission:setVar(player, 'Status', 1)
                    npcUtil.giveKeyItem(player, xi.keyItem.MISTMELT)
                end,
            },
        },
    },
})
'''


def main():
    projection=extract_and_project_lsb_mission(
        LUA,
        feature_id="mission:test:ancient-vows-shape",
        feature_name="Ancient Vows Shape",
        source_path="scripts/missions/cop/2_5_Ancient_Vows.lua",
        source_snapshot_id="snapshot:lsb:test",
    )
    assert projection.feature.feature_id=="mission:test:ancient-vows-shape"
    assert projection.artifact.path=="scripts/missions/cop/2_5_Ancient_Vows.lua"
    assert projection.implementation.status=="DISCOVERED"
    assert projection.evidence
    event_entities=[e for e in projection.entities if e.entity_type=="MISSION_EVENT"]
    assert len(event_entities)==1,event_entities
    assert event_entities[0].metadata["zone"]=="MISAREAUX_COAST"
    assert event_entities[0].metadata["actor"]=="_0p2"
    assert event_entities[0].metadata["event_id"]==6
    assert event_entities[0].entity_id=="server-event:lsb:MISAREAUX_COAST:_0p2:6"
    actor_entities=[e for e in projection.entities if e.entity_type=="SERVER_ACTOR"]
    assert len(actor_entities)==1 and actor_entities[0].display_name=="_0p2"
    relationships={e.relationship for e in projection.edges}
    assert {"HAS_STATE","HAS_TRANSITION","FROM_STATE","TO_STATE","TRIGGERED_BY_EVENT","EVENT_ACTOR","REQUIRES","AFFECTS"}.issubset(relationships),relationships
    assert any(e.target_node=="key_item:MISTMELT" and e.relationship=="AFFECTS" for e in projection.edges)
    assert any(e.target_node=="mission-subject:mission:test:ancient-vows-shape:mission_var:Status" and e.relationship=="REQUIRES" for e in projection.edges)
    source_evidence=[e for e in projection.evidence if e.evidence_type=="SOURCE_CODE"]
    assert source_evidence and ":L" in source_evidence[0].location

    with NamedTemporaryFile(suffix=".db") as tmp:
        con=graph_store.init_db(Path(tmp.name))
        persist_mission_graph(con,projection)
        feature_row=con.execute("SELECT name,feature_type FROM features WHERE feature_id=?",(projection.feature.feature_id,)).fetchone()
        assert feature_row==("Ancient Vows Shape","MISSION"),feature_row
        impl=con.execute("SELECT status,path FROM implementations WHERE feature_id=?",(projection.feature.feature_id,)).fetchone()
        assert impl==("DISCOVERED","scripts/missions/cop/2_5_Ancient_Vows.lua"),impl
        relationship_count=con.execute("SELECT COUNT(*) FROM entity_relationships WHERE source_node=?",(projection.feature.feature_id,)).fetchone()[0]
        assert relationship_count>=2,relationship_count
        trace=feature_trace.trace(con,projection.feature.feature_id,3,"out")
        assert trace["root"]==projection.feature.feature_id
        traced_types={
            rep["node_type"]
            for node in trace["nodes"]
            for rep in node.get("representations",())
            if rep.get("node_type")
        }
        assert "MISSION_TRANSITION" in traced_types,traced_types
        assert any(edge["relationship"]=="TRIGGERED_BY_EVENT" for edge in trace["edges"]),trace["edges"]
        assert any(edge["relationship"]=="REQUIRES" for edge in trace["edges"]),trace["edges"]
        con.close()
    print("mission source graph emission self-test: PASS")


if __name__=="__main__":
    main()
