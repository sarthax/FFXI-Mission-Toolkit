#!/usr/bin/env python3
"""Mixed LSB mob/NPC/object behavior regression based on representative source patterns."""
from __future__ import annotations

from workbench.plugins.domain.scripted_behavior import project_scripted_behavior
from workbench.plugins.domain.scripted_behavior_lsb_extract import (
    extract_helper_blocks,
    extract_lsb_scripted_behavior,
)


GARGOYLE=r'''
local entity = {}
entity.onMobDeath = function(mob, player, optParams)
    if optParams.isKiller then
        GetNPCByID(ID.npc.STONE_DOOR_OFFSET + 1):openDoor(30)
    end
end
return entity
'''

KEY_ITEM_NPC=r'''
local entity = {}
entity.onTrade = function(player, npc, trade)
    if npcUtil.tradeHas(trade, xi.item.MOBLIN_OIL) and
       not player:hasKeyItem(xi.keyItem.BRACELET_OF_VERVE) then
        player:confirmTrade()
        npcUtil.giveKeyItem(player, xi.keyItem.BRACELET_OF_VERVE)
    end
end
entity.onTrigger = function(player, npc)
    player:startEvent(44)
end
return entity
'''

STATEFUL_NPC=r'''
local entity = {}
entity.onTrigger = function(player, npc)
    local playCheck = player:getCharVar('[LuckyRoll]Played')
    if playCheck ~= VanadielUniqueDay() then
        player:startEvent(174)
    end
end
entity.onEventUpdate = function(player, csid, option, npc)
    player:updateEvent(4, 1, 0, 200)
end
entity.onEventFinish = function(player, csid, option, npc)
    player:addGil(10000)
    player:delGil(100)
    player:setCharVar('[LuckyRoll]Played', VanadielUniqueDay())
end
return entity
'''

ESCORT=r'''
local entity = {}
local function moveNext(mob)
    mob:pathThrough({ 1, 2, 3 }, xi.path.flag.WALK)
end
entity.closeDoor = function(mob)
    local npc = GetNPCByID(ID.npc.DOOR)
    if npc then
        npc:setAnimation(xi.animation.CLOSE_DOOR)
    end
end
entity.onMobRoam = function(mob)
    moveNext(mob)
end
entity.onMobDespawn = function(mob)
    entity.closeDoor(mob)
end
return entity
'''

BARE_GLOBAL_HELPER=r'''
local entity = {}
function moveGlobal(mob)
    mob:pathThrough({ 4, 5, 6 }, xi.path.flag.WALK)
end
function neverCalled(mob)
    mob:setAnimation(xi.animation.CLOSE_DOOR)
end
entity.onMobRoam = function(mob)
    moveGlobal(mob)
end
return entity
'''

SALVAGE_DOOR=r'''
local entity = {}
entity.onEventFinish = function(player, csid, option, npc)
    if csid == 300 and option == 1 then
        if xi.salvage.onDoorOpen(npc, nil, 1) then
            xi.salvage.sealDoors(npc:getInstance(), ID.npc.WEST)
            xi.salvage.unsealDoors(npc:getInstance(), { ID.npc.EAST })
            npc:setUntargetable(true)
        end
    end
end
return entity
'''


def kinds(script, subject):
    behavior=extract_lsb_scripted_behavior(
        script,
        feature_id=f"feature:test:{subject}",
        subject=subject,
        zone="TEST_ZONE",
        source_path=f"scripts/zones/Test/{subject}.lua",
    )
    return behavior,{rule.kind for rule in behavior.rules}


def main():
    gargoyle,gk=kinds(GARGOYLE,"Gargoyle")
    assert "world_state_change" in gk,gk
    world=next(rule for rule in gargoyle.rules if rule.kind=="world_state_change")
    assert any(effect.effect=="OPEN_DOOR" and effect.value=="30" for effect in world.effects),world

    key_npc,kk=kinds(KEY_ITEM_NPC,"Bracelet QM")
    assert {"trade_flow","player_progression","event_flow"} <= kk,kk
    progression=next(rule for rule in key_npc.rules if rule.kind=="player_progression")
    assert any(
        effect.effect=="GRANT_KEY_ITEM" and effect.value=="BRACELET_OF_VERVE"
        for effect in progression.effects
    ),progression

    stateful,sk=kinds(STATEFUL_NPC,"Lucky Roll")
    assert {"player_state","event_flow","player_reward"} <= sk,sk
    state=next(rule for rule in stateful.rules if rule.kind=="player_state" and rule.effects)
    assert any(effect.effect=="SET_CHAR_VAR" for effect in state.effects),state
    rewards=next(rule for rule in stateful.rules if rule.kind=="player_reward")
    assert {effect.effect for effect in rewards.effects}=={"ADD_GIL","REMOVE_GIL"},rewards

    helpers=extract_helper_blocks(ESCORT)
    assert {helper.name for helper in helpers}=={"moveNext","closeDoor"},helpers
    escort,ek=kinds(ESCORT,"Escort")
    assert "helper_call" in ek,ek
    assert "helper_effects" in ek,ek
    assert set(escort.metadata["reachable_helpers"])=={"moveNext","closeDoor"},escort.metadata
    helper_effects=[rule for rule in escort.rules if rule.kind=="helper_effects"]
    assert any(
        effect.effect=="PATH_ACTOR"
        for rule in helper_effects for effect in rule.effects
    ),helper_effects
    assert any(
        effect.effect=="SET_ANIMATION"
        for rule in helper_effects for effect in rule.effects
    ),helper_effects
    assert all(rule.metadata.get("source_lines") for rule in helper_effects),helper_effects

    bare_helpers=extract_helper_blocks(BARE_GLOBAL_HELPER)
    assert {helper.name for helper in bare_helpers}=={"moveGlobal","neverCalled"},bare_helpers
    assert all(helper.owner=="global" for helper in bare_helpers),bare_helpers
    bare,bk=kinds(BARE_GLOBAL_HELPER,"Bare Global Helper")
    assert "helper_call" in bk,bk
    assert "helper_effects" in bk,bk
    assert set(bare.metadata["reachable_helpers"])=={"moveGlobal"},bare.metadata
    bare_effects=[rule for rule in bare.rules if rule.kind=="helper_effects"]
    assert any(
        effect.effect=="PATH_ACTOR"
        for rule in bare_effects for effect in rule.effects
    ),bare_effects
    assert not any(
        effect.effect=="SET_ANIMATION"
        for rule in bare_effects for effect in rule.effects
    ),bare_effects

    salvage,dk=kinds(SALVAGE_DOOR,"Salvage Door")
    assert {"system_helper_call","world_state_change"} <= dk,dk
    system=next(rule for rule in salvage.rules if rule.kind=="system_helper_call")
    calls={(effect.metadata["module"],effect.metadata["function"]) for effect in system.effects}
    assert {
        ("salvage","onDoorOpen"),
        ("salvage","sealDoors"),
        ("salvage","unsealDoors"),
    } <= calls,calls
    projection=project_scripted_behavior(
        salvage,
        source_snapshot_id="lsb:test",
        evidence_source="LSB",
        evidence_location="scripts/zones/Bhaflau_Remnants/npcs/_23c.lua",
    )
    system_node=next(
        entity.entity_id for entity in projection.entities
        if entity.display_name=="system:xi.salvage"
    )
    assert any(
        edge.target_node==system_node and edge.relationship=="REQUIRES"
        for edge in projection.edges
    ),projection.edges

    print("mixed scripted mob/NPC/object behavior regression: PASS")


if __name__=="__main__":
    main()
