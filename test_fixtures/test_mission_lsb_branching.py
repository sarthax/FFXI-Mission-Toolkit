#!/usr/bin/env python3
"""Regression for branch-aware LSB mission handler extraction."""
from workbench.plugins.domain.mission_lsb_extract import (
    chain_event_transitions,
    correlate_lsb_handlers,
)


SAMPLE=r"""
[xi.zone.TEST_ZONE] =
{
    ['Branching_NPC'] =
    {
        onTrigger = function(player, npc)
            if mission:getVar(player, 'Status') == 0 then
                return mission:progressEvent(6)
            elseif mission:getVar(player, 'Status') == 1 then
                return mission:progressEvent(7)
            else
                return mission:progressEvent(8)
            end
        end,
    },

    onEventFinish =
    {
        [6] = function(player, csid, option, npc)
            if player:hasKeyItem(xi.keyItem.TEST_A) then
                player:delKeyItem(xi.keyItem.TEST_A)
                mission:setVar(player, 'Status', 2)
            else
                npcUtil.giveKeyItem(player, xi.keyItem.TEST_B)
                mission:setVar(player, 'Status', 3)
            end
        end,

        [7] = function(player, csid, option, npc)
            mission:setVar(player, 'Status', 4)
        end,

        [8] = function(player, csid, option, npc)
            mission:setVar(player, 'Status', 5)
        end,
    },
}
"""


def _event(machine,event_id,trigger=None):
    return [
        t for t in machine.transitions
        if t.event and t.event.event_id==event_id
        and (trigger is None or t.trigger==trigger)
    ]


def main():
    machine=correlate_lsb_handlers(SAMPLE,feature_id="mission:test:branching")
    assert not machine.validate(),machine.validate()

    triggers=[t for t in machine.transitions if t.trigger=="NPC_INTERACT"]
    assert {t.event.event_id for t in triggers}=={6,7,8},triggers
    assert len(triggers)==3,triggers

    t6=next(t for t in triggers if t.event.event_id==6)
    t7=next(t for t in triggers if t.event.event_id==7)
    t8=next(t for t in triggers if t.event.event_id==8)
    assert [c.value for c in t6.gate.conditions if c.subject=="mission_var:Status"]==[0],t6
    assert [c.value for c in t7.gate.conditions if c.subject=="mission_var:Status"]==[1],t7
    assert t8.gate is None,t8
    assert t6.metadata["branch_path"]==("if",),t6.metadata
    assert t7.metadata["branch_path"]==("elseif",),t7.metadata
    assert t8.metadata["branch_path"]==("else",),t8.metadata
    assert t6.metadata["branch_guard_complete"] is True,t6.metadata
    assert t7.metadata["branch_guard_complete"] is False,t7.metadata
    assert t8.metadata["branch_guard_complete"] is False,t8.metadata
    assert t7.confidence=="UNKNOWN" and t8.confidence=="UNKNOWN",(t7,t8)

    finish6=_event(machine,6,"EVENT_FINISH")
    assert len(finish6)==2,finish6
    guarded=next(t for t in finish6 if t.gate is not None)
    fallback=next(t for t in finish6 if t.gate is None)
    guarded_effects={(e.effect,e.subject,e.value) for e in guarded.effects}
    fallback_effects={(e.effect,e.subject,e.value) for e in fallback.effects}
    assert ("REMOVE","key_item:TEST_A",None) in guarded_effects,guarded_effects
    assert ("SET_VAR","mission_var:Status","2") in guarded_effects,guarded_effects
    assert ("GRANT","key_item:TEST_B",None) not in guarded_effects,guarded_effects
    assert ("GRANT","key_item:TEST_B",None) in fallback_effects,fallback_effects
    assert ("SET_VAR","mission_var:Status","3") in fallback_effects,fallback_effects
    assert ("REMOVE","key_item:TEST_A",None) not in fallback_effects,fallback_effects

    chained=chain_event_transitions(machine)
    event6_chains=[
        t for t in chained.transitions
        if t.metadata.get("logical_event_chain") and t.event and t.event.event_id==6
    ]
    assert len(event6_chains)==2,event6_chains
    assert {t.to_state for t in event6_chains}=={
        "state:mission_var:Status=2",
        "state:mission_var:Status=3",
    },event6_chains
    assert any(
        any(e.effect=="REMOVE" and e.subject=="key_item:TEST_A" for e in t.effects)
        and not any(e.effect=="GRANT" and e.subject=="key_item:TEST_B" for e in t.effects)
        for t in event6_chains
    ),event6_chains
    assert any(
        any(e.effect=="GRANT" and e.subject=="key_item:TEST_B" for e in t.effects)
        and not any(e.effect=="REMOVE" and e.subject=="key_item:TEST_A" for e in t.effects)
        for t in event6_chains
    ),event6_chains

    assert machine.metadata["branch_alternatives"]>=5,machine.metadata
    assert machine.metadata["incomplete_branch_guards"]>=3,machine.metadata
    assert chained.metadata["event_chain_branch_fanout"]>=1,chained.metadata

    print("branch-aware mission extraction self-test: PASS")


if __name__=="__main__":
    main()
