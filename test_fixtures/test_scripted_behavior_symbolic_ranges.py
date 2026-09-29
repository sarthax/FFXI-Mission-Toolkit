#!/usr/bin/env python3
"""Regression for bounded symbolic entity-range loops."""
from __future__ import annotations

from workbench.plugins.domain.scripted_behavior_lsb_extract import extract_lsb_scripted_behavior


SCRIPT=r'''
local instanceObject = {}

instanceObject.onInstanceProgressUpdate = function(instance, progress)
    for i = ID.npc.RUNIC_LAMP_OFFSET, ID.npc.RUNIC_LAMP_OFFSET + 4 do
        GetNPCByID(i, instance):setStatus(xi.status.DISAPPEAR)
    end

    for j = ID.mob.TEST_GROUP - 2, ID.mob.TEST_GROUP do
        DespawnMob(j, instance)
    end

    for k = ID.mob.TOO_MANY, ID.mob.TOO_MANY + 100 do
        GetMobByID(k, instance)
    end
end

return instanceObject
'''


def main():
    behavior=extract_lsb_scripted_behavior(
        SCRIPT,
        feature_id="feature:symbolic-ranges",
        subject="Range Controller",
        zone="TEST",
        source_path="scripts/zones/Test/instances/range.lua",
    )

    effects=[
        effect
        for rule in behavior.rules
        if rule.kind=="entity_references"
        for effect in rule.effects
        if effect.metadata.get("resolution")=="SYMBOLIC_RANGE_LOOP"
    ]

    lamp_targets={
        effect.target for effect in effects
        if effect.metadata.get("symbol")=="RUNIC_LAMP_OFFSET"
    }
    assert lamp_targets=={
        "entity-symbol:npc:RUNIC_LAMP_OFFSET",
        "entity-symbol:npc:RUNIC_LAMP_OFFSET:offset:+1",
        "entity-symbol:npc:RUNIC_LAMP_OFFSET:offset:+2",
        "entity-symbol:npc:RUNIC_LAMP_OFFSET:offset:+3",
        "entity-symbol:npc:RUNIC_LAMP_OFFSET:offset:+4",
    },lamp_targets

    group_targets={
        effect.target for effect in effects
        if effect.metadata.get("symbol")=="TEST_GROUP"
    }
    assert group_targets=={
        "entity-symbol:mob:TEST_GROUP:offset:-2",
        "entity-symbol:mob:TEST_GROUP:offset:-1",
        "entity-symbol:mob:TEST_GROUP",
    },group_targets

    assert all(effect.metadata["loop_step"]==1 for effect in effects),effects
    assert not any(
        effect.metadata.get("symbol")=="TOO_MANY"
        for effect in effects
    ),effects

    print("bounded symbolic entity-range regression: PASS")


if __name__=="__main__":
    main()
