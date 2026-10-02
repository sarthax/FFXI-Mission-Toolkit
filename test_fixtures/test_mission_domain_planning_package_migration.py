#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import sys
import tempfile

from workbench.devtools.missions import mission_feature_closure as canonical_closure
from workbench.devtools.missions import mission_representation as canonical_representation
from workbench.devtools.missions.mission_state_machine import (
    DependencyGate,
    MissionState,
    MissionStateMachine,
    MissionTransition,
    StateCondition,
    TransitionEffect,
)
from workbench.plugins.domain import mission_feature_closure as legacy_closure
from workbench.plugins.domain import mission_representation as legacy_representation


def main() -> None:
    assert legacy_closure is canonical_closure
    assert legacy_representation is canonical_representation

    previous=MissionStateMachine(
        "machine:previous","mission:test:previous",
        (MissionState("start","Start"),MissionState("done","Done",terminal=True)),
        (MissionTransition("finish","start","done","NPC_INTERACT",effects=(TransitionEffect("GRANT","key_item:TEST_KEY"),)),),
        ("start",),metadata={"mission_symbol":"PREVIOUS"},
    )
    root=MissionStateMachine(
        "machine:root","mission:test:root",
        (MissionState("start","Start"),),(),("start",),metadata={"mission_symbol":"ROOT"},
    )

    requirements=canonical_representation.requirements_from_state_machine(previous)
    assert {row.requirement_id for row in requirements}=={"transition:finish","lifecycle:key_item:TEST_KEY"}
    plan=canonical_representation.plan_mission_representation(
        requirements,
        (canonical_representation.MissionRepresentation("transition:finish","VERIFIED"),),
    )
    assert plan.status=="MANUAL_REQUIRED"
    assert plan.missing_requirement_ids==("lifecycle:key_item:TEST_KEY",)

    gate=DependencyGate("root-prereq","ALL",(StateCondition("mission:PREVIOUS","COMPLETE",True),))
    closure=canonical_closure.build_feature_requirement_closure(root,machines=(previous,),entry_gates=(gate,))
    summary=canonical_closure.dependency_summary(closure)
    assert closure.feature_ids==("mission:test:previous","mission:test:root")
    assert summary["resolved_dependency_count"]==1
    assert not closure.unresolved_subjects

    code=(
        "from workbench.devtools.missions.mission_representation import MissionRequirement, plan_mission_representation; "
        "p=plan_mission_representation((MissionRequirement('x','x'),),()); "
        "assert p.status=='MANUAL_REQUIRED'"
    )
    subprocess.run([sys.executable,"-c",code],cwd=tempfile.gettempdir(),check=True)
    print("mission domain planning package migration self-test: PASS")


if __name__=="__main__":
    main()
