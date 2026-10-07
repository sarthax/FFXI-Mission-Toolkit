#!/usr/bin/env python3
"""Regression contract for Feature Trace cross-tool source drill-down navigation."""
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
WORKBENCH_SRC=ROOT/"src/workbench"


def main():
    feature=(ROOT/"gui/templates/feature_trace.html").read_text(encoding="utf-8")
    behavior=(ROOT/"gui/templates/behavior_visualizer.html").read_text(encoding="utf-8")
    event=(ROOT/"gui/templates/event_view.html").read_text(encoding="utf-8")
    sql=(ROOT/"gui/templates/sql.html").read_text(encoding="utf-8")
    server=(WORKBENCH_SRC/"app/_host_impl.py").read_text(encoding="utf-8")
    binding_service=(WORKBENCH_SRC/"devtools/features/trace_binding_drilldown.py").read_text(encoding="utf-8")
    binding_shim=(WORKBENCH_SRC/"core/services/feature_trace_binding_drilldown.py").read_text(encoding="utf-8")

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
    assert 'candidate.read_text(encoding="utf-8", errors="replace")' in server
    assert "len(exact) != 1" in server
    assert '"candidate_count"' in server
    assert '"events": events' in server
    assert '"candidates"' in server
    assert '"match_basis"' in server
    assert "multiple exact-normalized script/entity names" in server
    assert "fuzzy/content Behavior Inspector matches only" in server
    assert "drill.candidates" in feature
    assert "match basis:" in feature

    for text in (
        "Lua → binding → engine handoff",
        "direct Lua API call",
        "Binding Reference",
        "C++ binding target",
        "Registration excerpt",
        "C++ implementation excerpt",
        "Shared helpers",
        "Callback ownership",
        "binding index could not be built",
        "match multiple registered names after case folding",
        "multiple binding locations/classes",
        "registered-name candidates",
        "source read:",
    ):
        assert text in feature,text

    bindings=(ROOT/"gui/templates/backport_bindings.html").read_text(encoding="utf-8")
    assert "trace_q" in bindings
    assert "Feature Trace entity {{ trace_q }}" in bindings
    assert "Binding Reference:" in behavior
    assert "feature_trace_binding_drilldown" in server
    assert "feature_trace_behavior_engine_drilldown(" in server
    assert "feature_trace_binding_lookup(" in server
    assert "workbench.devtools.features.trace_binding_drilldown" in binding_shim
    for text in (
        "def binding_index_for_server",
        "def binding_location",
        "def binding_lookup",
        "def behavior_engine_drilldown",
        "binding_index,index_error=_build_binding_index(server,source_root)",
        "index=binding_index",
        '"CASE_ONLY"',
        '"NOT_INDEXED"',
        "registration_excerpt",
        "implementation_excerpt",
        '"shared_helpers":helpers',
        '"callbacks":callbacks',
    ):
        assert text in binding_service,text

    print("Feature Trace cross-tool source drill-down regression: PASS")


if __name__=="__main__":
    main()
