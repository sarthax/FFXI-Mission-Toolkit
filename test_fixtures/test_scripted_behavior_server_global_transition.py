#!/usr/bin/env python3
"""Regression for literal server-global lifecycle transitions."""
from __future__ import annotations

from workbench.plugins.domain.scripted_behavior_lsb_extract import extract_lsb_scripted_behavior


SCRIPT=r'''
local entity = {}

entity.onTrigger = function(player, npc)
    local phase = GetServerVariable('GlobalMissionPhase')

    if phase == 1 then
        SetServerVariable('GlobalMissionPhase', 2)
    end

    if phase == dynamicValue then
        SetServerVariable('GlobalMissionPhase', 3)
    end

    if phase == 2 then
        SetServerVariable('OtherGlobal', 9)
    end

    if GetServerVariable('GlobalMissionPhase') == 4 then
        SetServerVariable('GlobalMissionPhase', 5)
    end

    if GetServerVariable('GlobalMissionPhase') == 6 then
        SetServerVariable('OtherGlobal', 10)
    end
end

return entity
'''


def main():
    behavior=extract_lsb_scripted_behavior(
        SCRIPT,
        feature_id="feature:server-global-transition",
        subject="Global State NPC",
        zone="TEST",
        source_path="scripts/zones/Test/npcs/Global_State_NPC.lua",
    )

    transitions=[
        rule for rule in behavior.rules
        if rule.kind=="state_transition"
        and rule.metadata.get("transition_form")=="SERVER_GLOBAL_LITERAL_IF"
    ]
    assert len(transitions)==2,transitions

    aliased=[r for r in transitions if r.metadata.get("selector_alias")=="phase"]
    direct=[r for r in transitions if r.metadata.get("selector_alias") is None]
    assert len(aliased)==1,transitions
    assert len(direct)==1,transitions

    rule=aliased[0]
    assert rule.metadata["state_id"]=="state:SERVER_GLOBAL:server:GlobalMissionPhase",rule
    assert rule.metadata["state_scope"]=="SERVER_GLOBAL",rule.metadata
    assert rule.metadata["selector_alias"]=="phase",rule.metadata
    assert rule.metadata["if_literal"]=="1",rule.metadata

    assert len(rule.conditions)==1,rule.conditions
    condition=rule.conditions[0]
    assert condition.subject=="state:SERVER_GLOBAL:server:GlobalMissionPhase",condition
    assert condition.operator=="STATE_EQUALS",condition
    assert condition.value=="1",condition

    assert len(rule.effects)==1,rule.effects
    effect=rule.effects[0]
    assert effect.effect=="WRITE_STATE",effect
    assert effect.target=="state:SERVER_GLOBAL:server:GlobalMissionPhase",effect
    assert effect.value=="2",effect

    direct_rule=direct[0]
    assert direct_rule.metadata["selector_expression"]=="GetServerVariable('GlobalMissionPhase')",direct_rule.metadata
    assert direct_rule.metadata["if_literal"]=="4",direct_rule.metadata
    assert direct_rule.effects[0].value=="5",direct_rule.effects

    # Computed predicates and writes to a different global must not become lifecycle transitions.
    assert not any(r.metadata.get("if_literal")=="dynamicValue" for r in transitions),transitions
    assert not any(r.metadata.get("state_name")=="OtherGlobal" for r in transitions),transitions

    print("server-global literal lifecycle transition regression: PASS")


if __name__=="__main__":
    main()
