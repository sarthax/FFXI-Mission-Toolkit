#!/usr/bin/env python3
"""Regression for runtime-relative entity ID references."""
from __future__ import annotations

from workbench.plugins.domain.scripted_behavior_lsb_extract import extract_lsb_scripted_behavior


SCRIPT=r'''
local entity = {}

entity.onMobSpawn = function(mob)
    local mobId = mob:getID()
    GetMobByID(mobId + 1)
    GetMobByID(mobId + 2)
    DespawnMob(mobId)

    local dynamic = mob:getID()
    GetMobByID(dynamic + offset) -- intentionally unresolved
end

return entity
'''


def main():
    behavior=extract_lsb_scripted_behavior(
        SCRIPT,
        feature_id="feature:runtime-relative-entity",
        subject="Runtime Relative Actor",
        zone="TEST",
        source_path="scripts/zones/Test/mobs/Runtime_Relative_Actor.lua",
    )

    effects=[
        effect
        for rule in behavior.rules
        if rule.kind=="entity_references"
        for effect in rule.effects
        if effect.metadata.get("resolution")=="RUNTIME_RELATIVE_ID"
    ]
    by_target={effect.target:effect for effect in effects}

    expected={
        "entity-runtime-id:mob:offset:+1",
        "entity-runtime-id:mob:offset:+2",
        "entity-runtime-id:mob",
    }
    assert expected <= set(by_target),(expected-set(by_target),set(by_target))

    plus_two=by_target["entity-runtime-id:mob:offset:+2"]
    assert plus_two.effect=="REFERENCES_ENTITY",plus_two
    assert plus_two.metadata["alias"]=="mobId",plus_two.metadata
    assert plus_two.metadata["runtime_receiver"]=="mob",plus_two.metadata
    assert plus_two.metadata["offset"]==2,plus_two.metadata
    assert plus_two.metadata["alias_source_line"] < plus_two.metadata["source_line"],plus_two.metadata

    base=by_target["entity-runtime-id:mob"]
    assert base.effect=="DESPAWN_ENTITY",base
    assert base.metadata["offset"]==0,base.metadata

    # Non-literal runtime offsets must remain unresolved.
    assert not any(effect.value=="dynamic+offset" for effect in effects),effects

    print("runtime-relative entity ID regression: PASS")


if __name__=="__main__":
    main()
