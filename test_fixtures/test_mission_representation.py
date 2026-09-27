#!/usr/bin/env python3
from workbench.plugins.domain.mission_representation import (
    MissionRequirement,
    MissionRepresentation,
    plan_mission_representation,
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
    print("mission representation planning self-test: PASS")


if __name__=="__main__":
    main()
