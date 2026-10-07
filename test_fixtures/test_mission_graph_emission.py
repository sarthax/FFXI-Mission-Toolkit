#!/usr/bin/env python3
"""Mission source extraction -> canonical graph emission regression."""
from __future__ import annotations

from pathlib import Path
from tempfile import NamedTemporaryFile

from workbench.devtools.features import trace as feature_trace
from workbench.core import graph as graph_store
from workbench.plugins.domain.mission_graph_emit import (
    extract_and_project_lsb_mission,
    persist_mission_graph,
    project_mission_graph,
)
from workbench.plugins.domain.mission_state_machine import (
    DependencyGate,
    MissionState,
    MissionStateMachine,
    MissionTransition,
    StateCondition,
    TransitionEffect,
)


LUA=r'''
helper = function(player)
    player:messageSpecial(100)
end

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
                    helper(player)
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
    metrics=projection.feature.metadata["extraction_metrics"]
    assert metrics["source_handler_count"]>=metrics["modeled_source_handler_count"],metrics
    assert metrics["event_chains"]>=1,metrics
    assert projection.evidence
    event_entities=[e for e in projection.entities if e.entity_type=="MISSION_EVENT"]
    assert len(event_entities)==1,event_entities
    assert event_entities[0].metadata["zone"]=="MISAREAUX_COAST"
    assert event_entities[0].metadata["actor"]=="_0p2"
    assert event_entities[0].metadata["event_id"]==6
    assert event_entities[0].entity_id=="server-event:lsb:MISAREAUX_COAST:_0p2:6"
    assert "feature_id" not in event_entities[0].metadata
    actor_entities=[e for e in projection.entities if e.entity_type=="SERVER_ACTOR"]
    assert len(actor_entities)==1 and actor_entities[0].display_name=="_0p2"
    relationships={e.relationship for e in projection.edges}
    assert {"HAS_STATE","HAS_TRANSITION","FROM_STATE","TO_STATE","TRIGGERED_BY_EVENT","EVENT_ACTOR","REQUIRES","AFFECTS","CALLS_HELPER"}.issubset(relationships),relationships
    assert any(e.target_node=="key_item:MISTMELT" and e.relationship=="AFFECTS" for e in projection.edges)
    shared_ki=next(e for e in projection.entities if e.entity_id=="key_item:MISTMELT")
    assert shared_ki.metadata["scope"]=="shared" and "feature_id" not in shared_ki.metadata
    scoped_status=next(e for e in projection.entities if e.entity_id=="mission-subject:mission:test:ancient-vows-shape:mission_var:Status")
    assert scoped_status.metadata["scope"]=="feature" and scoped_status.metadata["feature_id"]=="mission:test:ancient-vows-shape"
    assert any(e.target_node==scoped_status.entity_id and e.relationship=="REQUIRES" for e in projection.edges)
    source_evidence=[e for e in projection.evidence if e.evidence_type=="SOURCE_CODE"]
    assert source_evidence and ":L" in source_evidence[0].location
    helper_entity=next(e for e in projection.entities if e.entity_type=="MISSION_HELPER")
    assert helper_entity.entity_id=="mission-helper:mission:test:ancient-vows-shape:helper",helper_entity
    assert any(e.relationship=="CALLS_HELPER" and e.target_node==helper_entity.entity_id for e in projection.edges)

    second=extract_and_project_lsb_mission(
        LUA,
        feature_id="mission:test:other-feature",
        source_path="scripts/missions/cop/other.lua",
        source_snapshot_id="snapshot:lsb:test",
    )
    first_event=next(e.entity_id for e in projection.entities if e.entity_type=="MISSION_EVENT")
    second_event=next(e.entity_id for e in second.entities if e.entity_type=="MISSION_EVENT")
    assert first_event==second_event  # same source+zone+actor+CSID identity is reusable
    first_status={e.entity_id for e in projection.entities if e.entity_type=="MISSION_STATE_CHANNEL"}
    second_status={e.entity_id for e in second.entities if e.entity_type=="MISSION_STATE_CHANNEL"}
    assert first_status and second_status and first_status.isdisjoint(second_status)

    ordered_machine=MissionStateMachine(
        "machine:post-effect",
        "mission:test:post-effect",
        (MissionState("source:any","Source state"),),
        (
            MissionTransition(
                "finish","source:any","source:any","EVENT_FINISH",
                effects=(
                    TransitionEffect("SET_CHANNEL","mission_status:A",14),
                    TransitionEffect("COMPLETE","mission"),
                ),
                confidence="INFERRED",
                post_effect_gate=DependencyGate(
                    "all-paths","ALL",
                    (
                        StateCondition("mission_status:A","EQ",14),
                        StateCondition("mission_status:B","EQ",14),
                    ),
                ),
            ),
        ),
        ("source:any",),
    )
    ordered_projection=project_mission_graph(
        ordered_machine,
        source_path="scripts/missions/test_post_effect.lua",
        source_snapshot_id="snapshot:lsb:test",
    )
    ordered_transition=next(
        e for e in ordered_projection.entities if e.entity_type=="MISSION_TRANSITION"
    )
    assert ordered_transition.metadata["post_effect_gate"]["logic"]=="ALL"
    assert {c["subject"] for c in ordered_transition.metadata["post_effect_gate"]["conditions"]}=={
        "mission_status:A","mission_status:B"
    }
    post_edges=[
        e for e in ordered_projection.edges
        if e.source_node==ordered_transition.entity_id and e.relationship=="REQUIRES"
        and (e.notes or "").startswith("post-effect ")
    ]
    assert {e.target_node for e in post_edges}=={
        "mission-subject:mission:test:post-effect:mission_status:A",
        "mission-subject:mission:test:post-effect:mission_status:B",
    },post_edges

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
