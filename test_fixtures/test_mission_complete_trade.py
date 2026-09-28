#!/usr/bin/env python3
"""Regression for executable-only COMPLETE_TRADE extraction."""
from workbench.plugins.domain.mission_lsb_extract import correlate_lsb_handlers

SOURCE=r"""
[xi.zone.TEST_ZONE] =
{
    ['Trade_NPC'] =
    {
        onTrade = function(player, npc, trade)
            if mission:getVar(player, 'Status') == 0 then
                -- player:tradeComplete()
                local fake = "player:tradeComplete()"
                return mission:progressEvent(10)
            else
                player:tradeComplete()
                return mission:progressEvent(11)
            end
        end,
    },
}
"""

def main():
    machine=correlate_lsb_handlers(SOURCE,feature_id="mission:test:trade-complete")
    rows=[t for t in machine.transitions if t.trigger=="TRADE"]
    assert len(rows)==2,rows
    event10=next(t for t in rows if t.event and t.event.event_id==10)
    event11=next(t for t in rows if t.event and t.event.event_id==11)
    assert not any(e.effect=="COMPLETE_TRADE" for e in event10.effects),event10
    assert [e.effect for e in event11.effects].count("COMPLETE_TRADE")==1,event11
    print("mission complete-trade extraction self-test: PASS")

if __name__=="__main__":
    main()
