#!/usr/bin/env python3
"""Regression for timer/queue/listener callback extraction and visualization."""
from __future__ import annotations

import tempfile
from pathlib import Path

from workbench.core.services.scripted_behavior_visualizer import inspect_lsb_behavior
from workbench.plugins.domain.scripted_behavior_lsb_extract import (
    extract_callback_blocks,
    extract_lsb_scripted_behavior,
)


SCRIPT=r'''
local entity = {}

entity.onMobInitialize = function(mob)
    mob:addListener('WEATHER_CHANGE', 'TEST_WEATHER', function(mobArg, weather, element)
        if weather ~= xi.weather.RAIN then
            mobArg:setLocalVar('weatherState', 1)
            DespawnMob(mobArg:getID())
        end
    end)
end

entity.onMobSpawn = function(mob)
    mob:timer(3000, function(mobArg)
        mobArg:setLocalVar('ready', 1)
        mobArg:setUntargetable(false)
    end)
end

entity.onMobFight = function(mob, target)
    mob:queue(0, function(mobArg)
        mobArg:setLocalVar('phase', 2)
        mobArg:useMobAbility(xi.mobSkill.TEST_SKILL)
    end)
end

entity.onMobDeath = function(mob)
    GetNPCByID(ID.npc.TEST_RUNE):timer(9000,
    function(rune)
        rune:setStatus(xi.status.NORMAL)
        rune:setLocalVar('cued', 0)
    end)
end

return entity
'''


def main():
    callbacks=extract_callback_blocks(SCRIPT,start_line=1)
    kinds=[row.callback_type for row in callbacks]
    assert kinds==["addListener","timer","queue","timer"],kinds

    listener=callbacks[0]
    assert listener.event_name=="WEATHER_CHANGE",listener
    assert listener.trigger=="LISTENER:WEATHER_CHANGE",listener
    assert listener.args==("mobArg","weather","element"),listener

    timers=[row for row in callbacks if row.callback_type=="timer"]
    assert timers[0].delay_source=="3000",timers[0]
    assert timers[1].delay_source=="9000",timers[1]
    assert "GetNPCByID" in (timers[1].receiver or ""),timers[1]

    behavior=extract_lsb_scripted_behavior(
        SCRIPT,
        feature_id="feature:callbacks",
        subject="Callback Actor",
        zone="TEST",
        source_path="scripts/zones/Test/mobs/Callback_Actor.lua",
    )
    callback_rules=[rule for rule in behavior.rules if rule.kind=="callback"]
    assert len(callback_rules)==4,callback_rules
    assert behavior.metadata["callback_count"]==4,behavior.metadata
    assert {
        "LISTENER:WEATHER_CHANGE",
        "TIMER_CALLBACK",
        "QUEUE_CALLBACK",
    } <= {rule.trigger for rule in callback_rules},callback_rules

    nested_api=[
        effect.metadata["qualified_name"]
        for rule in behavior.rules
        if rule.metadata.get("callback_type")
        for effect in rule.effects
        if effect.effect=="API_CALL"
    ]
    assert "mobArg:setUntargetable" in nested_api,nested_api
    assert "mobArg:useMobAbility" in nested_api,nested_api
    assert "DespawnMob" in nested_api,nested_api
    assert "rune:setStatus" in nested_api,nested_api

    nested_state=[
        (effect.target,effect.value,rule.trigger)
        for rule in behavior.rules
        if rule.metadata.get("callback_type")
        for effect in rule.effects
        if effect.effect=="WRITE_STATE"
    ]
    assert ("state:ENTITY_LOCAL:mobArg:ready","1","TIMER_CALLBACK") in nested_state,nested_state
    assert ("state:ENTITY_LOCAL:mobArg:phase","2","QUEUE_CALLBACK") in nested_state,nested_state
    assert ("state:ENTITY_LOCAL:rune:cued","0","TIMER_CALLBACK") in nested_state,nested_state

    with tempfile.TemporaryDirectory() as td:
        root=Path(td)
        path=root/"scripts/zones/Test/mobs/Callback_Actor.lua"
        path.parent.mkdir(parents=True)
        path.write_text(SCRIPT,encoding="utf-8")
        result=inspect_lsb_behavior(root,"scripts/zones/Test/mobs/Callback_Actor.lua")
        graph=result["graph"]
        assert graph["summary"]["callbacks"]==4,graph["summary"]
        callback_nodes=[node for node in graph["nodes"] if node["kind"]=="callback"]
        assert len(callback_nodes)==4,callback_nodes
        assert any(node["meta"].get("callback_event")=="WEATHER_CHANGE" for node in callback_nodes),callback_nodes
        assert any(node["meta"].get("callback_delay_source")=="9000" for node in callback_nodes),callback_nodes
        assert sum(1 for edge in graph["edges"] if edge["kind"]=="SCHEDULES_CALLBACK")==4,graph["edges"]
        callback_ids={node["id"] for node in callback_nodes}
        assert all(
            any(edge["source"]==node_id and edge["kind"]=="HAS_RULE" for edge in graph["edges"])
            for node_id in callback_ids
        ),graph["edges"]

    print("scripted callback behavior regression: PASS")


if __name__=="__main__":
    main()
