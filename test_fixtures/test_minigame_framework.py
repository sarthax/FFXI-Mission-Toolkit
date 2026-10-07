#!/usr/bin/env python3
"""Regression for the reusable minigame / puzzle framework."""
from pathlib import Path
from tempfile import NamedTemporaryFile

from workbench.devtools.features import trace as feature_trace
from workbench.core import graph as graph_store
from workbench.core.schema import Entity, Feature
from workbench.plugins.domain import PluginContext, default_registry
from workbench.plugins.domain.minigame import (
    MinigameInteraction,
    MinigameModel,
    MinigameOutcome,
    MinigameReset,
    MinigameTimer,
    analyze_minigame,
    persist_minigame_graph,
    project_minigame_graph,
)
from workbench.plugins.domain.mission_state_machine import StateCondition, TransitionEffect


def _ready_model():
    return MinigameModel(
        "minigame:test:timed-score",
        "feature:test:timed-score",
        interactions=(
            MinigameInteraction(
                "start","Start puzzle","npc_interact",
                subject="npc:start",
                effects=(TransitionEffect("SET_VAR","minigame_var:active",1),),
                starts_timers=("round",),
                evidence_ids=("evidence:start",),
            ),
            MinigameInteraction(
                "target","Activate target","npc_interact",
                subject="object:target",
                conditions=(StateCondition("minigame_var:active","EQ",1),),
                score_delta=10,
                evidence_ids=("evidence:target",),
            ),
            MinigameInteraction(
                "finish","Submit score","npc_interact",
                subject="npc:finish",
                conditions=(StateCondition("score","GE",30),),
                effects=(TransitionEffect("SET_VAR","minigame_var:active",0),),
                cancels_timers=("round",),
            ),
        ),
        outcomes=(
            MinigameOutcome(
                "win","Puzzle cleared","win",
                conditions=(StateCondition("score","GE",30),),
                effects=(TransitionEffect("GRANT","key_item:PUZZLE_REWARD"),),
                evidence_ids=("evidence:win",),
            ),
            MinigameOutcome(
                "timeout","Time expired","timeout",
                effects=(TransitionEffect("SET_VAR","minigame_var:active",0),),
                evidence_ids=("evidence:timeout",),
            ),
        ),
        timers=(
            MinigameTimer(
                "round",60.0,expiry_outcome_ids=("timeout",),
                evidence_ids=("evidence:timer",),
            ),
        ),
        resets=(
            MinigameReset(
                "leave","Reset on exit","zone_out",
                clears_subjects=("minigame_var:active",),
                cancels_timers=("round",),
                reset_score=True,
                evidence_ids=("evidence:reset",),
            ),
        ),
        state_subjects=("minigame_var:active",),
        repeatable=True,
        metadata={"name":"Timed Score Fixture"},
    )


