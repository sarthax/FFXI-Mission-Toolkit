#!/usr/bin/env python3
"""Regression for open-ended hook ownership and API-call preservation."""
from __future__ import annotations

from workbench.plugins.domain.scripted_behavior_lsb_extract import (
    extract_hook_blocks,
    extract_lsb_scripted_behavior,
)

SCRIPT=r'''
local zoneObject = {}
zoneObject.onInitialize = function(zone)
    zone:registerCylindricalTriggerArea(1, -10, -20, 15)
    xi.treasure.initZone(zone)
end

zoneObject.onZoneWeatherChange = function(weather)
    local npc = GetNPCByID(ID.npc.QM1)
    if npc then
        npc:setStatus(xi.status.NORMAL)
    end
end

local instanceObject = {}
instanceObject.registryRequirements = function(player)
    return player:hasKeyItem(xi.keyItem.TEST_KEY)
end

instanceObject.afterInstanceRegister = function(player)
    local instance = player:getInstance()
    instance:setStage(3)
    player:setPos(1, 2, 3, 4, xi.zone.TEST)
    player:addCurrency('test_points', 50)
end

local entity = {}
entity.onMobDespawn = function(mob)
    SetServerVariable('[POP]Example', GetSystemTime() + 3600)
    mob:setRespawnTime(7200)
end
return entity
'''

def main():
    blocks=extract_hook_blocks(SCRIPT)
    owners={(b.owner,b.hook) for b in blocks}
    assert ("zoneObject","onInitialize") in owners,owners
    assert ("zoneObject","onZoneWeatherChange") in owners,owners
    assert ("instanceObject","registryRequirements") in owners,owners
    assert ("instanceObject","afterInstanceRegister") in owners,owners
    assert ("entity","onMobDespawn") in owners,owners

    behavior=extract_lsb_scripted_behavior(
        SCRIPT,
        feature_id="feature:open-ended",
        subject="Mixed Script",
        zone="TEST",
        source_path="scripts/zones/Test/Zone.lua",
    )
    api_rules=[r for r in behavior.rules if r.kind=="api_calls"]
    assert api_rules,behavior.rules
    names={
        effect.metadata["qualified_name"]
        for rule in api_rules
        for effect in rule.effects
        if effect.effect=="API_CALL"
    }
    expected={
        "zone:registerCylindricalTriggerArea",
        "xi.treasure.initZone",
        "GetNPCByID",
        "npc:setStatus",
        "player:hasKeyItem",
        "player:getInstance",
        "instance:setStage",
        "player:setPos",
        "player:addCurrency",
        "SetServerVariable",
        "GetSystemTime",
        "mob:setRespawnTime",
    }
    assert expected <= names,(expected-names,names)
    assert set(behavior.metadata["hook_owners"])=={"entity","instanceObject","zoneObject"},behavior.metadata
    for rule in api_rules:
        for effect in rule.effects:
            assert effect.metadata["source_line"]>=1,effect
            assert effect.metadata["source_line_text"],effect

    print("open-ended Lua behavior regression: PASS")

if __name__=="__main__":
    main()
