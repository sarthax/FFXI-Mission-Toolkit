#!/usr/bin/env python3
"""Regression for direct symbolic entity-reference extraction."""
from __future__ import annotations

from workbench.plugins.domain.scripted_behavior_lsb_extract import extract_lsb_scripted_behavior


SCRIPT=r'''
local entity = {}

entity.onMobDeath = function(mob)
    GetNPCByID(ID.npc.TEST_DOOR):openDoor(30)
    GetMobByID(ID.mob.TEST_ADD)
    SpawnMob(ID.mob.TEST_ADD + 2)
    DespawnMob(ID.npc.TEST_DOOR - 1)

    local base = ID.mob.TEST_ADD
    for i = 0, 1 do
        GetMobByID(base + i) -- deliberately unresolved dynamic offset
    end
end

return entity
'''


def main():
    behavior=extract_lsb_scripted_behavior(
        SCRIPT,
        feature_id="feature:entity-symbols",
        subject="Symbol Actor",
        zone="TEST",
        source_path="scripts/zones/Test/mobs/Symbol_Actor.lua",
    )

    rules=[rule for rule in behavior.rules if rule.kind=="entity_references"]
    assert rules,rules
    effects=[
        effect
        for rule in rules
        for effect in rule.effects
    ]

    by_call_target={(effect.metadata["call"],effect.target):effect for effect in effects}
    expected={
        ("GetNPCByID","entity-symbol:npc:TEST_DOOR"),
        ("GetMobByID","entity-symbol:mob:TEST_ADD"),
        ("SpawnMob","entity-symbol:mob:TEST_ADD:offset:+2"),
        ("DespawnMob","entity-symbol:npc:TEST_DOOR:offset:-1"),
    }
    assert expected <= set(by_call_target),(expected-set(by_call_target),by_call_target)

    assert by_call_target[("SpawnMob","entity-symbol:mob:TEST_ADD:offset:+2")].metadata["offset"]==2
    assert by_call_target[("DespawnMob","entity-symbol:npc:TEST_DOOR:offset:-1")].metadata["offset"]==-1

    assert all(
        effect.metadata["source_line"]>=1 and effect.metadata["source_line_text"]
        for effect in effects
    ),effects

    assert not any(
        effect.metadata.get("resolution")=="LITERAL_ALIAS"
        and effect.metadata.get("alias")=="base"
        for effect in effects
    ),effects

    print("direct symbolic entity-reference regression: PASS")


if __name__=="__main__":
    main()
