#!/usr/bin/env python3
from workbench.plugins.domain.mission_dsp import MissionPatchProposal, generated_mission_patch_proposals
from workbench.plugins.domain.mission_representation import MissionRequirement, MissionRepresentation, plan_mission_representation


def main():
    plan=plan_mission_representation(
        (
            MissionRequirement("present","present"),
            MissionRequirement("missing","missing"),
        ),
        (MissionRepresentation("present","VERIFIED"),),
    )
    outputs=generated_mission_patch_proposals(
        plan,
        (
            MissionPatchProposal("present","a.lua","-- should not emit","already present"),
            MissionPatchProposal("missing","b.lua","-- proposed change","missing behavior"),
        ),
    )
    assert len(outputs)==1,outputs
    assert outputs[0].metadata["proposal_only"] is True,outputs
    assert outputs[0].metadata["requirement_id"]=="missing",outputs
    print("mission proposal output self-test: PASS")


if __name__=="__main__":
    main()
