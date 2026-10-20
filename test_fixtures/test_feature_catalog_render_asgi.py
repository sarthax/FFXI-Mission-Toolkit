"""Native-free *rendered ASGI* regression for core operator pages.

Production route functions (read verbatim from the host module), actual Jinja
templates and FastAPI TestClient are used. Synthetic DB/graph/capture boundaries
are injected. This is stronger than the JSON-context unit contracts, but NOT
a full host import, browser session, installed xi_tinkerer, or DSP/Ashita test.
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.templating import Jinja2Templates

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from workbench.gui_shell import build_shell_context

from test_feature_catalog_http_contract import _isolated_host


def _production_jinja():
    """Use the real, unchanged repository templates and actual shell context."""
    templates = Jinja2Templates(directory=str(ROOT / "gui" / "templates"))
    templates.env.globals.update(
        current_theme=lambda: "light",
        backport_enabled=lambda: False,
        capture_review_items=lambda _capture_id: [],
        shell_context=lambda request: build_shell_context(
            path=request.url.path, method=request.method, settings={},
            default_topaz_root="C:/synthetic-missing-topaz",
            default_backport_root="C:/synthetic-missing-workspace",
            path_exists=lambda _path: False,
        ),
    )
    return templates


def test_help_and_roadmap_routes_render_actual_shell():
    client = _isolated_host(
        ("help_page", "roadmap_page"), templates=_production_jinja(),
    )
    help_response = client.get("/help")
    assert help_response.status_code == 200
    assert "text/html" in help_response.headers["content-type"]
    assert "wb-page-frame" in help_response.text or "Workbench" in help_response.text
    assert "When a workflow does not produce the expected result" in help_response.text
    assert "/feature-catalog" in help_response.text

    roadmap = client.get("/roadmap")
    assert roadmap.status_code == 200
    assert "text/html" in roadmap.headers["content-type"]
    assert "/feature-catalog" in roadmap.text


def test_catalog_route_renders_curated_recovery_table_through_jinja():
    # Real source-backed catalog/audit functions, real Jinja, no local DB or native wheel.
    client = _isolated_host(
        ("feature_catalog_page",), templates=_production_jinja(),
    )
    response = client.get("/feature-catalog")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert 'id="operator-workflow-bindings"' in response.text
    assert "21 failure/degraded-state checks" in response.text
    assert "21 with isolated HTTP tests" in response.text
    assert 'id="catalog-verification-ladder"' in response.text
    assert "local acceptance required" in response.text
    assert "Feature Catalog" in response.text
    assert 'href="/help"' in response.text

    detail = client.get("/feature-catalog", params={"feature": "feature-trace"})
    assert detail.status_code == 200
    assert "Documented subfunctions" in detail.text
    assert "Feature Trace" in detail.text


def test_catalog_reflected_filter_escapes_untrusted_text():
    client = _isolated_host(
        ("feature_catalog_page",), templates=_production_jinja(),
    )
    dangerous = '<script>alert("synthetic")</script>'
    response = client.get("/feature-catalog", params={"q": dangerous})
    assert response.status_code == 200
    assert dangerous not in response.text
    assert "&lt;script&gt;" in response.text
    assert "No matching capabilities." in response.text


def test_trace_graph_missing_renders_helpful_error_not_http_500():
    closed = []
    client = _isolated_host(
        ("feature_trace_page",), templates=_production_jinja(),
        _workbench_graph_connection=lambda: None,
        get_con=lambda: SimpleNamespace(close=lambda: closed.append(True)),
    )
    response = client.get("/features/trace", params={"q": '<img src=x onerror=alert("synthetic")>'})
    assert response.status_code == 200  # Rendered degraded page, not API 404.
    assert "Canonical Workbench graph is not available" in response.text
    assert "Build/import workbench.db" in response.text
    assert '<img src=x onerror=alert("synthetic")>' not in response.text
    assert "&lt;img" in response.text
    assert closed == [True]


def test_capture_review_filters_render_and_escape_evidence(monkeypatch):
    from workbench.captures import review_queue as rq

    kind = next(iter(rq.KINDS))
    injected = '<script>alert("synthetic")</script>'
    rows = [
        {"review_id": 11, "kind": kind, "capture_id": 1, "source_path": None,
         "key": "", "status": "pending", "blocking": 0, "resolution": None, "note": "",
         "detail": {"summary": injected, "candidates": []}},
        {"review_id": 12, "kind": kind, "capture_id": 1, "source_path": None,
         "key": "", "status": "resolved", "blocking": 0, "resolution": None, "note": "",
         "detail": {"summary": "Synthetic resolved", "candidates": []}},
    ]
    def inert_items(_con, status):
        assert status == "all"
        return [dict(row, detail=dict(row["detail"])) for row in rows]

    monkeypatch.setattr(rq, "items", inert_items)
    connections = []
    def synthetic_db():
        connection = sqlite3.connect(":memory:")
        connection.execute("CREATE TABLE zones (name TEXT)")
        connection.execute("CREATE TABLE captures (capture_id INTEGER, capture_label TEXT)")
        connection.execute("INSERT INTO captures VALUES (1, 'Synthetic capture')")
        connections.append(connection)
        return connection

    client = _isolated_host(
        ("capture_review_queue",), templates=_production_jinja(), get_con=synthetic_db,
    )
    empty = client.get("/captures/review", params={"status": "pending", "kind": "not-this-kind"})
    assert empty.status_code == 200
    assert "Nothing here for this filter." in empty.text
    assert "Pending (1)" in empty.text
    assert injected not in empty.text

    unfiltered = client.get("/captures/review", params={"status": "all"})
    assert unfiltered.status_code == 200
    assert "Synthetic resolved" in unfiltered.text
    assert injected not in unfiltered.text
    assert "&lt;script&gt;" in unfiltered.text
    assert "Synthetic capture" in unfiltered.text
    assert len(connections) == 2
    assert all(_closed(con) for con in connections)


def _closed(con):
    try:
        con.execute("SELECT 1")
    except sqlite3.ProgrammingError:
        return True
    return False
