"""Synthetic regression for readable, provenance-safe Feature Trace provider edges.

Compiles the actual production handler into an isolated FastAPI app, renders the
unchanged real templates and exercises the Feature Trace presentation adapter.
No Workbench host, local DSP index or native wheel is started.
"""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

from test_feature_catalog_http_contract import _isolated_host
from test_feature_catalog_render_asgi import _production_jinja

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from workbench.devtools.features import trace as feature_trace
from workbench.devtools.features.trace_catalog import present_relationships


def _generated(*, depth=2, basis="synthetic provider record"):
    return feature_trace._generated_display_edge({
        "source_node": "synthetic-source",
        "target_node": "synthetic-target",
        "relationship": "SPAWN_USES_GROUP",
        "generator": "lua-sql",
        "confidence": "VERIFIED",
        "metadata": {"depth": depth},
        "evidence": [{
            "kind": "PROVIDER_NATIVE", "basis": basis,
        }],
    })


def test_generated_edges_have_real_display_endpoints_and_source_depth():
    edge = _generated()
    assert edge["source_node"] == edge["from_node"] == "synthetic-source"
    assert edge["target_node"] == edge["to_node"] == "synthetic-target"
    assert edge["traversed_direction"] == "out"
    assert edge["depth"] == 2
    assert edge["status"] == "GENERATED_EVIDENCE"
    assert edge["generated"] is True
    assert edge["evidence_id"] is None
    assert edge["relationship_id"] is None
    assert edge["metadata"]["provider_evidence"] is True


def test_generated_edge_depth_not_invented_when_provider_does_not_record_one():
    edge = _generated(depth="2")
    assert edge["depth"] is None
    edge_without_depth = feature_trace._generated_display_edge({
        "source_node": "synthetic-source",
        "target_node": "synthetic-target",
        "relationship": "SPAWN_USES_GROUP",
        "generator": "lua-sql",
    })
    assert edge_without_depth["depth"] is None
    assert edge_without_depth["from_node"] == "synthetic-source"


def test_rendered_trace_shows_actual_edges_and_read_only_provenance():
    unsafe = '<img src=x onerror=alert("synthetic")>'
    provider = _generated(basis=unsafe)
    canonical = {
        "relationship_id": "synthetic:canonical-edge",
        "source_node": "synthetic-root",
        "target_node": "synthetic-canonical-target",
        "from_node": "synthetic-root",
        "to_node": "synthetic-canonical-target",
        "relationship": "REFERENCES_SOURCE",
        "status": "DISCOVERED",
        "confidence": "UNKNOWN",
        "evidence_id": "synthetic:evidence",
        "depth": 1,
        "metadata": {},
    }
    runtime = {
        "relationship_id": "synthetic:runtime-edge",
        "source_node": "capture:synthetic",
        "target_node": "synthetic-root",
        "from_node": "capture:synthetic",
        "to_node": "synthetic-root",
        "relationship": "RUNTIME_PACKET",
        "depth": 1,
        "evidence_id": "synthetic:packet",
        "status": "DISCOVERED",
        "metadata": {"opcode": "synthetic-packet"},
    }
    result = {
        "root": "synthetic-root",
        "max_depth": 1,
        "direction": "both",
        "truncated": False,
        "edges": [provider, canonical, runtime],
        "nodes": [],
        "paths": [],
        "notes": [],
        "runtime_hierarchy": {"observation_count": 1, "capture_count": 1, "groups": [
            {"opcode": "synthetic-packet", "direction": "incoming", "observation_count": 1,
             "capture_count": 1, "capture_groups": []},
        ]},
    }
    dossier = {
        "identity": {"node_id": "synthetic-root", "display_name": "Synthetic Root",
                     "node_type": "MOB", "source_count": 1},
        "facets": [],
        "semantic_node_count": 3,
        "semantic_relationship_count": 3,
    }
    closed = []
    service = SimpleNamespace(
        clear_query_mode=lambda: None,
        split_mode_query=feature_trace.split_mode_query,
        entity_query_diagnostics=lambda *_args: None,
        entity_implementation_path=lambda *_args: None,
        node_info=lambda *_args: {"known": True},
        trace=lambda *_args, **_kwargs: result,
    )
    app = _isolated_host(
        ("feature_trace_page",),
        templates=_production_jinja(),
        feature_trace=service,
        _feature_trace_branch_source_drilldown=lambda _path: None,
        _workbench_graph_connection=lambda: SimpleNamespace(close=lambda: closed.append("graph")),
        get_con=lambda: SimpleNamespace(close=lambda: closed.append("catalog")),
        present_relationships=present_relationships,
        build_dossier=lambda _result: dossier,
    )
    response = app.get("/features/trace", params={"q": "synthetic-root", "depth": 1})
    assert response.status_code == 200
    html = response.text
    assert 'href="/features/trace?q=synthetic-source"' in html
    assert 'href="/features/trace?q=synthetic-target"' in html
    assert "Provider-generated · read-only" in html
    assert "PROVIDER_NATIVE" in html
    assert unsafe not in html
    assert "&lt;img src=x" in html
    assert "synthetic:evidence" in html
    assert "These are bounded observation counts, not expanded semantic edges" in html
    assert 'href="#trace-runtime-observations"' in html
    assert 'id="trace-runtime-observations"' in html
    assert closed == ["graph", "catalog"]
