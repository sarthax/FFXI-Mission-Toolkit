#!/usr/bin/env python3
"""Regression for the reusable multi-zone progression / hunt framework."""
from pathlib import Path
from tempfile import NamedTemporaryFile

import feature_trace
from workbench.core import graph as graph_store
from workbench.core.schema import Entity, Feature
from workbench.plugins.domain import PluginContext, default_registry
from workbench.plugins.domain.multizone_progression import (
    MultiZoneProgression,
    ProgressionGate,
    ProgressionObjective,
    ProgressionStage,
    analyze_progression,
    persist_progression_graph,
    project_progression_graph,
)
from workbench.plugins.domain.mission_state_machine import StateCondition, TransitionEffect


def _ready_model():
    objectives=(
        ProgressionObjective(
            "briefing","Receive the briefing","NPC_INTERACT",("ZONE_A",),
            subject="npc:briefing",effects=(TransitionEffect("SET_VAR","mission_var:Progress",1),),
        ),
        ProgressionObjective(
            "east_hunt","Defeat eastern targets","MOB_DEATH",("ZONE_B",),
            subject="mob:east_target",required_count=3,
            conditions=(StateCondition("mission_var:Progress","GE",1),),
        ),
        ProgressionObjective(
            "west_hunt","Defeat western targets","MOB_DEATH",("ZONE_C",),
            subject="mob:west_target",required_count=2,
            conditions=(StateCondition("mission_var:Progress","GE",1),),
        ),
        ProgressionObjective(
            "scout","Optional scouting step","ZONE_IN",("ZONE_E",),
            subject="zone:ZONE_E",optional=True,
        ),
        ProgressionObjective(
            "turn_in","Report completion","NPC_INTERACT",("ZONE_D",),
            subject="npc:turn_in",effects=(TransitionEffect("COMPLETE","mission"),),
        ),
    )
    stages=(
        ProgressionStage("briefing","Briefing",("briefing",)),
        ProgressionStage(
            "east","Eastern hunt",("east_hunt",),
            ProgressionGate("east-prereq","ALL",("briefing",)),
        ),
        ProgressionStage(
            "west","Western hunt",("west_hunt",),
            ProgressionGate("west-prereq","ALL",("briefing",)),
        ),
        ProgressionStage(
            "scout","Optional scout",("scout",),
            ProgressionGate("scout-prereq","ANY",("east","west")),
            optional=True,
        ),
        ProgressionStage(
            "turnin","Converged turn-in",("turn_in",),
            ProgressionGate("turnin-prereq","ALL",("east","west")),
        ),
    )
    return MultiZoneProgression(
        "progression:test:multizone","feature:test:multizone",
        objectives,stages,("briefing",),
        ProgressionGate("complete","ALL",("turnin",)),
    )


