#!/usr/bin/env python3
from workbench.core.schema import Artifact, MigrationAction
from workbench.migrations.package_manifest import build_package_manifest
from workbench.migrations.package_plan import build_package_plan
from workbench.plugins.domain import (
    MissionRequirement,
    plan_mission_representation,
    mission_proposal_finding,
    apply_plugin_proposal_findings,
)


def main():
    plan=plan_mission_representation(
        (MissionRequirement("gap","missing"),),
        (),
    )
    finding=mission_proposal_finding("feature:test",plan,2)
    actions=(
        MigrationAction(
            "a:mission","migration:test","MANUAL_REVIEW","artifact:mission","MANUAL_REQUIRED",
            metadata={"source_role":"mission_script"},
        ),
    )
    refined=apply_plugin_proposal_findings(actions,(finding,))
    assert refined[0].action=="REVIEW_PROPOSALS",refined
    assert refined[0].metadata["proposal_count"]==2,refined

    manifest=build_package_manifest(
        build_package_plan(refined),
        (Artifact("artifact:mission","LUA",path="lua/mission.lua"),),
        source_family="LSB",
        target_family="DSP",
    )
    step=manifest["execution"]["steps"][0]
    assert step["backend"]=="manual",manifest
    assert step["conversion_status"]=="NOT_APPLICABLE",manifest
    print("plugin proposal refinement self-test: PASS")


if __name__=="__main__":
    main()
