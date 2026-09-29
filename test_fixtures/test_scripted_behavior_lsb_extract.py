#!/usr/bin/env python3
"""Regression for conservative LSB scripted-entity Lua extraction."""
from __future__ import annotations

from workbench.plugins.domain.scripted_behavior import project_scripted_behavior
from workbench.plugins.domain.scripted_behavior_lsb_extract import (
    extract_hook_blocks,
    extract_lsb_scripted_behavior,
)


AV = r'''
local entity = {}

entity.onMobSpawn = function(mob)
    if xi.av.experimental then
        mob:setDropID(0)
    end
    local jol = GetMobByID(ID.mob.JAILER_OF_LOVE)
    if jol ~= nil then
        if jol:getLocalVar('JoL_Qn_xzomit_Killed') == 9 then
            mob:addMod(xi.mod.REGEN, 125)
        end
        if jol:getLocalVar('JoL_Qn_hpemde_Killed') == 9 then
            mob:addMod(xi.mod.REGEN, 125)
        end
    end
end

entity.onMobEngage = function(mob, target)
    xi.av.nextsp = GetSystemTime() + math.randomInt(45, 90)
end

entity.onPlayerAbilityUse = function(mob, player, ability)
    if player:checkDistance(mob) <= 15 then
        mob:setLocalVar('lock', 1)
    end
end

entity.onMobFight = function(mob)
    if mob:getHPP() <= 60 then
        mob:addMod(xi.mod.STR, 50)
    end
end

entity.onSpellPrecast = function(mob, spell)
    spell:setAoE(xi.magic.aoe.RADIAL)
    spell:setRadius(30)
end

entity.onMagicHit = function(caster, target, spell)
    target:delMod(xi.mod.REGEN, 2)
end

entity.onMobDeath = function(mob)
    DespawnMob(mob:getID() + 1)
end

entity.onMobDespawn = function(mob)
    DespawnMob(mob:getID() + 1)
end

return entity
'''

JOL = r'''
local entity = {}

entity.onMobDeath = function(mob)
    if math.randomInt(1, 100) <= 25 then
        local av = GetMobByID(ID.mob.ABSOLUTE_VIRTUE)
        if av then
            mob:timer(10000, function(mobArg)
                SpawnMob(ID.mob.ABSOLUTE_VIRTUE)
                av:updateEnmity(mobArg:getTarget())
                av:updateClaim(mobArg:getTarget())
            end)
        end
    end
end

return entity
'''


def main():
    blocks=extract_hook_blocks(AV)
    assert [block.hook for block in blocks]==[
        "onMobSpawn",
        "onMobEngage",
        "onPlayerAbilityUse",
        "onMobFight",
        "onSpellPrecast",
        "onMagicHit",
        "onMobDeath",
        "onMobDespawn",
    ],blocks
    assert all(block.start_line <= block.end_line for block in blocks)

    av=extract_lsb_scripted_behavior(
        AV,
        feature_id="feature:av",
        subject="Absolute Virtue",
        zone="Al'Taieu",
        source_path="scripts/zones/AlTaieu/mobs/Absolute_Virtue.lua",
    )
    av_kinds={rule.kind for rule in av.rules}
    assert {
        "cross_entity_state",
        "loot_override",
        "combat_modifier",
        "timed_random_action",
        "player_action_response",
        "hp_threshold",
        "spell_override",
        "magic_response",
        "cleanup",
    } <= av_kinds,av_kinds
    cross=next(rule for rule in av.rules if rule.kind=="cross_entity_state")
    assert cross.subject=="entity-symbol:JAILER_OF_LOVE",cross
    assert cross.target=="Absolute Virtue",cross
    assert {
        c.value for c in cross.conditions if c.operator=="READS_LOCAL_STATE"
    }=={"JoL_Qn_xzomit_Killed","JoL_Qn_hpemde_Killed"},cross
    hpp=next(rule for rule in av.rules if rule.kind=="hp_threshold")
    assert hpp.conditions[0].operator=="HPP_AT_OR_BELOW",hpp
    assert hpp.conditions[0].value==60,hpp
    timer=next(rule for rule in av.rules if rule.kind=="timed_random_action")
    assert timer.conditions[0].value==(45,90),timer
    assert av.metadata["source_hook_count"]==8,av.metadata
    assert not av.metadata["unmodeled_hooks"],av.metadata
    assert all(rule.metadata.get("source_lines") for rule in av.rules),av.rules

    jol=extract_lsb_scripted_behavior(
        JOL,
        feature_id="feature:jol",
        subject="Jailer of Love",
        zone="Al'Taieu",
        source_path="scripts/zones/AlTaieu/mobs/Jailer_of_Love.lua",
    )
    jol_kinds={rule.kind for rule in jol.rules}
    assert {"spawn_from_death","inherit_runtime_target"} <= jol_kinds,jol_kinds
    spawn=next(rule for rule in jol.rules if rule.kind=="spawn_from_death")
    assert spawn.target=="entity-symbol:ABSOLUTE_VIRTUE",spawn
    assert spawn.conditions[0].operator=="PROBABILITY_PERCENT",spawn
    assert spawn.conditions[0].value==25,spawn
    assert spawn.effects[0].metadata["delay_ms"]==10000,spawn
    inherit=next(rule for rule in jol.rules if rule.kind=="inherit_runtime_target")
    assert inherit.target=="entity-symbol:ABSOLUTE_VIRTUE",inherit

    projection=project_scripted_behavior(
        av,
        source_snapshot_id="lsb:test",
        evidence_source="LSB",
        evidence_location="scripts/zones/AlTaieu/mobs/Absolute_Virtue.lua",
    )
    source_evidence=[
        row for row in projection.evidence
        if row.evidence_type=="SERVER_SOURCE" and row.location and ":L" in row.location
    ]
    assert source_evidence,projection.evidence
    rule_edge=next(
        edge for edge in projection.edges
        if edge.relationship=="HAS_BEHAVIOR_RULE"
    )
    assert rule_edge.evidence_id in {row.evidence_id for row in source_evidence},rule_edge
    assert ":L" in (rule_edge.source_location or ""),rule_edge

    print("LSB scripted behavior extraction regression: PASS")


if __name__=="__main__":
    main()
