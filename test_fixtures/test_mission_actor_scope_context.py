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


ACTOR_LOCAL=r"""
[xi.zone.TEST_ZONE] =
{
    ['First_NPC'] =
    {
        onTrigger = function(player, npc)
            return mission:progressEvent(50)
        end,

        onEventFinish =
        {
            [50] = function(player, csid, option, npc)
                mission:setVar(player, 'First', 1)
            end,
        },
    },

    ['Second_NPC'] =
    {
        onTrigger = function(player, npc)
            return mission:progressEvent(50)
        end,

        onEventFinish =
        {
            [50] = function(player, csid, option, npc)
                mission:setVar(player, 'Second', 1)
            end,
        },
    },
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

    scoped=correlate_lsb_handlers(ACTOR_LOCAL,feature_id="mission:test:actor-local")
    raw_finishes=[
        t for t in scoped.transitions
        if t.trigger=="EVENT_FINISH" and t.event and t.event.event_id==50
    ]
    assert {t.event.actor for t in raw_finishes}=={"First_NPC","Second_NPC"},raw_finishes
    scoped_chained=chain_event_transitions(scoped)
    chains=[
        t for t in scoped_chained.transitions
        if t.metadata.get("logical_event_chain") and t.event and t.event.event_id==50
    ]
    assert len(chains)==2,chains
    by_actor={t.event.actor:t for t in chains}
    assert set(by_actor)=={"First_NPC","Second_NPC"},chains
    first_effects={e.subject for e in by_actor["First_NPC"].effects}
    second_effects={e.subject for e in by_actor["Second_NPC"].effects}
    assert "mission_var:First" in first_effects and "mission_var:Second" not in first_effects,first_effects
    assert "mission_var:Second" in second_effects and "mission_var:First" not in second_effects,second_effects
    assert scoped_chained.metadata["event_chain_actor_scope"] is True,scoped_chained.metadata

    print("mission actor scope context self-test: PASS")


if __name__=="__main__":
    main()
