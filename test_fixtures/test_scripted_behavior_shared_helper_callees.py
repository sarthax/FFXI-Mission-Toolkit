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
    npc:setLocalVar('doorStep', 1)
end

xi.salvage.openPath = function(npc)
    GetNPCByID(ID.npc.TEST_DOOR):openDoor(30)
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

        result=inspect_lsb_behavior(root,"scripts/zones/Test/npcs/Test_NPC.lua")
        helpers={row["qualified_name"]:row for row in result["shared_helpers"]}
        row=helpers["xi.salvage.onDoorOpen"]

        assert row["status"]=="RESOLVED",row
        analysis=row["analysis"]
        assert analysis is not None,row
        callees=analysis["shared_helper_callees"]
        assert len(callees)==1,callees
        assert callees[0]["qualified_name"]=="xi.salvage.openPath",callees
        assert callees[0]["line"]>=row["candidates"][0]["line"],callees
        assert analysis["summary"]["shared_helper_callees"]==1,analysis["summary"]

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
        assert len(callee_nodes)==1,callee_nodes
        assert callee_nodes[0]["label"]=="xi.salvage.openPath",callee_nodes
        assert any(
            edge["kind"]=="CALLS_NESTED_SHARED_HELPER"
            and edge["target"]==callee_nodes[0]["id"]
            for edge in graph["edges"]
        ),graph["edges"]

    print("shared helper direct callee regression: PASS")


if __name__=="__main__":
    main()
