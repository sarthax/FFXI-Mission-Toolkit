"""Offline negative-path HTTP contracts using *actual* named Toolkit handler ASTs.

Synthetic in-memory SQLite and stubbed job/receiver boundaries only. This tests HTTP
validation, status and empty-state behavior without loading a local DSP/client, running
Wiki imports, opening a receiver socket or writing Toolkit settings. It does NOT prove
the full monolithic host was booted or browser/gameplay acceptance.
"""
from __future__ import annotations

import ast
import json
import sqlite3
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
HOST = ROOT / "src/workbench/app/_host_impl.py"


def _isolated_host(handlers: tuple[str, ...], **dependencies):
    """Compile the unchanged, decorated production handlers into an in-memory test app.

    Handlers are read from HEAD at test time: don't copy their logic into test fixtures.
    Only data/service boundaries are supplied as stubs or in-memory SQLite.
    """
    tree = ast.parse(HOST.read_text(encoding="utf-8"), filename=str(HOST))
    selected = [node for node in tree.body
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                and node.name in handlers]
    assert len(selected) == len(handlers), (handlers, [node.name for node in selected])
    app = FastAPI()
    env = {
        "app": app, "Request": Request, "Query": Query, "HTMLResponse": HTMLResponse,
        "JSONResponse": JSONResponse, "FileResponse": FileResponse,
        "HTTPException": HTTPException, "Path": Path,
        "sqlite3": sqlite3, "tempfile": tempfile,
    }
    env.update(dependencies)
    module = ast.Module(body=[
        ast.ImportFrom(module="__future__",
                       names=[ast.alias(name="annotations")], level=0),
        *selected,
    ], type_ignores=[])
    exec(compile(ast.fix_missing_locations(module), str(HOST), "exec"), env)
    return TestClient(app)


def test_trace_runtime_graph_unavailable_returns_404():
    closed = []
    client = _isolated_host(
        ("feature_trace_runtime_detail",),
        _workbench_graph_connection=lambda: None,
        get_con=lambda: SimpleNamespace(close=lambda: closed.append(True)),
    )
    response = client.get("/features/trace/runtime.json", params={"root": "synthetic"})
    assert response.status_code == 404
    assert response.json() == {"error": "Canonical Workbench graph is not available."}
    assert closed == [True]
    assert client.get("/features/trace/runtime.json").status_code == 422


def test_wiki_scrape_rejection_and_receipt_without_running_job():
    calls = []
    def start_job(url, db):
        calls.append((url, db))
        if url == "rejected":
            raise ValueError("synthetic unsupported source URL")
        return {"id": "synthetic-queued", "status": "queued"}

    client = _isolated_host(
        ("wiki_scrape_url",),
        wiki_jobs=SimpleNamespace(start_job=start_job),
        DB_PATH=Path("/synthetic/no-real-cache.sqlite3"),
    )
    rejected = client.post("/wiki/scrape", data={"url": " rejected "})
    assert rejected.status_code == 400
    assert rejected.json() == {"error": "synthetic unsupported source URL"}
    accepted = client.post("/wiki/scrape", data={"url": "valid-fixture"})
    assert accepted.status_code == 200
    assert accepted.json() == {"job": {"id": "synthetic-queued", "status": "queued"}}
    assert [call[0] for call in calls] == ["rejected", "valid-fixture"]
    # 200 here means a synthetic receipt, NOT an imported or completed Wiki job.


def test_wiki_snapshot_invalid_source_and_failed_export(monkeypatch, tmp_path):
    from workbench.devtools.reference import wiki_snapshot
    calls = []
    def failed_export(_db, _destination, _source):
        calls.append(_source)
        raise OSError("synthetic permission failure")

    monkeypatch.setattr(wiki_snapshot, "export_snapshot", failed_export)
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
    client = _isolated_host(("wiki_snapshot_download",),
                            DB_PATH=tmp_path / "synthetic-not-opened.db",
                            shutil=__import__("shutil"))
    invalid = client.get("/wiki/snapshot/export", params={"source": "not-supported"})
    assert invalid.status_code == 400
    assert invalid.json() == {"error": "Invalid Wiki source"}
    assert calls == []
    failed = client.get("/wiki/snapshot/export", params={"source": "all"})
    assert failed.status_code == 400
    assert "synthetic permission failure" in failed.json()["error"]
    assert calls == ["all"]
    assert not list(tmp_path.glob("wiki_snapshot_*")), "failed exports must clean temp directories"


