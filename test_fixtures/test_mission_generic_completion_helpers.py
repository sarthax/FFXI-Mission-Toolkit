#!/usr/bin/env python3
"""Regression for generic structural mission-completion helper discovery."""
from workbench.plugins.domain.mission_lsb_extract import (
    correlate_lsb_handlers,
    extract_dynamic_completion_gate,
    extract_dynamic_completion_gates,
)


SOURCE=r"""
local pathOrder =
{
    xi.mission.status.TEST.ALPHA,
    xi.mission.status.TEST.BETA,
    xi.mission.status.TEST.GAMMA,
}

local function allPathsReady(player)
    for pathArg = xi.mission.status.TEST.ALPHA, xi.mission.status.TEST.GAMMA do
        if player:getMissionStatus(mission.areaId, pathArg) ~= 14 then
            return false
        end
    end

    return true
end

local function unrelatedHelper(player)
    return player:getLevel()
end

mission.sections =
{
    [xi.zone.TEST_ZONE] =
    {
        onEventFinish =
        {
            [99] = function(player, csid, option, npc)
                player:setMissionStatus(mission.areaId, 14, xi.mission.status.TEST.BETA)

                if allPathsReady(player) then
                    mission:complete(player)
                end
            end,
        },
    },
}
"""


def main():
    gates=extract_dynamic_completion_gates(SOURCE)
    assert set(gates)=={"allPathsReady"},gates
    gate=gates["allPathsReady"]
    assert gate.gate_id=="helper:allPathsReady",gate
    assert {condition.subject for condition in gate.conditions}=={
        "mission_status:ALPHA",
        "mission_status:BETA",
        "mission_status:GAMMA",
    },gate
    assert all(condition.value==14 for condition in gate.conditions),gate

    compat=extract_dynamic_completion_gate(SOURCE)
    assert compat==gate,compat

    machine=correlate_lsb_handlers(SOURCE,feature_id="mission:test:generic-helper")
    complete=[
        transition for transition in machine.transitions
        if transition.event and transition.event.event_id==99
        and any(effect.effect=="COMPLETE" for effect in transition.effects)
    ]
    assert len(complete)==1,complete
    transition=complete[0]
    assert transition.gate is None,transition
    assert transition.post_effect_gate is not None,transition
    assert {condition.subject for condition in transition.post_effect_gate.conditions}=={
        "mission_status:ALPHA",
        "mission_status:BETA",
        "mission_status:GAMMA",
    },transition
    assert transition.metadata["completion_helpers"]==("allPathsReady",),transition.metadata
    assert transition.metadata["post_effect_gate_basis"]==("mission_status:BETA",),transition.metadata
    assert any(
        effect.effect=="SET_CHANNEL"
        and effect.subject=="mission_status:BETA"
        and effect.value==14
        for effect in transition.effects
    ),transition.effects

    print("generic mission completion helper self-test: PASS")


if __name__=="__main__":
    main()
