#!/usr/bin/env python3
"""Regression for verified downstream entity refs and inferred upstream impact candidates."""
from __future__ import annotations

import tempfile
from pathlib import Path

from workbench.core.services.scripted_behavior_visualizer import inspect_lsb_behavior
from workbench.plugins.domain.scripted_behavior_lsb_extract import extract_lsb_scripted_behavior


MOB=r'''
local entity = {}

entity.onMobDeath = function(mob, player, optParams)
    GetNPCByID(ID.npc.TEMPLE_GUARDIAN_DOOR):openDoor(300)
    SpawnMob(ID.mob.HELPER_GUARDIAN + 1)
    local witness = GetMobByID(ID.mob.WITNESS)
    -- GetNPCByID(ID.npc.COMMENT_ONLY):openDoor(5)
    local ignored = "GetMobByID(ID.mob.STRING_ONLY)"
end

return entity
'''

DOOR=r'''
local entity = {}
entity.onTrigger = function(player, npc)
    local guardian = GetMobByID(ID.mob.TEMPLE_GUARDIAN)
    if guardian ~= nil and guardian:getHP() > 0 then
        guardian:engage(player:getTargID())
    end
end
return entity
'''

NOISE=r'''
local entity = {}
-- ID.mob.TEMPLE_GUARDIAN appears only in a comment.
entity.onTrigger = function(player, npc)
    local text = "ID.mob.TEMPLE_GUARDIAN"
end
return entity
'''


def main():
    behavior=extract_lsb_scripted_behavior(
        MOB,
        feature_id="feature:impact",
        subject="Temple Guardian",
        zone="Temple_of_Uggalepih",
        source_path="scripts/zones/Temple_of_Uggalepih/mobs/Temple_Guardian.lua",
    )
    refs=[
        effect
        for rule in behavior.rules if rule.kind=="entity_reference"
        for effect in rule.effects if effect.effect=="REFERENCE_ENTITY"
    ]
    targets={effect.target for effect in refs}
    assert "entity-symbol:npc:TEMPLE_GUARDIAN_DOOR" in targets,targets
    assert "entity-expression:mob:HELPER_GUARDIAN+1" in targets,targets
    assert "entity-symbol:mob:WITNESS" in targets,targets
    assert all("COMMENT_ONLY" not in target for target in targets),targets
    assert all("STRING_ONLY" not in target for target in targets),targets
    dynamic=next(effect for effect in refs if effect.target=="entity-expression:mob:HELPER_GUARDIAN+1")
    assert dynamic.metadata["offset_sign"]=="+",dynamic
    assert dynamic.metadata["offset_source"]=="1",dynamic

    with tempfile.TemporaryDirectory() as td:
        root=Path(td)
        zone=root/"scripts/zones/Temple_of_Uggalepih"
        mob_path=zone/"mobs/Temple_Guardian.lua"
        door_path=zone/"npcs/_mf1.lua"
        noise_path=zone/"npcs/noise.lua"
        mob_path.parent.mkdir(parents=True)
        door_path.parent.mkdir(parents=True)
        mob_path.write_text(MOB,encoding="utf-8")
        door_path.write_text(DOOR,encoding="utf-8")
        noise_path.write_text(NOISE,encoding="utf-8")

        result=inspect_lsb_behavior(
            root,
            "scripts/zones/Temple_of_Uggalepih/mobs/Temple_Guardian.lua",
        )
        graph=result["graph"]
        assert graph["summary"]["entity_references"]==3,graph["summary"]
        rows={row["target"]:row for row in graph["entity_references"]}
        assert rows["entity-symbol:npc:TEMPLE_GUARDIAN_DOOR"]["operation"]=="GetNPCByID",rows
        assert rows["entity-expression:mob:HELPER_GUARDIAN+1"]["id_expression"]=="ID.mob.HELPER_GUARDIAN + 1",rows

        upstream=result["upstream_candidates"]
        assert len(upstream)==1,upstream
        row=upstream[0]
        assert row["path"].endswith("npcs/_mf1.lua"),row
        assert row["reference"]=="ID.mob.TEMPLE_GUARDIAN",row
        assert row["confidence"]=="INFERRED_IDENTITY",row
        assert "guardian = GetMobByID" in row["source_line"],row
        assert "filename-normalized candidate" in row["basis"],row

        target_nodes={n["label"] for n in graph["nodes"] if n["kind"]=="target"}
        assert "entity-symbol:npc:TEMPLE_GUARDIAN_DOOR" in target_nodes,target_nodes
        assert "entity-expression:mob:HELPER_GUARDIAN+1" in target_nodes,target_nodes

    print("scripted behavior entity-impact regression: PASS")


if __name__=="__main__":
    main()
