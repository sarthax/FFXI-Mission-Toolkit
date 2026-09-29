#!/usr/bin/env python3
"""Regression for literal entity-symbol alias propagation."""
from __future__ import annotations

from workbench.plugins.domain.scripted_behavior_lsb_extract import extract_lsb_scripted_behavior


SCRIPT=r'''
local entity = {}

entity.onMobSpawn = function(mob)
    local minionOffset = ID.mob.JAILER_OF_LOVE + 1
    GetMobByID(minionOffset + 0)
    GetMobByID(minionOffset + 1)
    SpawnMob(minionOffset + 2)

    local doorBase = ID.npc.TEST_DOOR - 2
    GetNPCByID(doorBase + 1)
    DespawnMob(doorBase)

    local dynamicBase = ID.mob.DYNAMIC_ADD
    for i = 0, 2 do
        GetMobByID(dynamicBase + i) -- intentionally unresolved in this slice
    end
end

return entity
'''


def main():
    behavior=extract_lsb_scripted_behavior(
        SCRIPT,
        feature_id="feature:entity-aliases",
        subject="Alias Actor",
        zone="TEST",
        source_path="scripts/zones/Test/mobs/Alias_Actor.lua",
    )

    effects=[
        effect
        for rule in behavior.rules
        if rule.kind=="entity_references"
        for effect in rule.effects
        if effect.metadata.get("resolution")=="LITERAL_ALIAS"
    ]
    by_target={effect.target:effect for effect in effects}

    expected={
        "entity-symbol:mob:JAILER_OF_LOVE:offset:+1",
        "entity-symbol:mob:JAILER_OF_LOVE:offset:+2",
        "entity-symbol:mob:JAILER_OF_LOVE:offset:+3",
        "entity-symbol:npc:TEST_DOOR:offset:-1",
        "entity-symbol:npc:TEST_DOOR:offset:-2",
    }
    assert expected <= set(by_target),(expected-set(by_target),set(by_target))

    assert by_target["entity-symbol:mob:JAILER_OF_LOVE:offset:+3"].metadata["alias"]=="minionOffset"
    assert by_target["entity-symbol:mob:JAILER_OF_LOVE:offset:+3"].metadata["alias_base_offset"]==1
    assert by_target["entity-symbol:mob:JAILER_OF_LOVE:offset:+3"].metadata["call_offset"]==2

    # Dynamic loop offsets must remain unresolved until bounded loop expansion is added.
    assert not any(
        effect.metadata.get("symbol")=="DYNAMIC_ADD"
        and effect.metadata.get("resolution")=="LITERAL_ALIAS"
        for effect in effects
    ),effects

    print("literal entity-symbol alias regression: PASS")


if __name__=="__main__":
    main()
