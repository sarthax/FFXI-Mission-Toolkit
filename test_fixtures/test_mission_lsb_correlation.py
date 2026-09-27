#!/usr/bin/env python3
from workbench.plugins.domain.mission_lsb_extract import correlate_lsb_handlers, materialize_channel_states

SAMPLE=r"""
[xi.zone.MISAREAUX_COAST] =
{
    ['_0p2'] =
    {
        onTrigger = function(player, npc)
            if mission:getVar(player, 'Status') == 0 then
                return mission:progressEvent(6)
            end
        end,
    },
    onEventFinish =
    {
        [6] = function(player, csid, option, npc)
            mission:setVar(player, 'Status', 1)
        end,
    },
}
[xi.zone.MONARCH_LINN] =
{
    onEventFinish =
    {
        [32001] = function(player, csid, option, npc)
            if
                mission:getVar(player, 'Status') == 2 and
                player:getLocalVar('battlefieldWin') == xi.battlefield.id.ANCIENT_VOWS
            then
                mission:complete(player)
                player:setPos(694, -5.5, -619, 74, 107)
            end
        end,
    },
}
"""

def main():
    m=correlate_lsb_handlers(SAMPLE,feature_id="mission:test")
    assert not m.validate(),m.validate()
    trigger=next(t for t in m.transitions if t.trigger=="NPC_INTERACT")
    assert trigger.event and trigger.event.event_id==6,trigger
    assert trigger.event.zone=="MISAREAUX_COAST",trigger
    assert trigger.event.actor=="_0p2",trigger
    assert trigger.gate.conditions[0].subject=="mission_var:Status",trigger

    finish=next(t for t in m.transitions if t.event and t.event.event_id==6 and t.trigger=="EVENT_FINISH")
    assert any(e.subject=="mission_var:Status" for e in finish.effects),finish

    win=next(t for t in m.transitions if t.event and t.event.event_id==32001)
    assert any(c.operator=="BATTLEFIELD_WON" and c.subject=="battlefield:ANCIENT_VOWS" for c in win.gate.conditions),win
    assert any(e.effect=="COMPLETE" for e in win.effects),win
    assert any(e.effect=="TELEPORT" for e in win.effects),win
    mm=materialize_channel_states(m)
    trigger2=next(t for t in mm.transitions if t.trigger=="NPC_INTERACT")
    assert trigger2.from_state=="state:mission_var:Status=0",trigger2
    finish2=next(t for t in mm.transitions if t.event and t.event.event_id==6 and t.trigger=="EVENT_FINISH")
    assert finish2.to_state=="state:mission_var:Status=1",finish2
    print("LSB handler correlation self-test: PASS")
    print("transitions",len(m.transitions))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
