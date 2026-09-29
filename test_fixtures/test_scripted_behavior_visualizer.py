#!/usr/bin/env python3
"""Behavior visualizer regression: causal primary graph plus non-promoted zone/instance context."""
from __future__ import annotations

import tempfile
from pathlib import Path

from workbench.core.services.scripted_behavior_visualizer import (
    find_lsb_behavior_sources,
    inspect_lsb_behavior,
)


MOB = r'''
local entity = {}
entity.onMobFight = function(mob, target)
    local phase = mob:getLocalVar('phase')
    if phase == 1 then
        mob:setLocalVar('phase', 2)
    end
end

entity.onMobDeath = function(mob, player, optParams)
    if optParams.isKiller then
        GetNPCByID(ID.npc.TEST_DOOR):openDoor(30)
        SetServerVariable('[POP]Test', GetSystemTime() + 3600)
    end
end
return entity
'''

ZONE = r'''
local zoneObject = {}
zoneObject.onZoneWeatherChange = function(weather)
    local qm = GetNPCByID(ID.npc.QM1)
    qm:setStatus(xi.status.NORMAL)
end
return zoneObject
'''

INSTANCE = r'''
local instanceObject = {}
instanceObject.onInstanceProgressUpdate = function(instance, progress)
    instance:setStage(progress)
    xi.instance.updateInstanceTime(instance, progress, ID.text)
end
return instanceObject
'''


def main():
    with tempfile.TemporaryDirectory() as td:
        root=Path(td)
        zone=root/"scripts/zones/Test_Zone"
        mob=zone/"mobs/Test_Mob.lua"
        mob.parent.mkdir(parents=True)
        mob.write_text(MOB,encoding="utf-8")
        (zone/"Zone.lua").write_text(ZONE,encoding="utf-8")
        inst=zone/"instances/test_instance.lua"
        inst.parent.mkdir(parents=True)
        inst.write_text(INSTANCE,encoding="utf-8")

        matches=find_lsb_behavior_sources(root,"Test Mob")
        assert any(row["path"].endswith("mobs/Test_Mob.lua") for row in matches),matches

        result=inspect_lsb_behavior(root,"scripts/zones/Test_Zone/mobs/Test_Mob.lua")
        assert result["source"]["zone"]=="Test_Zone",result["source"]
        graph=result["graph"]
        assert graph["summary"]["hooks"]==2,graph["summary"]
        assert graph["summary"]["states"]>=2,graph["summary"]
        labels={n["label"] for n in graph["nodes"]}
        assert "onMobDeath" in labels,labels
        api_nodes=[
            n for n in graph["nodes"]
            if n["kind"]=="effect" and n["meta"].get("effect")=="API_CALL"
        ]
        api_names={
            n["meta"]["metadata"].get("qualified_name")
            for n in api_nodes
        }
        assert "GetNPCByID" in api_names,api_names
        assert "SetServerVariable" in api_names,api_names
        assert any(
            n["kind"]=="effect" and n["meta"].get("effect")=="OPEN_DOOR"
            for n in graph["nodes"]
        ),graph["nodes"]

        state_by_id={row["state_id"]:row for row in graph["states"]}
        phase=state_by_id["state:ENTITY_LOCAL:mob:phase"]
        assert phase["reads"] and phase["writes"],phase
        assert phase["writes"][0]["value"]=="2",phase
        server=state_by_id["state:SERVER_GLOBAL:server:[POP]Test"]
        assert not server["reads"],server
        assert server["writes"],server
        state_nodes={n["meta"].get("state_id") for n in graph["nodes"] if n["kind"]=="state"}
        assert phase["state_id"] in state_nodes,state_nodes
        assert server["state_id"] in state_nodes,state_nodes
        assert any(e["kind"]=="STATE_READ" for e in graph["edges"]),graph["edges"]
        assert any(e["kind"]=="STATE_WRITE" for e in graph["edges"]),graph["edges"]
        state_links={row["state_id"]:row for row in graph["state_links"]}
        phase_link=state_links["state:ENTITY_LOCAL:mob:phase"]
        assert phase_link["ordering"]=="UNPROVEN",phase_link
        assert {"writer_hook":"onMobFight","reader_hook":"onMobFight"} not in phase_link["cross_hook_pairs"],phase_link
        assert {"writer_hook":"onMobFight","reader_hook":"onMobFight"} not in phase_link["cross_hook_pairs"],phase_link
        assert graph["summary"]["cross_hook_state_links"]>=1,graph["summary"]

        context_by_path={row["path"]:row for row in result["contexts"]}
        assert "scripts/zones/Test_Zone/Zone.lua" in context_by_path,context_by_path
        assert "scripts/zones/Test_Zone/instances/test_instance.lua" in context_by_path,context_by_path
        assert "onZoneWeatherChange" in context_by_path["scripts/zones/Test_Zone/Zone.lua"]["hooks"]
        assert "onInstanceProgressUpdate" in context_by_path["scripts/zones/Test_Zone/instances/test_instance.lua"]["hooks"]
        assert all(
            row["scope_basis"]=="same-zone context; not a proven dependency"
            for row in result["contexts"]
        ),result["contexts"]

        # Context controllers are deliberately not merged into the actor's causal graph.
        node_text=" ".join(labels)
        assert "onZoneWeatherChange" not in node_text,node_text
        assert "onInstanceProgressUpdate" not in node_text,node_text

    print("scripted behavior visualizer regression: PASS")


if __name__=="__main__":
    main()
