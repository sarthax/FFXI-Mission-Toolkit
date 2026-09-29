#!/usr/bin/env python3
"""Non-combat mission/NPC stress regression for generic scripted behavior."""
from __future__ import annotations

from workbench.plugins.domain.scripted_behavior_lsb_extract import extract_lsb_scripted_behavior
from workbench.core.services.scripted_behavior_visualizer import _graph_for_behavior


SCRIPT=r'''
local entity = {}

entity.onTrigger = function(player, npc)
    local missionStage = player:getCharVar('MissionStage')
    local guardedChoice = player:getCharVar('GuardedChoice')

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
        local result = option
        if result == 4 then
            player:setCharVar('ResultChoice', 4)
        end
    elseif csid == 102 then
        player:delKeyItem(xi.keyItem.TEST_SEAL)
        player:setCharVar('MissionStage', 2)
        GetNPCByID(ID.npc.TEST_DOOR):openDoor(30)

        if option == 1 then
            npcUtil.giveItem(player, 500)
            player:setCharVar('OutcomeChoice', 1)

            if player:getCharVar('OutcomeGate') == 3 then
                npcUtil.giveItem(player, 600)
                player:setCharVar('GuardedChoice', 9)
            end
        elseif option == 2 then
            player:addGil(100)
            GetNPCByID(ID.npc.SECOND_DOOR):openDoor(15)
            player:setCharVar('OutcomeChoice', 2)
        elseif option == dynamicOption then
            player:setCharVar('DynamicOutcome', 1)
        else
            player:setCharVar('FallbackOutcome', 1)
        end
    elseif csid == 999 then
        player:setCharVar('UnrelatedStage', 1)
    end
end

entity.onEventUpdate = function(player, csid, option, npc)
    if csid == 101 then
        if option == 7 then
            player:updateEvent(1)
            player:setCharVar('UpdateChoice', 7)
        elseif option == dynamicOption then
            player:updateEvent(2)
            player:setCharVar('DynamicUpdateChoice', 1)
        end
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
    assert {"onTrigger","onEventFinish","onEventUpdate"} <= hooks,hooks

    branch_rules=[
        rule for rule in rules
        if rule.kind=="event_branch_effects"
    ]
    branch_by_event={rule.metadata["event_id"]:rule for rule in branch_rules}
    assert set(branch_by_event)=={101,102,999},branch_by_event
    assert {
        effect.value for effect in branch_by_event[101].effects
        if effect.effect=="WRITE_STATE"
        and effect.target=="state:PLAYER_CHAR:player:MissionStage"
    }=={"1"},branch_by_event[101]
    assert {
        effect.value for effect in branch_by_event[102].effects
        if effect.effect=="WRITE_STATE"
        and effect.target=="state:PLAYER_CHAR:player:MissionStage"
    }=={"2"},branch_by_event[102]
    assert all(rule.metadata["branch_form"]=="CSID_LITERAL_BRANCH" for rule in branch_rules),branch_rules

    effects_101={(effect.effect,effect.target,effect.value) for effect in branch_by_event[101].effects}
    effects_102={(effect.effect,effect.target,effect.value) for effect in branch_by_event[102].effects}
    effects_999={(effect.effect,effect.target,effect.value) for effect in branch_by_event[999].effects}
    assert ("GRANT_KEY_ITEM","player","TEST_SEAL") in effects_101,effects_101
    assert not any(effect[0]=="REMOVE_KEY_ITEM" for effect in effects_101),effects_101
    assert ("REMOVE_KEY_ITEM","player","TEST_SEAL") in effects_102,effects_102
    assert ("OPEN_DOOR","world_entity","30") in effects_102,effects_102
    assert any(
        effect[0]=="REFERENCES_ENTITY" and effect[1]=="entity-symbol:npc:TEST_DOOR"
        for effect in effects_102
    ),effects_102
    assert not any(effect[0] in {"GRANT_KEY_ITEM","REMOVE_KEY_ITEM","OPEN_DOOR","REFERENCES_ENTITY"} for effect in effects_999),effects_999
    assert not any(effect[0] in {"GRANT_ITEM","ADD_GIL"} for effect in effects_102),effects_102
    assert not any(
        effect[0]=="WRITE_STATE"
        and effect[1] in {
            "state:PLAYER_CHAR:player:DynamicOutcome",
            "state:PLAYER_CHAR:player:FallbackOutcome",
        }
        for effect in effects_102
    ),effects_102

    outcome_rules=[rule for rule in rules if rule.kind=="event_outcome_effects"]
    outcomes={
        (rule.metadata["hook"],rule.metadata["event_id"],rule.metadata["outcome_selector"],rule.metadata["outcome_literal"]):rule
        for rule in outcome_rules
    }
    assert ("onEventFinish",101,"result","4") in outcomes,outcomes
    assert ("onEventFinish",102,"option","1") in outcomes,outcomes
    assert ("onEventFinish",102,"option","2") in outcomes,outcomes
    assert ("onEventUpdate",101,"option","7") in outcomes,outcomes
    assert not any(key[3]=="dynamicOption" for key in outcomes),outcomes

    result4={(effect.effect,effect.target,effect.value) for effect in outcomes[("onEventFinish",101,"result","4")].effects}
    option1={(effect.effect,effect.target,effect.value) for effect in outcomes[("onEventFinish",102,"option","1")].effects}
    option2={(effect.effect,effect.target,effect.value) for effect in outcomes[("onEventFinish",102,"option","2")].effects}
    update7={(effect.effect,effect.target,effect.value) for effect in outcomes[("onEventUpdate",101,"option","7")].effects}
    assert ("WRITE_STATE","state:PLAYER_CHAR:player:ResultChoice","4") in result4,result4
    assert ("GRANT_ITEM","player","500") in option1,option1
    assert ("WRITE_STATE","state:PLAYER_CHAR:player:OutcomeChoice","1") in option1,option1
    assert ("GRANT_ITEM","player","600") not in option1,option1
    assert ("WRITE_STATE","state:PLAYER_CHAR:player:GuardedChoice","9") not in option1,option1
    assert ("ADD_GIL","player","100") in option2,option2
    assert ("OPEN_DOOR","world_entity","15") in option2,option2
    assert ("WRITE_STATE","state:PLAYER_CHAR:player:OutcomeChoice","2") in option2,option2
    assert ("UPDATE_EVENT","player",None) in update7,update7
    assert ("WRITE_STATE","state:PLAYER_CHAR:player:UpdateChoice","7") in update7,update7
    assert not any(effect[0]=="ADD_GIL" for effect in option1),option1
    assert not any(effect[0]=="GRANT_ITEM" for effect in option2),option2

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
        assert "onEventFinish" in link["guard_hooks"],link
        assert link["finish_guard_hooks"]==["onEventFinish"],link
        assert {"start_hook":"onTrigger","guard_hook":"onEventFinish","handler_role":"FINISH","finish_guard_hook":"onEventFinish"} in link["cross_hook_pairs"],link
    assert graph["summary"]["events"]>=2,graph["summary"]
    assert graph["summary"]["cross_hook_event_links"]==2,graph["summary"]
    assert links[101]["update_guard_hooks"]==["onEventUpdate"],links[101]
    assert {"start_hook":"onTrigger","guard_hook":"onEventUpdate","handler_role":"UPDATE","update_guard_hook":"onEventUpdate"} in links[101]["cross_hook_pairs"],links[101]

    outcome_nodes=[
        node for node in graph["nodes"]
        if node["kind"]=="event_outcome"
    ]
    assert any(node["meta"].get("selector")=="option" and node["meta"].get("literal")=="1" for node in outcome_nodes),outcome_nodes
    assert any(edge["kind"]=="EVENT_OUTCOME_GUARD" for edge in graph["edges"]),graph["edges"]

    guarded_rules=[rule for rule in rules if rule.kind=="event_outcome_guarded_effects"]
    guarded=next(
        rule for rule in guarded_rules
        if rule.metadata.get("event_id")==102
        and rule.metadata.get("outcome_selector")=="option"
        and rule.metadata.get("outcome_literal")=="1"
        and rule.metadata.get("guard_state_id")=="state:PLAYER_CHAR:player:OutcomeGate"
        and rule.metadata.get("guard_literal")=="3"
    )
    guard_conditions={(condition.operator,condition.subject,condition.value) for condition in guarded.conditions}
    assert ("EVENT_ID_EQUALS","event:csid",102) in guard_conditions,guard_conditions
    assert ("EVENT_OUTCOME_EQUALS","event:option","1") in guard_conditions,guard_conditions
    assert ("STATE_EQUALS","state:PLAYER_CHAR:player:OutcomeGate","3") in guard_conditions,guard_conditions
    guarded_effects={(effect.effect,effect.target,effect.value) for effect in guarded.effects}
    assert ("GRANT_ITEM","player","600") in guarded_effects,guarded_effects
    assert ("WRITE_STATE","state:PLAYER_CHAR:player:GuardedChoice","9") in guarded_effects,guarded_effects

    outcome_effects={
        (row["hook"],row["event_id"],row["selector"],row["literal"],row["effect"],row["target"],row["value"]):row
        for row in graph["event_outcome_effects"]
    }
    assert ("onEventFinish",101,"result","4","WRITE_STATE","state:PLAYER_CHAR:player:ResultChoice","4") in outcome_effects,outcome_effects
    assert ("onEventFinish",102,"option","1","GRANT_ITEM","player","500") in outcome_effects,outcome_effects
    assert ("onEventFinish",102,"option","2","ADD_GIL","player","100") in outcome_effects,outcome_effects
    assert ("onEventUpdate",101,"option","7","UPDATE_EVENT","player",None) in outcome_effects,outcome_effects
    assert graph["summary"]["event_outcome_effects"]>=7,graph["summary"]
    guarded_projection={
        (row["event_id"],row["selector"],row["literal"],row["guard_state_id"],row["guard_literal"],row["effect"],row["target"],row["value"]):row
        for row in graph["event_outcome_guarded_effects"]
    }
    assert (102,"option","1","state:PLAYER_CHAR:player:OutcomeGate","3","GRANT_ITEM","player","600") in guarded_projection,guarded_projection
    assert (102,"option","1","state:PLAYER_CHAR:player:OutcomeGate","3","WRITE_STATE","state:PLAYER_CHAR:player:GuardedChoice","9") in guarded_projection,guarded_projection
    guarded_links=graph["event_outcome_guarded_state_links"]
    assert any(
        row["event_id"]==102
        and row["guard_state_id"]=="state:PLAYER_CHAR:player:OutcomeGate"
        and row["state_id"]=="state:PLAYER_CHAR:player:GuardedChoice"
        and row["reader_hooks"]==["onTrigger"]
        and row["ordering"]=="UNPROVEN"
        for row in guarded_links
    ),guarded_links
    assert graph["summary"]["event_outcome_guarded_effects"]>=2,graph["summary"]
    assert graph["summary"]["cross_hook_event_outcome_guarded_state_links"]>=1,graph["summary"]

    branch_effects={(row["event_id"],row["effect"],row["target"],row["value"]):row for row in graph["event_branch_effects"]}
    assert (101,"GRANT_KEY_ITEM","player","TEST_SEAL") in branch_effects,branch_effects
    assert (102,"REMOVE_KEY_ITEM","player","TEST_SEAL") in branch_effects,branch_effects
    assert (102,"OPEN_DOOR","world_entity","30") in branch_effects,branch_effects
    assert any(
        event_id==102 and effect=="REFERENCES_ENTITY" and target=="entity-symbol:npc:TEST_DOOR"
        for event_id,effect,target,_value in branch_effects
    ),branch_effects
    assert graph["summary"]["event_branch_effects"]>=7,graph["summary"]

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
