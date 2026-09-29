#!/usr/bin/env python3
"""Mechanically different NM stress proof based on King Vinegarroon source patterns."""
from __future__ import annotations

import tempfile
from pathlib import Path

from workbench.core.services.scripted_behavior_visualizer import inspect_lsb_behavior
from workbench.plugins.domain.scripted_behavior_lsb_extract import extract_lsb_scripted_behavior


SCRIPT=r'''
local entity = {}

local skillTable =
{
    [1] = xi.mobSkill.DEATH_SCISSORS,
    [2] = xi.mobSkill.CRITICAL_BITE,
    [3] = xi.mobSkill.VENOM_STING_1,
}

local function mobRegen(mob)
    local hour = VanadielHour()
    if hour >= 6 and hour <= 20 then
        mob:setMod(xi.mod.REGEN, 150)
    else
        mob:setMod(xi.mod.REGEN, 300)
    end
end

entity.onMobInitialize = function(mob)
    mob:setRespawnTime(75600)
    mob:addImmunity(xi.immunity.SILENCE)
    mob:addImmunity(xi.immunity.PETRIFY)
    mob:setMobMod(xi.mobMod.ADD_EFFECT, 1)

    mob:addListener('WEATHER_CHANGE', 'KV_WEATHER_CHANGE', function(mobArg, weather, element)
        if not mobArg:isSpawned() then
            return
        end
        if mobArg:isEngaged() then
            return
        end
        if xi.data.element.getWeatherElement(element) ~= xi.element.EARTH then
            DespawnMob(mobArg:getID())
        end
    end)
end

entity.onMobSpawn = function(mob)
    mob:setMod(xi.mod.REGAIN, 35)
    mob:setMobMod(xi.mobMod.BASE_DAMAGE_MULTIPLIER, 250)
end

entity.onMobRoam = function(mob)
    mobRegen(mob)
end

entity.onMobFight = function(mob, target)
    local drawInTable =
    {
        conditions =
        {
            target:getZPos() > -540,
            target:getXPos() < -350,
        },
        position = mob:getPos(),
        wait = 3,
    }

    for _, condition in ipairs(drawInTable.conditions) do
        if condition then
            mob:setMobMod(xi.mobMod.NO_MOVE, 1)
            utils.drawIn(target, drawInTable)
            break
        else
            mob:setMobMod(xi.mobMod.NO_MOVE, 0)
        end
    end
    mobRegen(mob)
end

entity.onMobSkillTarget = function(target, mob, mobskill)
    if mobskill:isAoE() then
        if math.randomInt(0, 100) >= 50 then
            mob:drawIn()
        else
            local allianceTarget = target
            for _, member in ipairs(allianceTarget:getAlliance()) do
                mob:drawIn(member, 0, 0)
            end
        end
        mob:useMobAbility(skillTable[math.randomInt(1, #skillTable)])
    end
end

entity.onMobDisengage = function(mob)
    if xi.data.element.getWeatherElement(mob:getWeather()) ~= xi.element.EARTH then
        DespawnMob(mob:getID())
    end
end

entity.onMobDeath = function(mob, player, optParams)
    if player then
        player:addTitle(xi.title.VINEGAR_EVAPORATOR)
    end
end

entity.onMobDespawn = function(mob)
    mob:setRespawnTime(75600)
end

return entity
'''


def main():
    behavior=extract_lsb_scripted_behavior(
        SCRIPT,
        feature_id="feature:king-vinegarroon-stress",
        subject="King Vinegarroon",
        zone="Western Altepa Desert",
        source_path="scripts/zones/Western_Altepa_Desert/mobs/King_Vinegarroon.lua",
    )

    hooks=set(behavior.hooks)
    expected_hooks={
        "onMobInitialize","onMobSpawn","onMobRoam","onMobFight",
        "onMobSkillTarget","onMobDisengage","onMobDeath","onMobDespawn",
    }
    assert expected_hooks <= hooks,(expected_hooks-hooks,hooks)
    assert behavior.metadata["callback_count"]==1,behavior.metadata
    assert "mobRegen" in behavior.metadata["reachable_helpers"],behavior.metadata

    callbacks=[rule for rule in behavior.rules if rule.kind=="callback"]
    assert len(callbacks)==1,callbacks
    assert callbacks[0].trigger=="LISTENER:WEATHER_CHANGE",callbacks[0]
    assert callbacks[0].metadata["callback_event"]=="WEATHER_CHANGE",callbacks[0]

    api_names={
        effect.metadata.get("qualified_name")
        for rule in behavior.rules
        for effect in rule.effects
        if effect.effect=="API_CALL"
    }
    expected_api={
        "mob:setRespawnTime",
        "mob:addImmunity",
        "mob:setMobMod",
        "mob:addListener",
        "mob:setMod",
        "VanadielHour",
        "utils.drawIn",
        "allianceTarget:getAlliance",
        "mob:drawIn",
        "mob:useMobAbility",
        "xi.data.element.getWeatherElement",
        "DespawnMob",
        "player:addTitle",
    }
    assert expected_api <= api_names,(expected_api-api_names,api_names)

    listener_api={
        effect.metadata.get("qualified_name")
        for rule in behavior.rules
        if rule.metadata.get("callback_type")=="addListener"
        for effect in rule.effects
        if effect.effect=="API_CALL"
    }
    assert {
        "mobArg:isSpawned",
        "mobArg:isEngaged",
        "xi.data.element.getWeatherElement",
        "DespawnMob",
    } <= listener_api,listener_api

    helper_rules=[
        rule for rule in behavior.rules
        if rule.metadata.get("helper")=="mobRegen"
    ]
    assert helper_rules,behavior.rules
    helper_api={
        effect.metadata.get("qualified_name")
        for rule in helper_rules
        for effect in rule.effects
        if effect.effect=="API_CALL"
    }
    assert {"VanadielHour","mob:setMod"} <= helper_api,helper_api

    # This proof deliberately verifies preservation before semantic promotion:
    # weather/time/alliance/positional gates are visible through API_CALL evidence even though
    # they are not yet normalized into dedicated condition types.
    assert not any(
        condition.operator in {"WEATHER_IS","VANADIEL_HOUR_RANGE","ALLIANCE_MEMBER"}
        for rule in behavior.rules
        for condition in rule.conditions
    ),"Stress fixture must document current semantic gap rather than inventing conditions."

    with tempfile.TemporaryDirectory() as td:
        root=Path(td)
        path=root/"scripts/zones/Western_Altepa_Desert/mobs/King_Vinegarroon.lua"
        path.parent.mkdir(parents=True)
        path.write_text(SCRIPT,encoding="utf-8")
        result=inspect_lsb_behavior(
            root,
            "scripts/zones/Western_Altepa_Desert/mobs/King_Vinegarroon.lua",
        )
        graph=result["graph"]
        assert graph["summary"]["callbacks"]==1,graph["summary"]
        assert any(
            node["kind"]=="callback"
            and node["meta"].get("callback_event")=="WEATHER_CHANGE"
            for node in graph["nodes"]
        ),graph["nodes"]
        assert any(
            node["kind"]=="effect"
            and node["meta"].get("effect")=="API_CALL"
            and node["meta"].get("metadata",{}).get("qualified_name")=="allianceTarget:getAlliance"
            for node in graph["nodes"]
        ),graph["nodes"]

    print("King Vinegarroon behavior stress regression: PASS")


if __name__=="__main__":
    main()
