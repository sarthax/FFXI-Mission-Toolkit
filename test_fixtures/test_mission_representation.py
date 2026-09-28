#!/usr/bin/env python3
from workbench.plugins.domain.mission_representation import (
    MissionRequirement,
    MissionRepresentation,
    plan_mission_representation,
    requirements_from_state_machine,
)
from workbench.plugins.domain.mission_state_machine import (
    DependencyGate,
    MissionState,
    MissionStateMachine,
    MissionTransition,
    StateCondition,
)


def main():
    requirements=(
        MissionRequirement("gate","Gate advances status 0 to 1"),
        MissionRequirement("riverne","Riverne advances status 1 to 2"),
        MissionRequirement("complete","Battlefield win completes mission"),
    )
    representations=(
        MissionRepresentation("gate","VERIFIED",("Misareaux/_0p2.lua",)),
        MissionRepresentation("complete","VERIFIED",("Monarch_Linn/bcnms/ancient_vows.lua",)),
    )
    plan=plan_mission_representation(requirements,representations)
    assert plan.status=="MANUAL_REQUIRED",plan
    assert plan.missing_requirement_ids==("riverne",),plan
    assert set(plan.represented_requirement_ids)=={"gate","complete"},plan
    machine=MissionStateMachine(
        "m","f",
        (MissionState("s","Start"),MissionState("d","Done",terminal=True)),
        (
            MissionTransition(
                "advance","s","d","EVENT_FINISH",evidence_ids=("ev:1",),
                post_effect_gate=DependencyGate(
                    "converge","ALL",
                    (
                        StateCondition("mission_status:A","EQ",14),
                        StateCondition("mission_status:B","EQ",14),
                    ),
                ),
            ),
        ),
        ("s",),
    )
    derived=requirements_from_state_machine(machine)
    assert derived[0].requirement_id=="transition:advance",derived
    assert derived[0].evidence==("ev:1",),derived
    assert "post-effect ALL" in derived[0].description,derived[0]
    print("mission representation planning self-test: PASS")


if __name__=="__main__":
    main()
