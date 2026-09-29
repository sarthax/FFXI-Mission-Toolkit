#!/usr/bin/env python3
"""Regression for bounded literal numeric-loop entity expansion."""
from __future__ import annotations

from workbench.plugins.domain.scripted_behavior_lsb_extract import extract_lsb_scripted_behavior


SCRIPT=r'''
local instanceObject = {}

instanceObject.onInstanceCreated = function(instance)
    for i = 0, 3 do
        SpawnMob(ID.mob.K23H1_LAMIA + i, instance)
    end

    local doorBase = ID.npc.TEST_DOOR + 10
    for j = 1, 2 do
        GetNPCByID(doorBase - j, instance):setStatus(xi.status.NORMAL)
    end

    for k = 0, 100 do
        GetMobByID(ID.mob.TOO_MANY + k, instance)
    end
end

return instanceObject
'''


def main():
    behavior=extract_lsb_scripted_behavior(
        SCRIPT,
        feature_id="feature:bounded-loops",
        subject="Loop Controller",
        zone="TEST",
        source_path="scripts/zones/Test/instances/loop.lua",
    )

    effects=[
        effect
        for rule in behavior.rules
        if rule.kind=="entity_references"
        for effect in rule.effects
        if effect.metadata.get("resolution")=="BOUNDED_NUMERIC_LOOP"
    ]
    targets={effect.target for effect in effects}

    assert {
        "entity-symbol:mob:K23H1_LAMIA",
        "entity-symbol:mob:K23H1_LAMIA:offset:+1",
        "entity-symbol:mob:K23H1_LAMIA:offset:+2",
        "entity-symbol:mob:K23H1_LAMIA:offset:+3",
    } <= targets,targets

    assert {
        "entity-symbol:npc:TEST_DOOR:offset:+9",
        "entity-symbol:npc:TEST_DOOR:offset:+8",
    } <= targets,targets

    lamia=[
        effect for effect in effects
        if effect.metadata.get("symbol")=="K23H1_LAMIA"
    ]
    assert len(lamia)==4,lamia
    assert {effect.metadata["loop_value"] for effect in lamia}=={0,1,2,3},lamia
    assert all(effect.metadata["loop_start"]==0 and effect.metadata["loop_end"]==3 for effect in lamia),lamia

    doors=[
        effect for effect in effects
        if effect.metadata.get("symbol")=="TEST_DOOR"
    ]
    assert len(doors)==2,doors
    assert all(effect.metadata.get("alias")=="doorBase" for effect in doors),doors
    assert {effect.metadata["offset"] for effect in doors}=={8,9},doors

    # Hard cap: 101 iterations must not expand.
    assert not any(
        effect.metadata.get("symbol")=="TOO_MANY"
        and effect.metadata.get("resolution")=="BOUNDED_NUMERIC_LOOP"
        for rule in behavior.rules
        if rule.kind=="entity_references"
        for effect in rule.effects
    ),behavior.rules

    # The direct-symbol parser must not emit a false base target for ID.mob.X + loopvar.
    false_direct=[
        effect for rule in behavior.rules if rule.kind=="entity_references"
        for effect in rule.effects
        if effect.metadata.get("symbol")=="TOO_MANY"
        and effect.metadata.get("resolution")=="DIRECT_SYMBOL"
    ]
    assert not false_direct,false_direct

    print("bounded numeric entity-loop regression: PASS")


if __name__=="__main__":
    main()
