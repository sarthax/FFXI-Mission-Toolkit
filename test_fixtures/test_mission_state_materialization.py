#!/usr/bin/env python3
"""Regression for conservative mission channel-state materialization."""
from workbench.plugins.domain.mission_lsb_extract import materialize_channel_states
from workbench.plugins.domain.mission_state_machine import (
    DependencyGate,
    MissionState,
    MissionStateMachine,
    MissionTransition,
    StateCondition,
    TransitionEffect,
)


def main():
    machine=MissionStateMachine(
        "machine:materialize","mission:test:materialize",
        (MissionState("source:any","Source state"),),
        (
            MissionTransition(
                "same","source:any","source:any","PROGRESS_CHANGE",
                gate=DependencyGate("same-gate","ALL",(
                    StateCondition("mission_var:Status","EQ",1),
                )),
                effects=(TransitionEffect("SET_VAR","mission_var:Status",2),),
            ),
            MissionTransition(
                "guard-only","source:any","source:any","PROGRESS_CHANGE",
                gate=DependencyGate("guard-gate","ALL",(
                    StateCondition("mission_status:A","EQ",4),
                )),
            ),
            MissionTransition(
                "write-only","source:any","source:any","PROGRESS_CHANGE",
                effects=(TransitionEffect("SET_CHANNEL","mission_status:B",5),),
            ),
            MissionTransition(
                "cross","source:any","source:any","PROGRESS_CHANGE",
                gate=DependencyGate("cross-gate","ALL",(
                    StateCondition("mission_status:A","EQ",7),
                )),
                effects=(TransitionEffect("SET_CHANNEL","mission_status:B",8),),
            ),
        ),
        ("source:any",),
    )

    out=materialize_channel_states(machine)
    by_id={t.transition_id:t for t in out.transitions}

    same=by_id["same"]
    assert same.from_state=="state:mission_var:Status=1",same
    assert same.to_state=="state:mission_var:Status=2",same
    assert same.metadata["state_edge_basis"]=="same_literal_channel",same.metadata

    guard=by_id["guard-only"]
    assert guard.from_state=="state:mission_status:A=4",guard
    assert guard.to_state=="source:any",guard
    assert guard.metadata["state_edge_basis"]=="guard_only_literal_channel",guard.metadata

    write=by_id["write-only"]
    assert write.from_state=="source:any",write
    assert write.to_state=="state:mission_status:B=5",write
    assert write.metadata["state_edge_basis"]=="write_only_literal_channel",write.metadata

    cross=by_id["cross"]
    assert cross.from_state=="source:any",cross
    assert cross.to_state=="source:any",cross
    assert cross.metadata["state_edge_basis"]=="cross_channel_ambiguous",cross.metadata
    assert cross.metadata["state_guard_subject"]=="mission_status:A",cross.metadata
    assert cross.metadata["state_write_subject"]=="mission_status:B",cross.metadata

    state_ids={state.state_id for state in out.states}
    assert "state:mission_status:A=7" not in state_ids,state_ids
    assert "state:mission_status:B=8" not in state_ids,state_ids

    print("mission state materialization self-test: PASS")


if __name__=="__main__":
    main()
