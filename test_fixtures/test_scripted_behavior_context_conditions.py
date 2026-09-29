#!/usr/bin/env python3
"""Regression for literal environmental and actor-context condition extraction."""
from __future__ import annotations

from workbench.plugins.domain.scripted_behavior_lsb_extract import extract_lsb_scripted_behavior


SCRIPT=r'''
local entity = {}

local function updateRegen(mob)
    local hour = VanadielHour()
    if hour >= 6 and hour <= 20 then
        mob:setMod(xi.mod.REGEN, 150)
    end
end

entity.onMobInitialize = function(mob)
    mob:addListener('WEATHER_CHANGE', 'TEST_WEATHER', function(mobArg, weather, element)
        if xi.data.element.getWeatherElement(element) ~= xi.element.EARTH then
            DespawnMob(mobArg:getID())
        end
    end)
end

entity.onMobRoam = function(mob)
    updateRegen(mob)
end

entity.onMobFight = function(mob, target)
    if target:getZPos() > -540 and target:getXPos() < -350 then
        mob:drawIn(target)
    end

    if target:checkDistance(mob) <= 15 then
        mob:updateEnmity(target)
    end
end

entity.onMobSkillTarget = function(target, mob, mobskill)
    local allianceTarget = target
    for _, member in ipairs(allianceTarget:getAlliance()) do
        mob:drawIn(member, 0, 0)
    end

    for _, member in ipairs(target:getParty()) do
        member:messageBasic(xi.msg.basic.NONE)
    end
end

return entity
'''


def main():
    behavior=extract_lsb_scripted_behavior(
        SCRIPT,
        feature_id="feature:context-conditions",
        subject="Context Actor",
        zone="TEST",
        source_path="scripts/zones/Test/mobs/Context_Actor.lua",
    )
    rules=[rule for rule in behavior.rules if rule.kind=="context_conditions"]
    assert rules,rules

    conditions=[
        condition
        for rule in rules
        for condition in rule.conditions
    ]
    operators={condition.operator for condition in conditions}

    assert "VANADIELHOUR_RANGE" in operators,operators
    assert "WEATHER_ELEMENT_NOT_EQUALS" in operators,operators
    assert "POSITION_COMPARE" in operators,operators
    assert "DISTANCE_COMPARE" in operators,operators
    assert "ACCESSES_ALLIANCE" in operators,operators
    assert "ACCESSES_PARTY" in operators,operators

    time=next(c for c in conditions if c.operator=="VANADIELHOUR_RANGE")
    assert time.value=={"min":6,"max":20},time
    assert time.metadata["alias"]=="hour",time

    weather=next(c for c in conditions if c.operator=="WEATHER_ELEMENT_NOT_EQUALS")
    assert weather.value=="EARTH",weather
    assert weather.metadata["weather_source"]=="element",weather

    pos=[
        c for c in conditions
        if c.operator=="POSITION_COMPARE"
    ]
    assert {
        (c.subject,c.value["axis"],c.value["operator"],c.value["value"])
        for c in pos
    }=={
        ("actor:target","Z",">",-540),
        ("actor:target","X","<",-350),
    },pos

    distance=next(c for c in conditions if c.operator=="DISTANCE_COMPARE")
    assert distance.subject=="actor:target",distance
    assert distance.value=={"target":"mob","operator":"<=","value":15},distance

    assert any(
        c.subject=="actor:allianceTarget" and c.operator=="ACCESSES_ALLIANCE"
        for c in conditions
    ),conditions
    assert any(
        c.subject=="actor:target" and c.operator=="ACCESSES_PARTY"
        for c in conditions
    ),conditions

    callback_rule=next(
        rule for rule in rules
        if rule.metadata.get("callback_type")=="addListener"
    )
    assert any(
        c.operator=="WEATHER_ELEMENT_NOT_EQUALS"
        for c in callback_rule.conditions
    ),callback_rule

    helper_rule=next(
        rule for rule in rules
        if rule.metadata.get("helper")=="updateRegen"
    )
    assert any(c.operator=="VANADIELHOUR_RANGE" for c in helper_rule.conditions),helper_rule

    for condition in conditions:
        assert condition.metadata.get("source_line")>=1,condition
        assert condition.metadata.get("source_line_text"),condition

    print("environment and actor-context condition regression: PASS")


if __name__=="__main__":
    main()