def _bridge_client(remote=False):
    from workbench.runtime.live_client.bridge_management_api import create_bridge_management_router
    manager = SimpleNamespace(
        status=lambda _cid: {"running": False, "connected": False},
        feeds=SimpleNamespace(feed=lambda _cid: None),
    )
    app = FastAPI()
    if remote:
        @app.middleware("http")
        async def _synthetic_remote(request: Request, call_next):
            request.scope["client"] = ("198.51.100.42", 32123)
            return await call_next(request)
    app.include_router(create_bridge_management_router(manager))
    return TestClient(app)


def test_bridge_remote_console_and_same_origin_rejection():
    assert _bridge_client(remote=True).get("/live-client/bridge/console").status_code == 403
    client = _bridge_client()
    path = "/live-client/bridge/headless"
    data = {"enabled": True, "character": "synthetic", "telemetry_dir": "/synthetic"}
    assert client.post(path, json=data).status_code == 403
    assert client.post(path, json=data, headers={"origin": "https://example.invalid"}).status_code == 403
    # Origin failures occur before settings, files or real receiver state are touched.


def test_bridge_headless_missing_fields_and_unwritable_feed(tmp_path):
    client = _bridge_client()
    route = "/live-client/bridge/headless"
    headers = {"origin": "http://testserver"}
    missing = client.post(route, json={"enabled": True}, headers=headers)
    assert missing.status_code == 400
    assert missing.json()["detail"] == "character and telemetry folder are required"
    blocked = tmp_path / "a-file-not-a-directory"
    blocked.write_text("synthetic", encoding="utf-8")
    failed = client.post(route, json={"enabled": True, "character": "synthetic",
                                      "telemetry_dir": str(blocked)}, headers=headers)
    assert failed.status_code == 400
    assert failed.json()["detail"].startswith("cannot create feed file:")
    assert blocked.read_text(encoding="utf-8") == "synthetic"


def test_bridge_status_invalid_client_and_null_snapshot():
    client = _bridge_client()
    invalid = client.get("/live-client/bridge/status/invalid%20client")
    assert invalid.status_code == 422
    assert invalid.json()["detail"] == "invalid client ID"
    missing = client.get("/live-client/bridge/status/synthetic")
    assert missing.status_code == 200
    assert missing.json()["snapshot"] is None
    assert missing.json()["connected"] is False


class _ContextAsJson:
    def TemplateResponse(self, request, _name, context):
        return JSONResponse({
            "module": context["module"],
            "events": context["events"],
            "packets": context["packets"],
            "total": context["total"],
            "page": context["page"],
        })


class _PacketDecode:
    @staticmethod
    def list_categories():
        return ["synthetic-classification"]

    @staticmethod
    def decode(*_args):
        return SimpleNamespace(description="synthetic packet", fields=[])

    @staticmethod
    def categorize_opcode(_desc):
        return "other"


def _capture_client():
    opened = []
    def get_con():
        con = sqlite3.connect(":memory:")
        con.row_factory = sqlite3.Row
        con.executescript("""
            CREATE TABLE capture_events (
                capture_id INTEGER, seq INTEGER, zone_db TEXT, entity_name TEXT,
                message_id INTEGER, opcode TEXT, opcode_name TEXT);
            CREATE TABLE captures (capture_id INTEGER, capture_label TEXT);
            CREATE TABLE capture_raw_packets (
                capture_id INTEGER, seq INTEGER, ts TEXT, direction TEXT,
                opcode TEXT, raw_hex TEXT);
            INSERT INTO capture_events
                (capture_id,seq,zone_db,entity_name,message_id,opcode,opcode_name)
                VALUES (1,1,NULL,'Synthetic NPC',123,'0x034','synthetic event');
            INSERT INTO captures VALUES (1,'synthetic capture');
            INSERT INTO capture_raw_packets VALUES (1,1,'','incoming','0x034','');
        """)
        opened.append(con)
        return con
    client = _isolated_host(
        ("captures_search",), get_con=get_con,
        templates=_ContextAsJson(), CAPTURE_SEARCH_PAGE_SIZE=20,
        CAPTURE_EVIDENCE_MODULES={
            "events": {"name": "Events"}, "packets": {"name": "Packets"},
        }, packet_decode=_PacketDecode(),
        capture_integrity=SimpleNamespace(canonical_row_key=lambda row: json.dumps(row)),
    )
    return client, opened


