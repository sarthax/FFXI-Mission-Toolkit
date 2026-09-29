#!/usr/bin/env python3
"""Non-combat mission/NPC stress regression for generic scripted behavior."""
from __future__ import annotations

from workbench.plugins.domain.scripted_behavior_lsb_extract import extract_lsb_scripted_behavior
from workbench.core.services.scripted_behavior_visualizer import _graph_for_behavior


SCRIPT=r'''
local entity = {}

entity.onTrigger = function(player, npc)
    local missionStage = player:getCharVar('MissionStage')

    if missionStage == 0 then
        player:startEvent(101)
    elseif missionStage == 1 then
        player:startEvent(102)
    elseif missionStage == 9 then
        player:startEvent(103)
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
    elseif csid == 999 then
        player:setCharVar('UnrelatedStage', 1)
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
    assert event_ids=={101,102,103},event_ids

    event_guards={
        condition.value for condition in conditions
        if condition.operator=="EVENT_ID_EQUALS"
        and condition.subject=="event:csid"
    }
    assert event_guards=={101,102,999},event_guards

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

    graph=_graph_for_behavior(behavior)
    event_nodes={
        node["meta"].get("event_id")
        for node in graph["nodes"]
        if node["kind"]=="event"
    }
    assert {101,102,103,999} <= event_nodes,event_nodes
    assert any(edge["kind"]=="STARTS_EVENT" for edge in graph["edges"]),graph["edges"]
    assert any(edge["kind"]=="EVENT_GUARD" for edge in graph["edges"]),graph["edges"]

    links={row["event_id"]:row for row in graph["event_links"]}
    assert set(links)=={101,102},links
    assert 103 not in links and 999 not in links,links
    for event_id in (101,102):
        link=links[event_id]
        assert link["relationship"]=="SHARED_EVENT_ID_ACROSS_HOOKS",link
        assert link["ordering"]=="UNPROVEN",link
        assert link["start_hooks"]==["onTrigger"],link
        assert link["finish_guard_hooks"]==["onEventFinish"],link
        assert {"start_hook":"onTrigger","finish_guard_hook":"onEventFinish"} in link["cross_hook_pairs"],link
    assert graph["summary"]["events"]>=2,graph["summary"]
    assert graph["summary"]["cross_hook_event_links"]==2,graph["summary"]

    event_state={(row["event_id"],row["state_id"],row["value"]):row for row in graph["event_state_effects"]}
    assert (101,"state:PLAYER_CHAR:player:MissionStage","1") in event_state,event_state
    assert (102,"state:PLAYER_CHAR:player:MissionStage","2") in event_state,event_state
    assert (999,"state:PLAYER_CHAR:player:UnrelatedStage","1") in event_state,event_state
    assert event_state[(101,"state:PLAYER_CHAR:player:MissionStage","1")]["ordering"]=="SOURCE_LOCAL",event_state
    assert event_state[(102,"state:PLAYER_CHAR:player:MissionStage","2")]["relationship"]=="EVENT_BRANCH_WRITES_STATE",event_state

    event_state_links={(row["event_id"],row["state_id"],row["value"]):row for row in graph["event_state_links"]}
    assert (101,"state:PLAYER_CHAR:player:MissionStage","1") in event_state_links,event_state_links
    assert (102,"state:PLAYER_CHAR:player:MissionStage","2") in event_state_links,event_state_links
    assert (999,"state:PLAYER_CHAR:player:UnrelatedStage","1") not in event_state_links,event_state_links
    assert event_state_links[(101,"state:PLAYER_CHAR:player:MissionStage","1")]["ordering"]=="UNPROVEN",event_state_links
    assert event_state_links[(101,"state:PLAYER_CHAR:player:MissionStage","1")]["reader_hooks"]==["onTrigger"],event_state_links
    assert graph["summary"]["event_state_effects"]>=3,graph["summary"]
    assert graph["summary"]["cross_hook_event_state_links"]>=2,graph["summary"]

    print("non-combat mission behavior stress regression: PASS")


if __name__=="__main__":
    main()
