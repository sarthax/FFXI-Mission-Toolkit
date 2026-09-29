#!/usr/bin/env python3
"""Non-combat mission/NPC stress regression for generic scripted behavior."""
from __future__ import annotations

from workbench.plugins.domain.scripted_behavior_lsb_extract import extract_lsb_scripted_behavior


SCRIPT=r'''
local entity = {}

entity.onTrigger = function(player, npc)
    local missionStage = player:getCharVar('MissionStage')

    if missionStage == 0 then
        player:startEvent(101)
    elseif missionStage == 1 then
        player:startEvent(102)
    end
end

entity.onEventFinish = function(player, csid, option, npc)
    if csid == 101 then
        npcUtil.giveKeyItem(player, xi.keyItem.TEST_SEAL)
        player:setCharVar('MissionStage', 1)
    elseif csid == 102 then
        player:delKeyItem(xi.keyItem.TEST_SEAL)
        player:setCharVar('MissionStage', 2)
        GetNPCByID(ID.npc.TEST_DOOR):openDoor(30)
    end
end

return entity
'''


def main():
    behavior=extract_lsb_scripted_behavior(
        SCRIPT,
        feature_id="feature:noncombat-mission-stress",
        subject="Mission NPC",
        zone="TEST",
        source_path="scripts/zones/Test/npcs/Mission_NPC.lua",
    )

    rules=list(behavior.rules)
    effects=[
        effect
        for rule in rules
        for effect in rule.effects
    ]
    conditions=[
        condition
        for rule in rules
        for condition in rule.conditions
    ]

    event_ids={
        effect.value for effect in effects
        if effect.effect=="START_EVENT"
    }
    assert event_ids=={101,102},event_ids

    assert any(
        condition.operator=="READS_STATE"
        and condition.subject=="state:PLAYER_CHAR:player:MissionStage"
        for condition in conditions
    ),conditions

    stage_writes=[
        effect for effect in effects
        if effect.effect=="WRITE_STATE"
        and effect.target=="state:PLAYER_CHAR:player:MissionStage"
    ]
    assert {effect.value for effect in stage_writes}>={"1","2"},stage_writes

    assert any(
        effect.effect=="GRANT_KEY_ITEM"
        and effect.value=="TEST_SEAL"
        for effect in effects
    ),effects
    assert any(
        effect.effect=="REMOVE_KEY_ITEM"
        and effect.value=="TEST_SEAL"
        for effect in effects
    ),effects

    assert any(
        effect.effect=="REFERENCES_ENTITY"
        and effect.target=="entity-symbol:npc:TEST_DOOR"
        for effect in effects
    ),effects
    assert any(
        effect.effect=="OPEN_DOOR"
        and effect.value=="30"
        for effect in effects
    ),effects

    hooks=set(behavior.hooks)
    assert {"onTrigger","onEventFinish"} <= hooks,hooks

    print("non-combat mission behavior stress regression: PASS")


if __name__=="__main__":
    main()
