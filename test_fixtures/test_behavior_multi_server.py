#!/usr/bin/env python3
"""Behavior inspector must work on Topaz- and old-DSP-style Lua, and search across server trees."""
from __future__ import annotations

import tempfile
from pathlib import Path

from workbench.core.services.scripted_behavior_visualizer import (
    find_behavior_sources_multi,
    find_lsb_behavior_sources,
    inspect_lsb_behavior,
)


DSP_NPC = r'''
require("scripts/globals/settings");

function onTrade(player,npc,trade)
end;

function onTrigger(player,npc)
    if (player:getVar("Quest") == 1) then
        player:startEvent(0x0063);
    else
        player:startEvent(0x0034);
    end
end;

function onEventFinish(player,csid,option)
    if (csid == 0x0063) then
        player:setVar("Quest", 2);
    end
end;
'''

TOPAZ_NPC = r'''
local entity = {}

entity.onTrigger = function(player, npc)
    if not player:hasKeyItem(tpz.ki.LETTER_FROM_ZEID) then
        player:startEvent(99)
    end
end

entity.onEventFinish = function(player, csid, option)
    if (csid == 99) then
        npcUtil.giveKeyItem(player, tpz.ki.LETTER_FROM_ZEID)
        player:setCharVar("Quest", 1)
    end
end

return entity
'''

SHARED_TABLE = "local defaults = {\n    ['Gumbah'] = { event = 52 },\n}\n"


def write(root: Path, rel: str, text: str):
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def main():
    with tempfile.TemporaryDirectory() as tmp:
        dsp = Path(tmp) / "dsp"
        topaz = Path(tmp) / "topaz"
        lsb = Path(tmp) / "lsb"
        write(dsp, "scripts/zones/Bastok_Mines/npcs/Gumbah.lua", DSP_NPC)
        write(topaz, "scripts/zones/Bastok_Mines/npcs/Gumbah.lua", TOPAZ_NPC)
        write(lsb, "scripts/zones/Bastok_Mines/DefaultActions.lua", SHARED_TABLE)

        # DSP: bare global hooks, hex CSIDs, getVar/setVar.
        res = inspect_lsb_behavior(dsp, "scripts/zones/Bastok_Mines/npcs/Gumbah.lua")
        hooks = set(res["behavior"].hooks)
        assert {"onTrade", "onTrigger", "onEventFinish"} <= hooks, hooks
        assert res["graph"]["summary"]["events"] >= 2, res["graph"]["summary"]
        assert "99" in str(res["graph"]), "hex CSID 0x0063 (=99) not parsed as a literal"

        # Topaz: tpz.ki key items are recognised as key-item effects/guards.
        res = inspect_lsb_behavior(topaz, "scripts/zones/Bastok_Mines/npcs/Gumbah.lua")
        assert {"onTrigger", "onEventFinish"} <= set(res["behavior"].hooks)
        assert "LETTER_FROM_ZEID" in str(res["graph"]), "tpz.ki key item not extracted"

        # Multi-tree search: tagged per server, filename hit in dsp/topaz, content hit in lsb.
        rows = find_behavior_sources_multi({"dsp": dsp, "topaz": topaz, "lsb": lsb, "none": None}, "Gumbah")
        by_server = {r["server"]: r for r in rows}
        assert set(by_server) == {"dsp", "topaz", "lsb"}, by_server
        assert by_server["lsb"].get("match") == "content"
        assert by_server["dsp"]["path"].endswith("npcs/Gumbah.lua")
        assert [r["server"] for r in rows][0] == "dsp", "priority order must be preserved"

        # Single-tree call keeps the old contract (extra key only).
        assert find_lsb_behavior_sources(dsp, "gumbah")[0]["server"] is None

    print("behavior multi-server regression: PASS")


if __name__ == "__main__":
    main()
