#!/usr/bin/env python3
"""Regression for the reusable multi-zone progression / hunt framework."""
from workbench.plugins.domain import PluginContext, default_registry
from workbench.plugins.domain.multizone_progression import (
    MultiZoneProgression,
    ProgressionGate,
    ProgressionObjective,
    ProgressionStage,
    analyze_progression,
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
