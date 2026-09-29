#!/usr/bin/env python3
"""Regression for shared xi helper definition resolution in Behavior Inspector."""
from __future__ import annotations

import tempfile
from pathlib import Path

from workbench.core.services.scripted_behavior_visualizer import inspect_lsb_behavior


PRIMARY=r'''
local entity = {}
entity.onTrigger = function(player, npc)
    xi.salvage.onDoorOpen(npc, nil, 1)
    xi.instance.sharedCallback(player)
    xi.unknown.missingThing(player)
end
return entity
'''

SALVAGE=r'''
xi = xi or {}
xi.salvage = xi.salvage or {}
xi.salvage.onDoorOpen = function(npc, arg, option)
    return true
end
'''

INSTANCE_A=r'''
xi = xi or {}
xi.instance = xi.instance or {}
function xi.instance.sharedCallback(player)
    return player ~= nil
end
'''

INSTANCE_B=r'''
xi.instance.sharedCallback = function(player)
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

        salvage_row=helpers["xi.salvage.onDoorOpen"]
        assert salvage_row["status"]=="RESOLVED",salvage_row
        assert len(salvage_row["candidates"])==1,salvage_row
        assert salvage_row["candidates"][0]["path"]=="scripts/globals/salvage.lua",salvage_row

        instance_row=helpers["xi.instance.sharedCallback"]
        assert instance_row["status"]=="AMBIGUOUS",instance_row
        assert {
            row["path"] for row in instance_row["candidates"]
        }=={
            "scripts/globals/instance.lua",
            "scripts/globals/instance/extra.lua",
        },instance_row

        unknown=helpers["xi.unknown.missingThing"]
        assert unknown["status"]=="UNRESOLVED",unknown
        assert not unknown["candidates"],unknown

        graph=result["graph"]
        helper_nodes={
            node["label"]:node
            for node in graph["nodes"]
            if node["kind"]=="shared_helper"
        }
        assert helper_nodes["xi.salvage.onDoorOpen"]["meta"]["resolution_status"]=="RESOLVED"
        assert helper_nodes["xi.instance.sharedCallback"]["meta"]["resolution_status"]=="AMBIGUOUS"
        assert helper_nodes["xi.unknown.missingThing"]["meta"]["resolution_status"]=="UNRESOLVED"
        assert any(
            edge["kind"]=="CALLS_SHARED_HELPER"
            for edge in graph["edges"]
        ),graph["edges"]

    print("shared helper definition resolution regression: PASS")


if __name__=="__main__":
    main()
