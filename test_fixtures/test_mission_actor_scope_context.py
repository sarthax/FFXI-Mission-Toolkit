#!/usr/bin/env python3
"""Regression for Lua table-scoped mission actor context."""
from workbench.plugins.domain.mission_lsb_extract import (
    chain_event_transitions,
    correlate_lsb_handlers,
)


SOURCE=r"""
[xi.zone.TEST_ZONE] =
{
    ['First_NPC'] =
    {
        onTrigger = function(player, npc)
            return mission:progressEvent(10)
        end,
    },

    ['Second_NPC'] =
    {
        onTrigger = function(player, npc)
            return mission:progressEvent(20)
        end,
    },

    ['Declarative_NPC'] = mission:progressEvent(30),

    onEventFinish =
    {
        [10] = function(player, csid, option, npc)
            mission:setVar(player, 'Status', 1)
        end,

        [20] = function(player, csid, option, npc)
            mission:setVar(player, 'Status', 2)
        end,
    },

    onZoneIn = function(player, prevZone)
        if mission:getVar(player, 'Status') == 0 then
            return 40
        end
    end,
}
"""


def main():
    machine=correlate_lsb_handlers(SOURCE,feature_id="mission:test:actor-scope")
    assert not machine.validate(),machine.validate()

    triggers={
        t.event.event_id:t for t in machine.transitions
        if t.trigger=="NPC_INTERACT" and t.event
    }
    assert triggers[10].event.actor=="First_NPC",triggers[10]
    assert triggers[20].event.actor=="Second_NPC",triggers[20]
    assert triggers[30].event.actor=="Declarative_NPC",triggers[30]

    finishes={
        t.event.event_id:t for t in machine.transitions
        if t.trigger=="EVENT_FINISH" and t.event
    }
    assert finishes[10].event.zone=="TEST_ZONE",finishes[10]
    assert finishes[20].event.zone=="TEST_ZONE",finishes[20]
    assert finishes[10].event.actor is None,finishes[10]
    assert finishes[20].event.actor is None,finishes[20]
    assert finishes[10].metadata["context_basis"]=="table_scope",finishes[10].metadata

    zone_in=next(t for t in machine.transitions if t.trigger=="ZONE_IN")
    assert zone_in.metadata["zone"]=="TEST_ZONE",zone_in
    assert zone_in.metadata["actor"] is None,zone_in

    chained=chain_event_transitions(machine)
    c10=next(
        t for t in chained.transitions
        if t.metadata.get("logical_event_chain") and t.event and t.event.event_id==10
    )
    c20=next(
        t for t in chained.transitions
        if t.metadata.get("logical_event_chain") and t.event and t.event.event_id==20
    )
    assert c10.event.actor=="First_NPC",c10
    assert c20.event.actor=="Second_NPC",c20

    print("mission actor scope context self-test: PASS")


if __name__=="__main__":
    main()
