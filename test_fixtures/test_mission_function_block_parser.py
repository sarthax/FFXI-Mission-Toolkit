#!/usr/bin/env python3
"""Regression for conservative outermost Lua function block extraction."""
from workbench.plugins.domain.mission_lsb_extract import (
    _balanced_function_blocks,
    correlate_lsb_handlers,
    extract_helper_transitions,
)


SOURCE=r'''
-- function fake_comment()
local quoted = "function fake_string() end"
local long_text = [[
function fake_long_string()
end
]]
--[[
function fake_block_comment()
end
]]

helper = function(player)
    player:timer(1000, function(player)
        if player:getLevel() > 1 then
            player:addTitle(xi.title.TEST_TITLE)
        end
    end)
end

[xi.zone.TEST_ZONE] =
{
    ['Parser_NPC'] =
    {
        onTrigger = function(player, npc)
            if mission:getVar(player, 'Status') == 0 then
                return mission:progressEvent(10)
            end
        end,
    },
}
'''


def main():
    blocks=list(_balanced_function_blocks(SOURCE))
    assert len(blocks)==2,[(start,end,text.splitlines()[0]) for start,end,text in blocks]
    first_lines=[text.splitlines()[0].strip() for _start,_end,text in blocks]
    assert first_lines==[
        "helper = function(player)",
        "onTrigger = function(player, npc)",
    ],first_lines
    assert "player:timer(1000, function(player)" in blocks[0][2]
    assert all("fake_" not in text for _start,_end,text in blocks),blocks

    helpers=extract_helper_transitions(SOURCE)
    assert len(helpers)==1,helpers
    assert helpers[0].metadata["helper"]=="helper",helpers[0]
    assert any(effect.effect=="GRANT_TITLE" for effect in helpers[0].effects),helpers[0]

    machine=correlate_lsb_handlers(SOURCE,feature_id="mission:test:function-parser")
    triggers=[t for t in machine.transitions if t.trigger=="NPC_INTERACT"]
    assert len(triggers)==1,triggers
    assert triggers[0].event and triggers[0].event.event_id==10,triggers[0]
    assert triggers[0].event.actor=="Parser_NPC",triggers[0]

    print("mission function block parser self-test: PASS")


if __name__=="__main__":
    main()
