#!/usr/bin/env python3
"""Generic scripted-entity behavior model regression using the AV/Jailer proof."""
from __future__ import annotations

import json
import sqlite3
import tempfile
from pathlib import Path

from workbench.devtools.features import trace as feature_trace
from workbench.core import graph
from workbench.plugins.domain.scripted_behavior import (
    behavior_map_from_probe,
    persist_scripted_behavior,
    project_scripted_behavior,
)


ROOT=Path(__file__).resolve().parents[1]
PROBE=ROOT/"test_fixtures"/"fixtures"/"absolute_virtue_behavior_probe.json"


def main():
    payload=json.loads(PROBE.read_text(encoding="utf-8"))
    behavior=behavior_map_from_probe(
        payload,
        feature_id="feature:scripted-behavior:absolute-virtue",
    )
    assert behavior.subject=="Absolute Virtue",behavior
    assert behavior.zone=="Al'Taieu",behavior
    assert len(behavior.hooks)>=9,behavior.hooks
    kinds={rule.kind for rule in behavior.rules}
    assert {
        "spawn_from_death",
        "inherit_runtime_target",
        "cross_entity_state",
        "hp_threshold",
        "timed_random_action",
        "player_action_response",
        "magic_response",
        "spell_override",
        "cleanup",
        "loot_override",
    } <= kinds,kinds

    spawn=next(rule for rule in behavior.rules if rule.kind=="spawn_from_death")
    assert spawn.subject=="Jailer of Love",spawn
    assert spawn.target=="Absolute Virtue",spawn
    assert spawn.trigger=="ENTITY_DEATH",spawn
    assert any(effect.effect=="SPAWN_ENTITY" for effect in spawn.effects),spawn

    hp=next(rule for rule in behavior.rules if rule.kind=="hp_threshold")
    assert any(
        condition.operator=="HPP_AT_OR_BELOW" and condition.value==60
        for condition in hp.conditions
    ),hp

    projection=project_scripted_behavior(
        behavior,
        source_snapshot_id="lsb:test",
        evidence_location=str(PROBE.relative_to(ROOT)),
    )
    entity_types={entity.entity_type for entity in projection.entities}
    assert {"SCRIPTED_BEHAVIOR_MAP","ENTITY_HOOK","BEHAVIOR_RULE","SCRIPTED_ENTITY"} <= entity_types,entity_types
    relationships={edge.relationship for edge in projection.edges}
    assert {
        "HAS_BEHAVIOR_MAP",
        "HAS_HOOK",
        "HAS_BEHAVIOR_RULE",
        "BEHAVIOR_SUBJECT",
        "REFERENCES_ACTOR",
        "REQUIRES",
    } <= relationships,relationships

    jailer=next(
        entity for entity in projection.entities
        if entity.display_name=="Jailer of Love"
    )
    assert any(
        edge.target_node==jailer.entity_id and edge.relationship=="REQUIRES"
        for edge in projection.edges
    ),projection.edges

    with tempfile.TemporaryDirectory() as td:
        db=Path(td)/"workbench.db"
        con=graph.init_db(db)
        persist_scripted_behavior(con,projection)
        trace=feature_trace.trace(
            con,
            projection.feature.feature_id,
            depth=4,
            direction="out",
        )
        traced_types={
            rep["node_type"]
            for node in trace["nodes"]
            for rep in node.get("representations",())
            if rep.get("node_type")
        }
        assert "SCRIPTED_BEHAVIOR_MAP" in traced_types,traced_types
        assert "BEHAVIOR_RULE" in traced_types,traced_types
        assert any(
            edge["relationship"]=="REQUIRES" and edge["target_node"]==jailer.entity_id
            for edge in trace["edges"]
        ),trace["edges"]
        con.close()

    print("generic scripted behavior model regression: PASS")


if __name__=="__main__":
    main()
