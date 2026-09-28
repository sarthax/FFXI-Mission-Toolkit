#!/usr/bin/env python3
"""Regression for exact mission distance comparator semantics."""
from workbench.plugins.domain.mission_lsb_extract import correlate_lsb_handlers


SOURCE=r"""
[xi.zone.TEST_ZONE] =
{
    ['LT_NPC'] =
    {
        onTrigger = function(player, npc)
            if player:checkDistance(npc) < 1.5 then
                return mission:progressEvent(1)
            end
        end,
    },
    ['LE_NPC'] =
    {
        onTrigger = function(player, npc)
            if player:checkDistance(npc) <= 2 then
                return mission:progressEvent(2)
            end
        end,
    },
    ['GT_NPC'] =
    {
        onTrigger = function(player, npc)
            if player:checkDistance(npc) > 3.25 then
                return mission:progressEvent(3)
            end
        end,
    },
    ['GE_NPC'] =
    {
        onTrigger = function(player, npc)
            if player:checkDistance(npc) >= 4 then
                return mission:progressEvent(4)
            end
        end,
    },
}
"""


def main():
    machine=correlate_lsb_handlers(SOURCE,feature_id="mission:test:distance")
    expected={
        1:("LT",1.5),
        2:("LE",2.0),
        3:("GT",3.25),
        4:("GE",4.0),
    }
    for event_id,(operator,value) in expected.items():
        transition=next(
            t for t in machine.transitions
            if t.event and t.event.event_id==event_id
        )
        distance=next(
            c for c in transition.gate.conditions
            if c.subject=="player_to_actor_distance"
        )
        assert distance.operator==operator,(event_id,distance)
        assert distance.value==value,(event_id,distance)

    print("mission distance comparator self-test: PASS")


if __name__=="__main__":
    main()
