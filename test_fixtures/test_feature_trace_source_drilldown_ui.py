#!/usr/bin/env python3
"""Regression contract for Feature Trace cross-tool source drill-down navigation."""
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def main():
    feature=(ROOT/"gui/templates/feature_trace.html").read_text(encoding="utf-8")
    behavior=(ROOT/"gui/templates/behavior_visualizer.html").read_text(encoding="utf-8")
    event=(ROOT/"gui/templates/event_view.html").read_text(encoding="utf-8")
    sql=(ROOT/"gui/templates/sql.html").read_text(encoding="utf-8")
    server=(ROOT/"gui_server.py").read_text(encoding="utf-8")

    for text in (
        "Server Lua drill-down",
        "Open exact Behavior source",
        "Search Behavior Inspector",
        "Behavior graph JSON",
        "Source preview",
        "Open indexed SQL row",
        "Indexed SQL row",
        "Trace this representation",
    ):
        assert text in feature,text

    assert "Feature Trace for subject" in behavior
    assert "Trace source path" in behavior
    assert "Graph JSON" in behavior
    assert "/features/trace?q={{ row.name|urlencode }}" in behavior

    assert "Behavior source" in event
    assert "Feature Trace script/entity" in event
    assert "/behavior?source={{ s.path|urlencode }}" in event

    assert "Feature Trace" in sql
    assert "/features/trace?q={{ r[entity_col]|urlencode }}" in sql

    assert "def _feature_trace_norm_source_name" in server
    assert "def _feature_trace_branch_source_drilldown" in server
    assert "find_behavior_sources_multi({server: source_root}" in server
    assert "inspect_lsb_behavior(source_root, chosen" in server
    assert "candidate.read_text(encoding="utf-8", errors="replace")" in server
    assert "len(exact) != 1" in server
    assert '"candidate_count"' in server
    assert '"events": events' in server
    assert '"candidates"' in server
    assert '"match_basis"' in server
    assert "multiple exact-normalized script/entity names" in server
    assert "fuzzy/content Behavior Inspector matches only" in server
    assert "drill.candidates" in feature
    assert "match basis:" in feature

    print("Feature Trace cross-tool source drill-down regression: PASS")


if __name__=="__main__":
    main()
