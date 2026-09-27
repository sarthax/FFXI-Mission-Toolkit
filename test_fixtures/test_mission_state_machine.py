#!/usr/bin/env python3
from workbench.plugins.domain.mission_state_machine import (
    DependencyGate, EventIdentity, MissionState, MissionStateMachine, MissionTransition,
    StateCondition, TransitionEffect, analyze_state_machine, conditions_for_alternatives,
)


def main():
    gate=conditions_for_alternatives(("quest:a","quest:b","quest:c"),gate_id="nation-branch")
    assert gate.logic=="ANY"
    assert len(gate.conditions)==3

    machine=MissionStateMachine(
        "machine:test","feature:test",
        states=(
            MissionState("start","Start"),
            MissionState("branch_a","Branch A"),
            MissionState("branch_b","Branch B"),
            MissionState("done","Done",terminal=True),
        ),
        entry_state_ids=("start",),
        transitions=(
            MissionTransition(
                "choose-a","start","branch_a","NPC_INTERACT",
                gate=DependencyGate("a-gate","ALL",(StateCondition("mission:prior","COMPLETE",True),)),
                event=EventIdentity("Zone A",149,"Actor A"),
                effects=(TransitionEffect("GRANT","key_item:seal"),),
                confidence="VERIFIED",
            ),
            MissionTransition(
                "finish-a","branch_a","done","EVENT_FINISH",
                effects=(TransitionEffect("REQUIRE","key_item:seal"),TransitionEffect("REMOVE","key_item:seal"),TransitionEffect("COMPLETE","quest:a")),
                confidence="VERIFIED",
            ),
            MissionTransition(
                "choose-b","start","branch_b","ZONE_IN",
                implementation_status="EXPECTED_GAP",
                confidence="EXPECTED",
            ),
            MissionTransition("finish-b","branch_b","done","EVENT_FINISH",confidence="EXPECTED"),
        ),
    )
    analysis=analyze_state_machine(machine)
    assert analysis.status=="PARTIAL",analysis
    assert analysis.event_keys==("event:Zone A:Actor A:149",),analysis
    assert analysis.lifecycle_subjects["key_item:seal"]==("GRANT","REMOVE","REQUIRE"),analysis
    assert analysis.gap_transition_ids==("choose-b",),analysis
    assert analysis.branch_readiness[0].status=="VIABLE_WITH_GAPS",analysis

    assert EventIdentity("Zone A",149,"Actor A").key != EventIdentity("Zone B",149,"Actor A").key
    try:
        MissionStateMachine("bad","f",(MissionState("a","A"),),(MissionTransition("t","a","missing","X"),),("a",)).validate()
    except Exception:
        raise AssertionError("validate returns errors rather than raising")
    assert MissionStateMachine("bad","f",(MissionState("a","A"),),(MissionTransition("t","a","missing","X"),),("a",)).validate()
    print("generic mission state-machine self-test: PASS")


if __name__=="__main__":
    main()