@pytest.mark.parametrize("invalid", ["text", "4.5", "0xZZ", " "])
def test_capture_bad_event_message_id_returns_422_before_database(invalid):
    client, opened = _capture_client()
    response = client.get("/captures/search",
                          params={"module": "events", "message_id": invalid})
    assert response.status_code == 422
    assert response.json()["detail"] == "message_id must be an integer"
    assert opened == [], "invalid filters must be rejected before DB acquisition"


def test_capture_unfiltered_modes_do_not_imply_missing_evidence():
    client, _opened = _capture_client()
    for module in ("events", "packets"):
        response = client.get("/captures/search", params={"module": module})
        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 0 and body["events"] == [] and body["packets"] == []


def test_capture_indexed_event_filter_empty_and_positive_synthetic_case():
    client, _opened = _capture_client()
    absent = client.get("/captures/search",
                        params={"module": "events", "message_id": "999"})
    assert absent.status_code == 200 and absent.json()["total"] == 0
    present = client.get("/captures/search",
                         params={"module": "events", "message_id": "123"})
    assert present.status_code == 200 and present.json()["total"] == 1
    assert present.json()["events"][0]["entity_name"] == "Synthetic NPC"


def test_capture_unknown_packet_category_returns_zero_not_all_rows():
    client, _opened = _capture_client()
    response = client.get("/captures/search",
                          params={"module": "packets", "pk_category": "unknown-category"})
    assert response.status_code == 200
    assert response.json()["total"] == 0 and response.json()["packets"] == []


# A second tranche covers the five recovery paths that previously had only
# handler-local source markers. No DSP, DAT, or local capture state is consumed.

class _RecoveryContextAsJson:
    def TemplateResponse(self, request, _name, context):
        keys = ("error", "matches", "result", "title", "page_view", "evidence",
                "report", "comparison", "rows", "counts", "kind_counts")
        return JSONResponse({k: context[k] for k in keys if k in context})


def _trace_page_client(*, graph_available, matches=()):
    closed = []
    graph = SimpleNamespace(close=lambda: closed.append("graph"))
    catalog = SimpleNamespace(close=lambda: closed.append("catalog"))

    def should_not_trace(*_args, **_kwargs):
        pytest.fail("An absent or ambiguous graph root must not execute a trace")

    trace = SimpleNamespace(
        clear_query_mode=lambda: None,
        split_mode_query=lambda q: (None, q),
        entity_query_diagnostics=lambda *_args: {"status": "synthetic-ambiguous"},
        entity_implementation_path=lambda *_args: None,
        node_info=lambda *_args: {"known": False},
        search_nodes=lambda *_args: list(matches),
        trace=should_not_trace,
    )
    client = _isolated_host(
        ("feature_trace_page",), templates=_RecoveryContextAsJson(),
        _workbench_graph_connection=lambda: graph if graph_available else None,
        get_con=lambda: catalog,
        feature_trace=trace,
        _feature_trace_branch_source_drilldown=lambda _path: None,
        present_relationships=lambda _edges: [],
        build_dossier=lambda _result: None,
    )
    return client, closed


def test_trace_page_missing_graph_exposes_error_without_searching():
    client, closed = _trace_page_client(graph_available=False)
    response = client.get("/features/trace", params={"q": "synthetic"})
    assert response.status_code == 200  # HTML page with an error, not an HTTP 404.
    assert "Canonical Workbench graph is not available" in response.json()["error"]
    assert response.json()["matches"] == []
    assert response.json()["result"] is None
    assert closed == ["catalog"]


def test_trace_page_ambiguous_nodes_avoids_arbitrary_root():
    matches = [{"node_id": "synthetic:A"}, {"node_id": "synthetic:B"}]
    client, closed = _trace_page_client(graph_available=True, matches=matches)
    response = client.get("/features/trace", params={"q": "synthetic"})
    assert response.status_code == 200
    assert response.json()["matches"] == matches
    assert response.json()["result"] is None
    assert response.json()["error"] is None
    assert closed == ["graph", "catalog"]


