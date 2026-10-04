from __future__ import annotations

import sqlite3
from types import SimpleNamespace

from workbench.core import graph
from workbench.devtools.features import trace as feature_trace
from workbench.devtools.features.trace_expansion import (
    binding_engine_candidates,
    mission_state_candidates,
    provider_candidates,
)


def _provider_db():
    con = sqlite3.connect(":memory:")
    con.executescript(graph.SCHEMA)
    con.executescript("""
    CREATE TABLE topaz_mob_spawn_points(mobid INTEGER PRIMARY KEY,mobname TEXT,groupid INTEGER,pos_x REAL,pos_y REAL,pos_z REAL,pos_rot INTEGER);
    CREATE TABLE topaz_mob_groups(zoneid INTEGER,groupid INTEGER,name TEXT,poolid INTEGER,dropid INTEGER,respawntime INTEGER,minLevel INTEGER,maxLevel INTEGER,PRIMARY KEY(zoneid,groupid));
    CREATE TABLE topaz_mob_pools(poolid INTEGER PRIMARY KEY,name TEXT,familyid INTEGER,modelid INTEGER);
    """)
    zoneid = 100
    mobid = (zoneid << 12) + 1
    con.execute("INSERT INTO topaz_mob_spawn_points VALUES(?,?,?,?,?,?,?)", (mobid, "Trace Test NM", 7, 0, 0, 0, 0))
    con.execute("INSERT INTO topaz_mob_groups VALUES(?,?,?,?,?,?,?,?)", (zoneid, 7, "Trace Test Group", 22, 0, 300, 75, 75))
    con.execute("INSERT INTO topaz_mob_pools VALUES(?,?,?,?)", (22, "Trace Test Pool", 10, 123))
    con.commit()
    return con, mobid


def test_provider_expansion_walks_generic_topaz_spawn_group_pool_chain():
    con, mobid = _provider_db()
    root = f"catalog:topaz_mob_spawn_points:{mobid}"
    rows = provider_candidates(con, root, mode="implementation", max_depth=3)
    relationships = [row.relationship for row in rows]
    assert "SPAWN_USES_GROUP" in relationships
    assert "GROUP_USES_POOL" in relationships
    assert all(row.confidence == "VERIFIED" for row in rows)

    traced = feature_trace.trace(con, root, 3, "both", con, mode="implementation")
    generated = traced["generated_relationships"]
    assert {row["relationship"] for row in generated} >= {"SPAWN_USES_GROUP", "GROUP_USES_POOL"}
    assert traced["generated_relationship_count"] >= 2
    assert any(row["id"] == "lua-sql" and row["active"] for row in traced["generator_plan"])
    # Focused display graph now includes read-only generated provider evidence, while the
    # persisted-only collection stays empty for this provider-only fixture.
    assert traced["canonical_edges"] == []
    assert {row["relationship"] for row in traced["edges"]} >= {"SPAWN_USES_GROUP", "GROUP_USES_POOL"}
    assert all(row.get("generated") is True for row in traced["edges"])
    assert all(row["status"] == "GENERATED_EVIDENCE" for row in traced["edges"])
    names = {
        rep.get("display_name")
        for node in traced["nodes"]
        for rep in (node.get("representations") or [])
    }
    assert "Trace Test Group" in names
    assert "Trace Test Pool" in names
    con.close()


def test_mission_state_machine_projects_framework_neutral_progression_candidates():
    condition = SimpleNamespace(subject="charvar:LegacyStatus", operator="EQ", value=2)
    gate = SimpleNamespace(conditions=(condition,))
    event = SimpleNamespace(zone="BASTOK_MARKETS_S", event_id=100, actor="Engelhart")
    effects = (
        SimpleNamespace(effect="SET_VAR", subject="charvar:LegacyStatus", value=3),
        SimpleNamespace(effect="GRANT", subject="key_item:TEST_KEY", value=None),
        SimpleNamespace(effect="COMPLETE", subject="mission", value=None),
    )
    transition = SimpleNamespace(
        transition_id="legacy:engelhart:100", gate=gate, event=event, effects=effects
    )
    machine = SimpleNamespace(transitions=(transition,))
    rows = mission_state_candidates(machine, "mission:wotg:test")
    relationships = {row.relationship for row in rows}
    assert "HAS_MISSION_TRANSITION" in relationships
    assert "TRIGGERS_EVENT" in relationships
    assert "REQUIRES_STATE" in relationships
    assert "SETS_MISSION_STATE" in relationships
    assert "GRANTS_REWARD" in relationships
    assert "COMPLETES_MISSION_STATE" in relationships
    assert all(row.generator == "mission-state" for row in rows)


def test_binding_engine_candidates_preserve_lua_and_cpp_evidence():
    engine = {
        "direct_calls": [{
            "qualified_name": "player.addKeyItem",
            "line": 42,
            "source_line": "player:addKeyItem(tpz.ki.TEST_KEY)",
            "binding": {
                "status": "EXACT",
                "locations": [{"class": "CLuaBaseEntity", "file": "lua_baseentity.cpp", "line": 123}],
            },
        }]
    }
    rows = binding_engine_candidates(engine, "npc:engelhart")
    relationships = {row.relationship for row in rows}
    assert relationships == {"CALLS_LUA_API", "BINDS_CPP_FUNCTION"}
    cpp = next(row for row in rows if row.relationship == "BINDS_CPP_FUNCTION")
    assert cpp.confidence == "VERIFIED"
    assert cpp.evidence[0]["file"] == "lua_baseentity.cpp"
