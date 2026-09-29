#!/usr/bin/env python3
"""Regression for structured Lua state-flow extraction across entity/player/instance/server scopes."""
from __future__ import annotations

from workbench.plugins.domain.scripted_behavior_lsb_extract import extract_lsb_scripted_behavior
from workbench.core.services.scripted_behavior_visualizer import _graph_for_behavior


SCRIPT=r'''
local entity = {}

entity.onMobSpawn = function(mob)
    mob:setLocalVar('phase', 1)
    mob:setLocalVar('nextAction', GetSystemTime() + 30)
end

entity.onMobFight = function(mob, target)
    local phase = mob:getLocalVar('phase')
    local nextAction = mob:getLocalVar('nextAction')
    if phase == 1 and GetSystemTime() >= nextAction then
        mob:setLocalVar('phase', 2)
        mob:setLocalVar('nextAction', GetSystemTime() + math.randomInt(15, 20))
    end
end

entity.onTrigger = function(player, npc)
    if player:getCharVar('QuestStep') == 2 then
        player:setCharVar('QuestStep', 3)
    end
end

entity.onEventFinish = function(player, csid, option, npc)
    local instance = player:getInstance()
    if instance:getLocalVar('Objective') == 4 then
        instance:setLocalVar('Objective', 5)
    end
end

entity.onMobDespawn = function(mob)
    if GetServerVariable('[POP]Example') == 0 then
        SetServerVariable('[POP]Example', GetSystemTime() + 3600)
    end
end

return entity
'''


def main():
    behavior=extract_lsb_scripted_behavior(
        SCRIPT,
        feature_id="feature:state-flow",
        subject="Stateful Actor",
        zone="TEST",
        source_path="scripts/zones/Test/mobs/Stateful_Actor.lua",
    )
    rules=[rule for rule in behavior.rules if rule.kind=="state_flow"]
    assert rules,rules

    accesses=[]
    for rule in rules:
        for condition in rule.conditions:
            if condition.operator=="READS_STATE":
                accesses.append(("READ",condition.subject,condition.value,condition.metadata))
        for effect in rule.effects:
            if effect.effect=="WRITE_STATE":
                accesses.append(("WRITE",effect.target,effect.value,effect.metadata))

    ids={row[1] for row in accesses}
    assert "state:ENTITY_LOCAL:mob:phase" in ids,ids
    assert "state:ENTITY_LOCAL:mob:nextAction" in ids,ids
    assert "state:PLAYER_CHAR:player:QuestStep" in ids,ids
    assert "state:INSTANCE_LOCAL:instance:Objective" in ids,ids
    assert "state:SERVER_GLOBAL:server:[POP]Example" in ids,ids

    writes={(sid,value) for access,sid,value,_meta in accesses if access=="WRITE"}
    assert ("state:ENTITY_LOCAL:mob:phase","1") in writes,writes
    assert ("state:ENTITY_LOCAL:mob:phase","2") in writes,writes
    assert ("state:PLAYER_CHAR:player:QuestStep","3") in writes,writes
    assert ("state:INSTANCE_LOCAL:instance:Objective","5") in writes,writes
    assert any(
        sid=="state:SERVER_GLOBAL:server:[POP]Example"
        and "GetSystemTime()" in value
        for sid,value in writes
    ),writes

    for _access,_sid,_value,meta in accesses:
        assert meta["source_line"]>=1,meta
        assert meta["source_line_text"],meta
        assert meta["scope"] in {
            "ENTITY_LOCAL","PLAYER_CHAR","INSTANCE_LOCAL","SERVER_GLOBAL"
        },meta

    fight=next(rule for rule in rules if rule.rule_id=="onMobFight:state-flow")
    read_ids={condition.subject for condition in fight.conditions}
    write_ids={effect.target for effect in fight.effects}
    assert "state:ENTITY_LOCAL:mob:phase" in read_ids & write_ids,(read_ids,write_ids)
    assert "state:ENTITY_LOCAL:mob:nextAction" in read_ids & write_ids,(read_ids,write_ids)

    graph=_graph_for_behavior(behavior)
    links={row["state_id"]:row for row in graph["state_links"]}
    phase_link=links["state:ENTITY_LOCAL:mob:phase"]
    assert phase_link["relationship"]=="SHARED_STATE_ACROSS_HOOKS",phase_link
    assert phase_link["ordering"]=="UNPROVEN",phase_link
    assert phase_link["writer_hooks"]==["onMobFight","onMobSpawn"],phase_link
    assert phase_link["reader_hooks"]==["onMobFight"],phase_link
    assert {"writer_hook":"onMobSpawn","reader_hook":"onMobFight"} in phase_link["cross_hook_pairs"],phase_link
    assert "state:PLAYER_CHAR:player:QuestStep" not in links,links
    assert graph["summary"]["cross_hook_state_links"]>=1,graph["summary"]

    print("structured scripted state-flow regression: PASS")


if __name__=="__main__":
    main()
