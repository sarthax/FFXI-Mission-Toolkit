#!/usr/bin/env python3
"""Regression for section-scoped literal mission completion convergence."""
from pathlib import Path

from workbench.plugins.domain.mission_lsb_extract import extract_section_completion_gate


ROOT = Path(__file__).resolve().parents[1]


def _subjects(gate):
    return {condition.subject for condition in gate.conditions} if gate else set()


def main():
    road_forks = (ROOT / "test_fixtures" / "fixtures" / "lsb_the_road_forks.lua").read_text(encoding="utf-8")
    gate = extract_section_completion_gate(road_forks)
    assert gate is not None, gate
    assert gate.logic == "ALL", gate
    assert _subjects(gate) == {"mission_status:SANDORIA", "mission_status:WINDURST"}, gate
    assert {condition.value for condition in gate.conditions} == {14}, gate

    scoped = """
mission.sections =
{
    {
        check = function(player, currentMission, missionStatus, vars)
            return player:getMissionStatus(mission.areaId, xi.mission.status.COP.UNRELATED_A) == 14 and
                player:getMissionStatus(mission.areaId, xi.mission.status.COP.UNRELATED_B) == 14
        end,

        [xi.zone.PORT_JEUNO] =
        {
            ['Other'] = mission:event(1),
        },
    },

    {
        check = function(player, currentMission, missionStatus, vars)
            return player:getMissionStatus(mission.areaId, xi.mission.status.COP.PATH_A) == 7 and
                player:getMissionStatus(mission.areaId, xi.mission.status.COP.PATH_B) == 7
        end,

        [xi.zone.METALWORKS] =
        {
            onEventFinish =
            {
                [99] = function(player, csid, option, npc)
                    mission:complete(player)
                end,
            },
        },
    },
}
"""
    gate = extract_section_completion_gate(scoped)
    assert gate is not None, gate
    assert _subjects(gate) == {"mission_status:PATH_A", "mission_status:PATH_B"}, gate
    assert {condition.value for condition in gate.conditions} == {7}, gate

    ambiguous = """
mission.sections =
{
    {
        check = function(player, currentMission, missionStatus, vars)
            return player:getMissionStatus(mission.areaId, xi.mission.status.COP.LEFT_A) == 9 and
                player:getMissionStatus(mission.areaId, xi.mission.status.COP.LEFT_B) == 9
        end,
        [xi.zone.BASTOK_MARKETS] =
        {
            onEventFinish =
            {
                [10] = function(player, csid, option, npc)
                    mission:complete(player)
                end,
            },
        },
    },
    {
        check = function(player, currentMission, missionStatus, vars)
            return player:getMissionStatus(mission.areaId, xi.mission.status.COP.RIGHT_A) == 9 and
                player:getMissionStatus(mission.areaId, xi.mission.status.COP.RIGHT_B) == 9
        end,
        [xi.zone.WINDURST_WOODS] =
        {
            onEventFinish =
            {
                [11] = function(player, csid, option, npc)
                    mission:complete(player)
                end,
            },
        },
    },
}
"""
    assert extract_section_completion_gate(ambiguous) is None

    unscoped = """
if player:getMissionStatus(mission.areaId, xi.mission.status.COP.A) == 14 and
   player:getMissionStatus(mission.areaId, xi.mission.status.COP.B) == 14 then
    mission:complete(player)
end
"""
    assert extract_section_completion_gate(unscoped) is None

    print("Mission section completion scope regression: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
