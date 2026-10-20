"""Native-free route and rendered-Jinja contracts for explicit Feature Trace modes.

Synthetic graph and service stubs only. The production handler is AST-extracted
unchanged. No local indexed DSP data, browser automation, or client is used.
"""
from __future__ import annotations

import html
import re
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from workbench.devtools.features import trace as live_facade
from workbench.devtools.features.trace_catalog import present_relationships
from test_feature_catalog_http_contract import _isolated_host
from test_feature_catalog_render_asgi import _production_jinja


def _client():
    traced = []
    searched = []
    cleared = []
    closed = []
    edges = [{
        "relationship_id": "synthetic-link", "source_node": "synthetic-root",
        "target_node": "synthetic-target", "from_node": "synthetic-root",
        "to_node": "synthetic-target", "relationship": "HAS_SOURCE",
        "status": "DISCOVERED", "confidence": "UNKNOWN",
        "depth": 1, "evidence_id": "synthetic-proof", "metadata": {},
    }]
    def _trace(_graph, root, depth, direction, _catalog, **kwargs):
        traced.append({"root": root, "depth": depth, "direction": direction, "kwargs": kwargs})
        m = kwargs.get("mode")
        return {
            "root": root, "max_depth": depth, "direction": direction,
            "trace_mode": {"id": m, "label": "Focused synthetic"} if m else None,
            "edges": edges, "nodes": [], "paths": [], "notes": [],
            "truncated": False,
            "runtime_hierarchy": {"observation_count": 0, "capture_count": 0, "groups": []},
        }
    def _query(_graph, _catalog, q):
        searched.append(q)
        return None
    service = SimpleNamespace(
        clear_query_mode=lambda: cleared.append(True),
        split_mode_query=live_facade.split_mode_query,
        entity_query_diagnostics=_query,
        entity_implementation_path=_query,
        node_info=lambda _graph, root, _catalog: {"known": root == "synthetic-root"},
        search_nodes=lambda *_args: [],
        trace=_trace,
    )
    dossier = {
        "identity": {"node_id": "synthetic-root", "display_name": "Synthetic Root",
                     "node_type": "MOB", "source_count": 1},
        "facets": [], "semantic_node_count": 2, "semantic_relationship_count": 1,
    }
    client = _isolated_host(
        ("feature_trace_page",),
        feature_trace=service, templates=_production_jinja(),
        _workbench_graph_connection=lambda: SimpleNamespace(close=lambda: closed.append("graph")),
        get_con=lambda: SimpleNamespace(close=lambda: closed.append("catalog")),
        _feature_trace_branch_source_drilldown=lambda _path: None,
        present_relationships=present_relationships,
        build_dossier=lambda _result: dossier,
    )
    return client, traced, searched, cleared, closed


def test_mode_selector_matches_real_facade_modes():
    template = (ROOT / "gui/templates/feature_trace.html").read_text(encoding="utf-8")
    form = template.split('id="featureTraceTop"', 1)[1].split("</form>", 1)[0]
    choices = set(re.findall(r'<option value="([a-z]+)"', form))
    assert choices == {row["id"] for row in live_facade.mode_options()}
    assert "All recorded (legacy)" in form
    assert 'name="mode"' in form
    assert 'id="trace-question-mode"' in form


def test_legacy_unfiltered_default_is_unchanged_and_returns_full_result():
    client, traced, searched, cleared, closed = _client()
    response = client.get("/features/trace", params={"q": "synthetic-root"})
    assert response.status_code == 200
    assert traced == [{"root": "synthetic-root", "depth": 3,
                       "direction": "both", "kwargs": {}}]
    assert searched == ["synthetic-root", "synthetic-root"]
    assert cleared == [True]
    assert closed == ["graph", "catalog"]
    assert "HAS_SOURCE" in response.text
    assert 'id="trace-mode-help"' in response.text
    assert 'id="trace-focused-mode"' not in response.text


@pytest.mark.parametrize("mode", [
    "implementation", "mission", "triggers", "effects", "dependencies",
    "runtime", "identity", "diagnose", "all",
])
def test_explicit_question_is_forwarded_to_production_traversal(mode):
    client, traced, _searched, _cleared, closed = _client()
    response = client.get("/features/trace",
                          params={"q": "synthetic-root", "mode": mode,
                                  "depth": 2, "direction": "in"})
    assert response.status_code == 200
    assert traced[0]["kwargs"] == {"mode": mode}
    assert traced[0]["depth"] == 2 and traced[0]["direction"] == "in"
    assert 'id="trace-focused-mode"' in response.text
    assert f'<option value="{mode}" selected' in response.text
    # Navigation into either endpoint keeps the question and existing depth.
    assert f"mode={mode}&amp;depth=2&amp;direction=in" in response.text
    assert 'href="/features/trace?q=synthetic-root&amp;depth=2&amp;direction=in"' in response.text
    assert closed == ["graph", "catalog"]


def test_existing_at_mode_query_prefix_populates_selector_and_strips_search():
    client, traced, searched, cleared, _closed = _client()
    response = client.get("/features/trace", params={"q": "@mission synthetic-root"})
    assert response.status_code == 200
    assert traced[0]["kwargs"] == {"mode": "mission"}
    assert searched == ["synthetic-root", "synthetic-root"]
    assert '<option value="mission" selected' in response.text
    assert 'name="q" value="synthetic-root"' in response.text
    assert cleared == [True]


def test_explicit_selection_wins_over_legacy_mode_prefix():
    client, traced, searched, _cleared, _closed = _client()
    response = client.get("/features/trace",
                          params={"q": "@mission synthetic-root", "mode": "effects"})
    assert response.status_code == 200
    assert traced[0]["kwargs"] == {"mode": "effects"}
    assert searched == ["synthetic-root", "synthetic-root"]
    assert '<option value="effects" selected' in response.text


def test_invalid_selection_never_silently_becomes_valid_or_leaks_into_followup():
    client, traced, _searched, cleared, _closed = _client()
    response = client.get("/features/trace",
                          params={"q": "synthetic-root", "mode": "invented-mode"})
    assert response.status_code == 200
    assert traced[0]["kwargs"] == {}
    followup = client.get("/features/trace", params={"q": "synthetic-root"})
    assert followup.status_code == 200
    assert traced[1]["kwargs"] == {}
    assert cleared == [True, True]


def test_hidden_legacy_mode_context_can_be_reset_without_mutating_graph():
    token = live_facade._QUERY_MODE.set("mission")
    try:
        live_facade.clear_query_mode()
        assert live_facade._QUERY_MODE.get() is None
    finally:
        live_facade._QUERY_MODE.reset(token)


def test_untrusted_query_does_not_render_unescaped_html_in_question_selector():
    client, _traced, _searched, _cleared, _closed = _client()
    payload = '<script>alert("synthetic")</script>'
    response = client.get("/features/trace", params={"q": payload, "mode": "mission"})
    assert response.status_code == 200
    assert payload not in response.text
    assert "&lt;script&gt;" in response.text
