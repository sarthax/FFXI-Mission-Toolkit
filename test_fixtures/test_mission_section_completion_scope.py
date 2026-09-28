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

    arnau = next(
        transition for transition in machine.transitions
        if transition.metadata.get("actor") == "Arnau"
        and transition.trigger == "NPC_INTERACT"
    )
    assert arnau.gate is not None, arnau
    assert {
        (condition.subject, condition.operator, condition.value)
        for condition in arnau.gate.conditions
    } == {("mission_status:SANDORIA", "EQ", 1)}, arnau.gate
    assert tuple(arnau.metadata.get("section_eligibility_conditions", ())) == (
        {"subject":"mission_status:SANDORIA","operator":"LE","value":14},
    ), arnau.metadata
    assert arnau.metadata.get("section_index") == 1, arnau.metadata

    completion_cid = next(
        transition for transition in machine.transitions
        if transition.metadata.get("actor") == "Cid"
        and transition.event
        and transition.event.event_id == 847
    )
    assert {
        (condition["subject"], condition["operator"], condition["value"])
        for condition in completion_cid.metadata.get("section_eligibility_conditions", ())
    } == {
        ("mission_status:SANDORIA", "EQ", 14),
        ("mission_status:WINDURST", "EQ", 14),
    }, completion_cid.metadata
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
    arnau_chain = next(
        transition for transition in chained.transitions
        if transition.metadata.get("trigger_transition_id") == arnau.transition_id
    )
    assert tuple(arnau_chain.metadata.get("section_eligibility_conditions", ())) == (
        {"subject":"mission_status:SANDORIA","operator":"LE","value":14},
    ), arnau_chain.metadata

    arnau_node = f"mission-transition:{chained.feature_id}:{arnau_chain.transition_id}"
    arnau_section_edges = [
        edge for edge in projection.edges
        if edge.source_node == arnau_node
        and edge.relationship == "REQUIRES"
        and edge.notes
        and edge.notes.startswith("section eligibility:")
    ]
    assert len(arnau_section_edges) == 1, arnau_section_edges
    assert arnau_section_edges[0].target_node.endswith("mission_status:SANDORIA"), arnau_section_edges
    assert arnau_section_edges[0].notes == "section eligibility: LE 14", arnau_section_edges
    assert arnau_section_edges[0].confidence == "INFERRED", arnau_section_edges

    arnau_handler_edges = [
        edge for edge in projection.edges
        if edge.source_node == arnau_node
        and edge.relationship == "REQUIRES"
        and edge.notes == "EQ 1"
    ]
    assert len(arnau_handler_edges) == 1, arnau_handler_edges

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

    aliased_multiline = """
mission.sections =
{
    {
        check = function(player, currentMission, missionStatus, vars)
            local leftStatus = player:getMissionStatus(
                mission.areaId,
                xi.mission.status.COP.LEFT
            )
            local rightStatus = player:getMissionStatus(
                mission.areaId,
                xi.mission.status.COP.RIGHT
            )

            return currentMission == mission.missionId and
                leftStatus >= 7 and
                rightStatus == 9
        end,

        [xi.zone.METALWORKS] =
        {
            ['Cid'] = mission:progressEvent(77),
        },
    },
}
"""
    alias_machine = correlate_lsb_handlers(
        aliased_multiline,
        feature_id="mission:test:aliased_multiline",
    )
    alias_transition = next(
        transition for transition in alias_machine.transitions
        if transition.metadata.get("actor") == "Cid"
    )
    assert {
        (condition["subject"], condition["operator"], condition["value"])
        for condition in alias_transition.metadata.get("section_eligibility_conditions", ())
    } == {
        ("mission_status:LEFT", "GE", 7),
        ("mission_status:RIGHT", "EQ", 9),
    }, alias_transition.metadata

    multiline_completion = """
mission.sections =
{
    {
        check = function(player, currentMission, missionStatus, vars)
            local leftStatus = player:getMissionStatus(
                mission.areaId,
                xi.mission.status.COP.LEFT
            )

            return currentMission == mission.missionId and
                leftStatus == 14 and
                player:getMissionStatus(
                    mission.areaId,
                    xi.mission.status.COP.RIGHT
                ) == 14
        end,

        [xi.zone.METALWORKS] =
        {
            onEventFinish =
            {
                [88] = function(player, csid, option, npc)
                    mission:complete(player)
                end,
            },
        },
    },
}
"""
    multiline_gate = extract_section_completion_gate(multiline_completion)
    assert multiline_gate is not None, multiline_gate
    assert _subjects(multiline_gate) == {
        "mission_status:LEFT",
        "mission_status:RIGHT",
    }, multiline_gate
    assert {condition.value for condition in multiline_gate.conditions} == {14}, multiline_gate

    disjunctive = """
mission.sections =
{
    {
        check = function(player, currentMission, missionStatus, vars)
            local leftStatus = player:getMissionStatus(
                mission.areaId,
                xi.mission.status.COP.LEFT
            )

            return leftStatus == 14 or
                player:getMissionStatus(mission.areaId, xi.mission.status.COP.RIGHT) == 14
        end,

        [xi.zone.METALWORKS] =
        {
            ['Cid'] = mission:progressEvent(99),
        },
    },
}
"""
    disjunctive_machine = correlate_lsb_handlers(
        disjunctive,
        feature_id="mission:test:disjunctive",
    )
    disjunctive_transition = next(
        transition for transition in disjunctive_machine.transitions
        if transition.metadata.get("actor") == "Cid"
    )
    assert not disjunctive_transition.metadata.get("section_eligibility_conditions"), disjunctive_transition.metadata

    print("Mission section completion scope regression: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
