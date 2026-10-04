from __future__ import annotations

import sqlite3

from workbench.core import graph
from workbench.devtools.features import trace as feature_trace
from workbench.devtools.features.trace_benchmarks import SCENARIOS, SCENARIO_BY_ID, evaluate_terms
from workbench.devtools.features.trace_generators import generators_for
from workbench.devtools.features.trace_modes import mode_options, normalize_mode
from workbench.devtools.features.trace_resolver import resolve_candidates


def _graph():
    con = sqlite3.connect(":memory:")
    con.executescript(graph.SCHEMA)
    return con


def test_resolver_prefers_exact_identity_and_groups_representations():
    rows = [
        {"node_id": "catalog:sql_npc_list:16974347", "node_type": "NPC", "display_name": "Raustigne", "numeric_id": 16974347, "provider": "server-sql"},
        {"node_id": "catalog:identity_records:client-raustigne", "node_type": "CLIENT_IDENTITY", "display_name": "Raustigne", "aliases": {"entity_id": 16974347}, "provider": "client-identity"},
        {"node_id": "catalog:sql_npc_list:123", "node_type": "NPC", "display_name": "Raustigne's Friend", "numeric_id": 123, "provider": "server-sql"},
    ]
    resolved = resolve_candidates("16974347", rows)
    assert resolved.status == "RESOLVED"
    assert resolved.object_kind == "entity"
    assert resolved.confidence == "VERIFIED"
    group = next(g for g in resolved.groups if g["identity"] == "16974347")
    assert len(group["representations"]) == 2


def test_resolver_keeps_ambiguous_partial_names_unresolved():
    rows = [
        {"node_id": "npc:a", "node_type": "NPC", "display_name": "Iron Gate"},
        {"node_id": "npc:b", "node_type": "NPC", "display_name": "Iron Gatekeeper"},
    ]
    result = resolve_candidates("Iron", rows)
    assert result.status == "AMBIGUOUS"
    assert result.root is None


def test_trace_modes_narrow_recorded_edges_without_breaking_default_trace():
    con = _graph()
    for node_id, node_type in (("root", "MISSION"), ("event:10", "EVENT"), ("reward:item", "ITEM"), ("cpp:helper", "FUNCTION")):
        con.execute("INSERT INTO entities(entity_id,entity_type,display_name,metadata_json) VALUES(?,?,?,?)", (node_id, node_type, node_id, "{}"))
    rows = (
        ("e1", "root", "event:10", "TRIGGERS_EVENT", None, "VERIFIED", "DISCOVERED", "{}", None),
        ("e2", "root", "reward:item", "GRANTS_REWARD", None, "VERIFIED", "DISCOVERED", "{}", None),
        ("e3", "root", "cpp:helper", "BINDS_CPP_FUNCTION", None, "VERIFIED", "DISCOVERED", "{}", None),
    )
    con.executemany("INSERT INTO entity_relationships VALUES(?,?,?,?,?,?,?,?,?)", rows)
    con.commit()

    ordinary = feature_trace.trace(con, "root", 1, "out")
    assert {e["relationship"] for e in ordinary["edges"]} == {"TRIGGERS_EVENT", "GRANTS_REWARD", "BINDS_CPP_FUNCTION"}

    mission = feature_trace.trace(con, "root", 1, "both", mode="mission")
    assert mission["trace_mode"]["id"] == "mission"
    assert "TRIGGERS_EVENT" in {e["relationship"] for e in mission["edges"]}
    assert "GRANTS_REWARD" in {e["relationship"] for e in mission["edges"]}
    assert mission["root_kind"] == "mission"
    assert any(row["id"] == "mission-state" for row in mission["generator_plan"])
    con.close()


def test_mode_and_generator_registry_cover_all_seven_expansion_phases():
    ids = {row["id"] for row in mode_options()}
    assert {"implementation", "triggers", "effects", "dependencies", "mission", "runtime", "identity", "diagnose", "all"}.issubset(ids)
    assert normalize_mode("bogus").mode_id == "implementation"
    assert any(spec.generator_id == "mission-state" for spec in generators_for("mission", "mission"))
    assert any(spec.generator_id == "binding" for spec in generators_for("implementation", "implementation"))
    assert any(spec.generator_id == "runtime" for spec in generators_for("runtime", "runtime"))


def test_benchmark_catalog_is_broad_not_sample_specific():
    assert len(SCENARIOS) >= 30
    for required in ("wotg-fires", "absolute-virtue", "dsp-quest", "topaz-quest", "door", "vendor", "battlefield", "capture-entity", "binding"):
        assert required in SCENARIO_BY_ID
    result = evaluate_terms(["MISSION_EVENT", "SET_STATE", "COMPLETE_MISSION", "QUEST_PREREQUISITE"], SCENARIO_BY_ID["wotg-fires"])
    assert result["passed"] is True