def _wiki_page_client(*, existing_page=False, mismatch=False):
    source = "synthetic-bg"
    linked_page_id = "synthetic-page"
    observed_calls = []

    def get_con():
        con = sqlite3.connect(":memory:")
        con.execute("CREATE TABLE reference_wiki_pages (source_id TEXT, page_id TEXT, title TEXT)")
        if existing_page:
            con.execute("INSERT INTO reference_wiki_pages VALUES (?, ?, ?)",
                        (source, linked_page_id, "Synthetic Wiki Entry"))
        return con

    wiki_evidence = SimpleNamespace(
        SOURCE_BG=source, SOURCE_FFXICLOPEDIA="synthetic-clopedia",
        SOURCE_WIKIWIKI_JP="synthetic-jp", init_db=lambda _con: None,
        page_evidence=lambda *_args: {"synthetic": "evidence"},
    )
    wiki_document = SimpleNamespace(init_db=lambda _con: None)
    wiki_claim_compare = SimpleNamespace(
        init_db=lambda _con: None,
        alignment_report=lambda *_args: {"synthetic": "comparison"},
    )
    wiki_compile = SimpleNamespace(compile_report=lambda *_args: {"synthetic": "report"})

    def page_view(*_args):
        observed_calls.append("opened")
        return {"page_id": "wrong-page-id" if mismatch else linked_page_id,
                "title": "Synthetic Wiki Entry"}

    client = _isolated_host(
        ("wiki_browse",), templates=_RecoveryContextAsJson(),
        get_con=get_con, wiki_evidence=wiki_evidence,
        wiki_document=wiki_document, wiki_claim_compare=wiki_claim_compare,
        wiki_compile=wiki_compile, _wiki_page_view=page_view,
        wiki_jobs=SimpleNamespace(SITES={}, recent_jobs=lambda: []),
    )
    return client, observed_calls, source, linked_page_id


def test_wiki_source_qualified_page_not_found_never_falls_back_by_title():
    client, observed, source, page_id = _wiki_page_client()
    response = client.get("/wiki", params={
        "source": source, "page_id": page_id, "title": "Someone Else's Title",
    })
    assert response.status_code == 200  # Error rendered on Wiki page.
    data = response.json()
    assert data["error"] == "The source-qualified Wiki page was not found."
    assert data["title"] == ""
    assert data["page_view"] is None
    assert data["evidence"] is None
    assert observed == [], "missing page IDs may not fall back to a title lookup"


def test_wiki_same_title_wrong_page_id_is_rejected():
    client, observed, source, page_id = _wiki_page_client(existing_page=True, mismatch=True)
    response = client.get("/wiki", params={"source": source, "page_id": page_id})
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Synthetic Wiki Entry"
    assert data["error"] == "The exact Wiki source page could not be opened."
    assert data["page_view"] is None
    assert data["report"] is None and data["evidence"] is None
    assert data["comparison"] is None
    assert observed == ["opened"], "the mismatched result must not be displayed"


def test_capture_review_filters_empty_without_resolving_findings(monkeypatch):
    from workbench.captures import review_queue as rq
    raw_records = [
        {"status": "pending", "kind": "metadata", "capture_id": 1,
         "detail": {"candidates": ["synthetic candidate"]}},
        {"status": "resolved", "kind": "metadata", "capture_id": 1,
         "detail": {"candidates": []}},
    ]
    calls = []
    def items(_con, status):
        calls.append(status)
        return [
            {**row, "detail": dict(row["detail"])}
            for row in raw_records
        ]
    monkeypatch.setattr(rq, "items", items)
    monkeypatch.setattr(rq, "KINDS", ("metadata",), raising=False)

    def get_con():
        con = sqlite3.connect(":memory:")
        con.execute("CREATE TABLE zones (name TEXT)")
        con.execute("CREATE TABLE captures (capture_id INTEGER, capture_label TEXT)")
        con.execute("INSERT INTO captures VALUES (1, 'Synthetic capture')")
        return con

    client = _isolated_host(
        ("capture_review_queue",), get_con=get_con,
        templates=_RecoveryContextAsJson(),
    )
    empty = client.get("/captures/review", params={"status": "pending", "kind": "other"})
    assert empty.status_code == 200 and empty.json()["rows"] == []
    assert empty.json()["counts"] == {
        "pending": 1, "resolved": 1, "dismissed": 0, "auto_resolved": 0,
    }
    all_rows = client.get("/captures/review", params={"status": "all"})
    assert all_rows.status_code == 200
    assert len(all_rows.json()["rows"]) == 2
    assert all_rows.json()["rows"][0]["detail"]["candidates"] == [
        {"title": "synthetic candidate"}
    ]
    assert calls == ["all", "all"]


def test_wiki_correct_source_and_page_id_retains_matching_evidence():
    client, observed, source, page_id = _wiki_page_client(existing_page=True, mismatch=False)
    response = client.get("/wiki", params={"source": source, "page_id": page_id})
    assert response.status_code == 200
    data = response.json()
    assert data["error"] == ""
    assert data["page_view"]["page_id"] == page_id
    assert data["evidence"] == {"synthetic": "evidence"}
    assert data["comparison"] == {"synthetic": "comparison"}
    assert observed == ["opened"]
