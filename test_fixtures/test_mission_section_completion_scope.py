#!/usr/bin/env python3
"""Regression for section-scoped literal mission completion convergence."""
from pathlib import Path

from workbench.plugins.domain.mission_graph_emit import project_mission_graph
from workbench.plugins.domain.mission_lsb_extract import (
    chain_event_transitions,
    correlate_lsb_handlers,
    extract_section_completion_gate,
)


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

    machine = correlate_lsb_handlers(road_forks, feature_id="mission:cop:the_road_forks")
    assert machine.completion_gate is not None, machine
    assert _subjects(machine.completion_gate) == {"mission_status:SANDORIA", "mission_status:WINDURST"}, machine.completion_gate
    assert {condition.value for condition in machine.completion_gate.conditions} == {14}, machine.completion_gate
    assert machine.metadata.get("extractor") == "lsb_static_literal", machine.metadata

    chained = chain_event_transitions(machine)
    assert chained.completion_gate == machine.completion_gate, (machine.completion_gate, chained.completion_gate)

    projection = project_mission_graph(
        chained,
        source_path="scripts/missions/cop/the_road_forks.lua",
        source_snapshot_id="fixture:road-forks",
        source_family="LSB",
    )
    feature_gate = projection.feature.metadata.get("completion_gate")
    assert feature_gate and feature_gate["logic"] == "ALL", feature_gate
    assert {
        row["subject"] for row in feature_gate["conditions"]
    } == {"mission_status:SANDORIA", "mission_status:WINDURST"}, feature_gate
    completion_edges = [
        edge for edge in projection.edges
        if edge.source_node == chained.feature_id
        and edge.relationship == "REQUIRES"
        and edge.notes
        and edge.notes.startswith("mission completion gate:")
    ]
    assert len(completion_edges) == 2, completion_edges
    assert {
        edge.target_node for edge in completion_edges
    } == {
        "mission-subject:mission:cop:the_road_forks:mission_status:SANDORIA",
        "mission-subject:mission:cop:the_road_forks:mission_status:WINDURST",
    }, completion_edges
    assert all(edge.confidence == "INFERRED" for edge in completion_edges), completion_edges
    assert all(edge.status == "DISCOVERED" for edge in completion_edges), completion_edges

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
