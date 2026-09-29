#!/usr/bin/env python3
"""Regression for literal switch/case named-state transitions."""
from __future__ import annotations

from workbench.plugins.domain.scripted_behavior_lsb_extract import extract_lsb_scripted_behavior


SCRIPT=r'''
local entity = {}

entity.onMobSpawn = function(mob)
    mob:setLocalVar('phase', 1)
    mob:setLocalVar('abilityOrder', 0)
end

entity.onMobFight = function(mob, target)
    local phase = mob:getLocalVar('phase')
    local abilityOrder = mob:getLocalVar('abilityOrder')

    switch (phase): caseof
    {
        [1] = function()
            if mob:getHPP() < 70 then
                mob:setLocalVar('phase', 2)
                mob:setLocalVar('abilityOrder', 1)
            end
        end,

        [2] = function()
            if mob:getHPP() < 40 then
                mob:setLocalVar('phase', 3)
            end
        end,

        [3] = function()
            if mob:getHPP() < 15 then
                mob:setLocalVar('phase', 4)
                mob:setLocalVar('abilityOrder', 2)
            end
        end,

        [4] = function()
            mob:setLocalVar('abilityOrder', 0)
        end,
    }
end

return entity
'''


def main():
    behavior=extract_lsb_scripted_behavior(
        SCRIPT,
        feature_id="feature:phase-machine",
        subject="Phase Boss",
        zone="TEST",
        source_path="scripts/zones/Test/mobs/Phase_Boss.lua",
    )
    transitions=[rule for rule in behavior.rules if rule.kind=="state_transition"]
    assert len(transitions)==3,transitions
    assert behavior.metadata["state_transition_count"]==3,behavior.metadata

    pairs=[]
    for rule in transitions:
        assert len(rule.conditions)==1,rule
        assert len(rule.effects)==1,rule
        condition=rule.conditions[0]
        effect=rule.effects[0]
        assert condition.subject=="state:ENTITY_LOCAL:mob:phase",condition
        assert condition.operator=="STATE_EQUALS",condition
        assert effect.effect=="WRITE_STATE",effect
        assert effect.target=="state:ENTITY_LOCAL:mob:phase",effect
        pairs.append((condition.value,effect.value))
        assert rule.metadata["selector_alias"]=="phase",rule.metadata
        assert rule.metadata["state_name"]=="phase",rule.metadata
        assert rule.metadata["source_lines"][0] <= rule.metadata["source_lines"][1],rule.metadata
        assert effect.metadata["source_line"]>=rule.metadata["source_lines"][0],effect.metadata

    assert pairs==[("1","2"),("2","3"),("3","4")],pairs

    # Writes to another state inside the phase cases stay generic state flow and are not
    # incorrectly promoted as phase transitions.
    assert all(
        effect.target!="state:ENTITY_LOCAL:mob:abilityOrder"
        for rule in transitions for effect in rule.effects
    ),transitions
    generic_writes=[
        effect for rule in behavior.rules if rule.kind=="state_flow"
        for effect in rule.effects if effect.target=="state:ENTITY_LOCAL:mob:abilityOrder"
    ]
    assert generic_writes,generic_writes

    print("literal switch state-transition regression: PASS")


if __name__=="__main__":
    main()
