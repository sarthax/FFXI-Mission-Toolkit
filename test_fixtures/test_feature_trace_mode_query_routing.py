from __future__ import annotations

import sqlite3

from workbench.core import graph
from workbench.devtools.features import trace as feature_trace


def _db():
    con = sqlite3.connect(":memory:")
    con.executescript(graph.SCHEMA)
    for node_id, node_type in (("mission:test", "MISSION"), ("event:1", "EVENT"), ("cpp:test", "FUNCTION")):
        con.execute(
            "INSERT INTO entities(entity_id,entity_type,display_name,metadata_json) VALUES(?,?,?,?)",
            (node_id, node_type, node_id, "{}"),
        )
    con.executemany(
        "INSERT INTO entity_relationships VALUES(?,?,?,?,?,?,?,?,?)",
        (
            ("edge:event", "mission:test", "event:1", "TRIGGERS_EVENT", None, "VERIFIED", "DISCOVERED", "{}", None),
            ("edge:cpp", "mission:test", "cpp:test", "BINDS_CPP_FUNCTION", None, "VERIFIED", "DISCOVERED", "{}", None),
        ),
    )
    con.commit()
    return con


def test_split_mode_query_leaves_ordinary_search_untouched():
    assert feature_trace.split_mode_query("Cait Sith") == (None, "Cait Sith")
    assert feature_trace.split_mode_query("@mission Cait Sith") == ("mission", "Cait Sith")
    assert feature_trace.split_mode_query("@runtime 16974347") == ("runtime", "16974347")
    assert feature_trace.split_mode_query("@not-a-mode Cait Sith") == (None, "@not-a-mode Cait Sith")


def test_existing_gui_style_query_helpers_carry_explicit_mode_to_trace():
    con = _db()
    # Mirrors the existing /features/trace flow: diagnostics/node lookup happen before trace(),
    # and the route itself does not need a new query parameter for the request-scoped mode hint.
    feature_trace.entity_query_diagnostics(con, con, "@mission mission:test")
    info = feature_trace.node_info(con, "@mission mission:test", con)
    assert info["known"] is True
    result = feature_trace.trace(con, "mission:test", 1, "both", con)
    assert result["trace_mode"]["id"] == "mission"
    relationships = {row["relationship"] for row in result["edges"]}
    assert "TRIGGERS_EVENT" in relationships
    assert "BINDS_CPP_FUNCTION" not in relationships
    con.close()


def test_direct_programmatic_trace_without_prefix_remains_unfiltered():
    con = _db()
    result = feature_trace.trace(con, "mission:test", 1, "out", con)
    assert "trace_mode" not in result
    assert {row["relationship"] for row in result["edges"]} == {"TRIGGERS_EVENT", "BINDS_CPP_FUNCTION"}
    con.close()


def test_prefix_on_root_also_works_without_prior_query_helper():
    con = _db()
    result = feature_trace.trace(con, "@implementation mission:test", 1, "out", con)
    assert result["root"] == "mission:test"
    assert result["trace_mode"]["id"] == "implementation"
    relationships = {row["relationship"] for row in result["edges"]}
    assert "BINDS_CPP_FUNCTION" in relationships
    assert "TRIGGERS_EVENT" not in relationships
    con.close()