def main():
    model=_ready_model()
    assert not model.validate(),model.validate()
    assert model.interactions[0].trigger=="NPC_INTERACT",model.interactions[0]
    assert model.outcomes[0].result=="WIN",model.outcomes[0]
    assert model.resets[0].trigger=="ZONE_OUT",model.resets[0]

    analysis=analyze_minigame(model)
    assert analysis.status=="STRUCTURALLY_READY",analysis
    assert not analysis.structural_gaps,analysis
    assert analysis.interaction_trigger_counts=={"NPC_INTERACT":3},analysis
    assert analysis.result_counts=={"TIMEOUT":1,"WIN":1},analysis
    assert analysis.score_rule_count==1,analysis
    assert analysis.score_reset_present is True,analysis
    assert analysis.has_win and analysis.has_loss,analysis
    assert analysis.mutable_state_subjects==("minigame_var:active",),analysis
    assert analysis.reset_state_coverage==("minigame_var:active",),analysis
    assert not analysis.missing_reset_subjects,analysis
    assert analysis.timer_reset_coverage==("round",),analysis
    assert not analysis.missing_reset_timers,analysis
    timer=analysis.timer_lifecycles[0]
    assert timer.timer_id=="round" and timer.started and timer.cancellable, timer
    assert timer.expiry_outcomes==("timeout",) and timer.structurally_closed,timer

    projection=project_minigame_graph(
        model,feature_name="Timed Score Fixture",source_snapshot_id="snapshot:test"
    )
    assert projection.feature.feature_type=="MINIGAME",projection.feature
    rels={edge.relationship for edge in projection.edges}
    assert {
        "HAS_TIMER","HAS_INTERACTION","HAS_OUTCOME","HAS_RESET",
        "STARTS_TIMER","CANCELS_TIMER","EXPIRES_TO","REFERENCES",
        "REQUIRES","AFFECTS","RESETS",
    } <= rels,rels
    assert any(
        edge.relationship=="EXPIRES_TO"
        and edge.target_node=="minigame-outcome:feature:test:timed-score:timeout"
        for edge in projection.edges
    ),projection.edges
    state_entity=next(
        entity for entity in projection.entities
        if entity.entity_id=="minigame-subject:feature:test:timed-score:minigame_var:active"
    )
    assert state_entity.metadata["scope"]=="feature",state_entity
    reward=next(
        entity for entity in projection.entities
        if entity.entity_id=="key_item:PUZZLE_REWARD"
    )
    assert reward.metadata["scope"]=="shared",reward
    assert any(
        edge.relationship=="HAS_INTERACTION"
        and edge.target_node=="minigame-interaction:feature:test:timed-score:start"
        and edge.evidence_id=="evidence:start"
        for edge in projection.edges
    ),projection.edges

    with NamedTemporaryFile(suffix=".db") as tmp:
        con=graph_store.init_db(Path(tmp.name))
        graph_store.insert_record(con,Feature(
            model.feature_id,"Existing Feature","MISSION","mission",
            status="DISCOVERED",metadata={"preserve":True},
        ))
        graph_store.insert_record(con,Entity(
            "object:target","CANONICAL_TARGET","Existing Target",{"preserve":True},
        ))
        con.commit()
        persist_minigame_graph(con,projection)
        feature_row=con.execute(
            "SELECT name,feature_type FROM features WHERE feature_id=?",
            (model.feature_id,),
        ).fetchone()
        assert feature_row==("Existing Feature","MISSION"),feature_row
        target_row=con.execute(
            "SELECT entity_type,display_name FROM entities WHERE entity_id='object:target'"
        ).fetchone()
        assert target_row==("CANONICAL_TARGET","Existing Target"),target_row

        trace=feature_trace.trace(con,model.feature_id,3,"out")
        traced_types={
            rep["node_type"]
            for node in trace["nodes"]
            for rep in node.get("representations",())
            if rep.get("node_type")
        }
        assert "MINIGAME_INTERACTION" in traced_types,traced_types
        assert "MINIGAME_TIMER" in traced_types,traced_types
        assert "MINIGAME_OUTCOME" in traced_types,traced_types
        assert any(edge["relationship"]=="STARTS_TIMER" for edge in trace["edges"]),trace["edges"]
        con.close()

    registry=default_registry()
    plugin=registry.get("framework.minigame")
    context=PluginContext(feature_id=model.feature_id,metadata={"minigame_model":model})
    assert plugin.identify(context)
    findings=plugin.discover_dependencies(context)
    summary=next(row for row in findings if row.finding_type=="MINIGAME_STRUCTURE")
    assert summary.status=="STRUCTURALLY_READY",summary
    assert "evidence:timer" in summary.evidence_ids,summary
    assert not any(row.finding_type.endswith("_GAP") for row in findings),findings
    report=plugin.report(context)
    assert report["minigame"]["status"]=="STRUCTURALLY_READY",report
    assert report["minigame"]["score_rule_count"]==1,report
    assert report["minigame"]["timer_lifecycles"][0]["structurally_closed"] is True,report

    partial=MinigameModel(
        "minigame:test:partial","feature:test:partial",
        interactions=(
            MinigameInteraction(
                "start","Start","NPC_INTERACT",
                effects=(TransitionEffect("SET_VAR","minigame_var:active",1),),
                starts_timers=("round",),score_delta=1,
            ),
        ),
        outcomes=(MinigameOutcome("win","Win","WIN"),),
        timers=(MinigameTimer("round",30.0),),
        resets=(
            MinigameReset(
                "bad-reset","Bad reset","ZONE_OUT",
                clears_subjects=(),cancels_timers=(),reset_score=False,
            ),
        ),
        state_subjects=("minigame_var:active",),
        repeatable=True,
    )
    partial_analysis=analyze_minigame(partial)
    assert partial_analysis.status=="PARTIAL",partial_analysis
    assert "timer_lifecycle_open:round" in partial_analysis.structural_gaps,partial_analysis
    assert "reset_state_incomplete" in partial_analysis.structural_gaps,partial_analysis
    assert "reset_timer_incomplete" in partial_analysis.structural_gaps,partial_analysis
    assert "score_reset_missing" in partial_analysis.structural_gaps,partial_analysis
    assert "loss_or_timeout_outcome_missing" in partial_analysis.structural_gaps,partial_analysis
    partial_findings=plugin.discover_dependencies(
        PluginContext(feature_id=partial.feature_id,metadata={"minigame_model":partial})
    )
    assert any(row.finding_type=="TIMER_LIFECYCLE_GAP" for row in partial_findings),partial_findings
    assert any(row.finding_type=="RESET_COVERAGE_GAP" for row in partial_findings),partial_findings

    invalid=MinigameModel(
        "minigame:test:invalid","feature:test:invalid",
        interactions=(
            MinigameInteraction("start","Start","NPC_INTERACT",starts_timers=("missing",)),
        ),
        outcomes=(MinigameOutcome("win","Win","WIN"),),
    )
    invalid_analysis=analyze_minigame(invalid)
    assert invalid_analysis.status=="INVALID",invalid_analysis
    assert "start: unknown timer missing" in invalid_analysis.validation_errors,invalid_analysis

    one_shot=MinigameModel(
        "minigame:test:oneshot","feature:test:oneshot",
        interactions=(MinigameInteraction("act","Act","NPC_INTERACT",score_delta=1),),
        outcomes=(
            MinigameOutcome("win","Win","WIN"),
            MinigameOutcome("loss","Loss","LOSS"),
        ),
        repeatable=False,
    )
    one_shot_analysis=analyze_minigame(one_shot)
    assert one_shot_analysis.status=="STRUCTURALLY_READY",one_shot_analysis
    assert not one_shot_analysis.missing_reset_subjects,one_shot_analysis
    assert "score_reset_missing" not in one_shot_analysis.structural_gaps,one_shot_analysis

    print("minigame framework self-test: PASS")


if __name__=="__main__":
    main()
