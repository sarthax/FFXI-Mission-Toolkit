#!/usr/bin/env python3
"""Regression for one-level direct shared-helper callee visibility."""
from __future__ import annotations

import tempfile
from pathlib import Path

from workbench.core.services.scripted_behavior_visualizer import inspect_lsb_behavior


PRIMARY=r'''
local entity = {}
entity.onTrigger = function(player, npc)
    xi.salvage.onDoorOpen(npc)
end
return entity
'''

SALVAGE=r'''
xi = xi or {}
xi.salvage = xi.salvage or {}
xi.salvage.onDoorOpen = function(npc)
    xi.salvage.openPath(npc)
    xi.instance.sharedCallback(npc)
    xi.unknown.missingThing(npc)
    npc:setLocalVar('doorStep', 1)
end

xi.salvage.openPath = function(npc)
    GetNPCByID(ID.npc.TEST_DOOR):openDoor(30)
end
'''

INSTANCE_A=r'''
xi = xi or {}
xi.instance = xi.instance or {}
xi.instance.sharedCallback = function(npc)
    return npc ~= nil
end
'''

INSTANCE_B=r'''
xi.instance.sharedCallback = function(npc)
    return true
end
'''


def main():
    with tempfile.TemporaryDirectory() as td:
        root=Path(td)
        primary=root/"scripts/zones/Test/npcs/Test_NPC.lua"
        primary.parent.mkdir(parents=True)
        primary.write_text(PRIMARY,encoding="utf-8")

        salvage=root/"scripts/globals/salvage.lua"
        salvage.parent.mkdir(parents=True)
        salvage.write_text(SALVAGE,encoding="utf-8")

        instance_file=root/"scripts/globals/instance.lua"
        instance_file.write_text(INSTANCE_A,encoding="utf-8")
        nested=root/"scripts/globals/instance/extra.lua"
        nested.parent.mkdir(parents=True)
        nested.write_text(INSTANCE_B,encoding="utf-8")

        result=inspect_lsb_behavior(root,"scripts/zones/Test/npcs/Test_NPC.lua")
        helpers={row["qualified_name"]:row for row in result["shared_helpers"]}
        row=helpers["xi.salvage.onDoorOpen"]

        assert row["status"]=="RESOLVED",row
        analysis=row["analysis"]
        assert analysis is not None,row
        callees={item["qualified_name"]:item for item in analysis["shared_helper_callees"]}
        assert set(callees)=={
            "xi.salvage.openPath",
            "xi.instance.sharedCallback",
            "xi.unknown.missingThing",
        },callees
        assert callees["xi.salvage.openPath"]["status"]=="RESOLVED",callees
        assert len(callees["xi.salvage.openPath"]["candidates"])==1,callees
        assert callees["xi.salvage.openPath"]["candidates"][0]["path"]=="scripts/globals/salvage.lua",callees
        assert callees["xi.instance.sharedCallback"]["status"]=="AMBIGUOUS",callees
        assert len(callees["xi.instance.sharedCallback"]["candidates"])==2,callees
        assert callees["xi.unknown.missingThing"]["status"]=="UNRESOLVED",callees
        assert not callees["xi.unknown.missingThing"]["candidates"],callees
        assert callees["xi.salvage.openPath"]["line"]>=row["candidates"][0]["line"],callees
        assert analysis["summary"]["shared_helper_callees"]==3,analysis["summary"]

        # This slice only exposes the direct nested helper call; it must not recursively
        # analyze openPath and invent second-level effects under onDoorOpen.
        assert not any(
            effect["target"]=="entity-symbol:npc:TEST_DOOR"
            for effect in analysis["entity_effects"]
        ),analysis["entity_effects"]

        graph=result["graph"]
        callee_nodes=[
            node for node in graph["nodes"]
            if node["kind"]=="shared_helper_callee"
        ]
        assert len(callee_nodes)==3,callee_nodes
        by_label={node["label"]:node for node in callee_nodes}
        assert by_label["xi.salvage.openPath"]["meta"]["status"]=="RESOLVED",by_label
        assert by_label["xi.instance.sharedCallback"]["meta"]["status"]=="AMBIGUOUS",by_label
        assert by_label["xi.unknown.missingThing"]["meta"]["status"]=="UNRESOLVED",by_label
        assert all(
            any(
                edge["kind"]=="CALLS_NESTED_SHARED_HELPER"
                and edge["target"]==node["id"]
                for edge in graph["edges"]
            )
            for node in callee_nodes
        ),graph["edges"]

    print("shared helper direct callee regression: PASS")


if __name__=="__main__":
    main()