def main():
    model=_ready_model()
    assert not model.validate(),model.validate()
    analysis=analyze_progression(model)
    assert analysis.status=="STRUCTURALLY_READY",analysis
    assert analysis.reachable_stage_ids==("briefing","east","scout","turnin","west"),analysis
    assert not analysis.unreachable_stage_ids,analysis
    assert analysis.zone_ids==("ZONE_A","ZONE_B","ZONE_C","ZONE_D","ZONE_E"),analysis
    assert analysis.branch_stage_ids==("scout",),analysis
    assert analysis.convergence_stage_ids==("turnin",),analysis
    assert analysis.terminal_stage_ids==("scout","turnin"),analysis
    assert analysis.objective_trigger_counts["MOB_DEATH"]==2,analysis
    assert analysis.required_objective_count==4,analysis
    assert analysis.optional_objective_count==1,analysis
    assert analysis.completion_gate_satisfied_structurally is True,analysis
    assert any(
        edge.source_stage_id=="east" and edge.target_stage_id=="turnin"
        for edge in analysis.cross_zone_dependencies
    ),analysis.cross_zone_dependencies

    projection=project_progression_graph(
        model,feature_name="Progression Fixture",source_snapshot_id="snapshot:test"
    )
    assert projection.feature.feature_type=="MULTIZONE_PROGRESSION",projection.feature
    rels={edge.relationship for edge in projection.edges}
    assert {"HAS_STAGE","HAS_OBJECTIVE","LOCATED_IN","REQUIRES","AFFECTS"} <= rels,rels
    scoped_subject=next(
        entity for entity in projection.entities
        if entity.entity_id=="progression-subject:feature:test:multizone:mission_var:Progress"
    )
    assert scoped_subject.metadata["scope"]=="feature",scoped_subject
    assert any(
        edge.relationship=="REQUIRES"
        and edge.source_node=="progression-stage:feature:test:multizone:turnin"
        and edge.target_node=="progression-stage:feature:test:multizone:east"
        for edge in projection.edges
    ),projection.edges

    with NamedTemporaryFile(suffix=".db") as tmp:
        con=graph_store.init_db(Path(tmp.name))
        graph_store.insert_record(con,Feature(
            model.feature_id,"Existing Mission Feature","MISSION","mission",
            status="DISCOVERED",metadata={"preserve":True},
        ))
        graph_store.insert_record(con,Entity(
            "zone:ZONE_A","ZONE","Existing Zone A",{"preserve":True},
        ))
        con.commit()
        persist_progression_graph(con,projection)
        existing_feature=con.execute(
            "SELECT name,feature_type,metadata_json FROM features WHERE feature_id=?",
            (model.feature_id,),
        ).fetchone()
        assert existing_feature[0]=="Existing Mission Feature",existing_feature
        assert existing_feature[1]=="MISSION",existing_feature
        existing_zone=con.execute(
            "SELECT display_name,metadata_json FROM entities WHERE entity_id='zone:ZONE_A'"
        ).fetchone()
        assert existing_zone[0]=="Existing Zone A",existing_zone
        trace=feature_trace.trace(con,model.feature_id,3,"out")
        traced_types={
            rep["node_type"]
            for node in trace["nodes"]
            for rep in node.get("representations",())
            if rep.get("node_type")
        }
        assert "PROGRESSION_STAGE" in traced_types,traced_types
        assert "PROGRESSION_OBJECTIVE" in traced_types,traced_types
        assert any(edge["relationship"]=="REQUIRES" for edge in trace["edges"]),trace["edges"]
        con.close()

    registry=default_registry()
    plugin=registry.get("framework.multizone_progression")
    context=PluginContext(
        feature_id=model.feature_id,
        metadata={"progression_model":model},
    )
    assert plugin.identify(context)
    findings=plugin.discover_dependencies(context)
    summary=next(f for f in findings if f.finding_type=="PROGRESSION_STRUCTURE")
    assert summary.status=="STRUCTURALLY_READY",summary
    assert any(f.finding_type=="CROSS_ZONE_DEPENDENCY" for f in findings),findings
    report=plugin.report(context)
    assert report["progression"]["status"]=="STRUCTURALLY_READY",report
    assert report["progression"]["cross_zone_dependency_count"]>=4,report

    cyclic=MultiZoneProgression(
        "progression:test:cycle","feature:test:cycle",
        (
            ProgressionObjective("a_obj","A","NPC_INTERACT",("ZONE_A",)),
            ProgressionObjective("b_obj","B","NPC_INTERACT",("ZONE_B",)),
        ),
        (
            ProgressionStage("a","A",("a_obj",),ProgressionGate("a-pre","ALL",("b",))),
            ProgressionStage("b","B",("b_obj",),ProgressionGate("b-pre","ALL",("a",))),
        ),
    )
    cycle_analysis=analyze_progression(cyclic)
    assert cycle_analysis.status=="CYCLIC",cycle_analysis
    assert set(cycle_analysis.cycle_stage_ids)=={"a","b"},cycle_analysis

    invalid=MultiZoneProgression(
        "progression:test:invalid","feature:test:invalid",
        (ProgressionObjective("known","Known","NPC_INTERACT",("ZONE_A",)),),
        (ProgressionStage("stage","Stage",("missing",)),),
    )
    invalid_analysis=analyze_progression(invalid)
    assert invalid_analysis.status=="INVALID",invalid_analysis
    assert any("unknown objective missing" in error for error in invalid_analysis.validation_errors),invalid_analysis

    print("multi-zone progression framework self-test: PASS")


if __name__=="__main__":
    main()
