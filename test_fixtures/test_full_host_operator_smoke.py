"""Fail-closed tests for the local, *real-host* opt-in acceptance runner.

All test apps here are synthetic and never import workbench.app.host.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import PlainTextResponse

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import full_host_operator_smoke as smoke


def _checkout(tmp_path):
    root = tmp_path / "disposable-fixture"
    root.mkdir()
    (root / ".git").mkdir()
    return root


def test_no_implicit_full_host_execution(tmp_path, capsys, monkeypatch):
    root = _checkout(tmp_path)
    monkeypatch.setattr(smoke, "sandbox_preflight", lambda _root: {
        "checkout_marker_present": True,
        "native_wheel_available": True,
        "state_blockers": [], "disposable_candidate": True,
    })
    assert smoke.main([], root=root) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["result"] == "NOT_RUN"
    assert output["execution_scope"] == "preflight_only"
    assert output["reason"].startswith("Preflight only")


def test_state_guard_refuses_existing_databases_or_private_state(tmp_path):
    root = _checkout(tmp_path)
    clean = smoke.sandbox_preflight(root, native_present=True)
    assert clean["disposable_candidate"]
    for name in smoke.UNSAFE_STATE:
        file = root / name
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text("synthetic do-not-open", encoding="utf-8")
        guarded = smoke.sandbox_preflight(root, native_present=True)
        assert name in guarded["state_blockers"]
        assert not guarded["disposable_candidate"]
        file.unlink()
    (root / ".git").rmdir()
    assert not smoke.sandbox_preflight(root, native_present=True)["disposable_candidate"]


def test_execute_refused_without_ack_and_without_native(tmp_path, monkeypatch, capsys):
    root = _checkout(tmp_path)
    safe = smoke.sandbox_preflight(root, native_present=True)
    monkeypatch.setattr(smoke, "sandbox_preflight", lambda _root: safe)
    assert smoke.main(["--execute"], root=root) == 2
    refused = json.loads(capsys.readouterr().out)
    assert refused["result"] == "NOT_RUN" and "Refused" in refused["reason"]
    missing_native = {**safe, "native_wheel_available": False}
    monkeypatch.setattr(smoke, "sandbox_preflight", lambda _root: missing_native)
    assert smoke.main(["--execute", "--ack-disposable-checkout"], root=root) == 2
    missing = json.loads(capsys.readouterr().out)
    assert missing["result"] == "NOT_RUN"
    assert "xi_tinkerer" in missing["reason"]


def test_route_registration_uses_method_not_only_path():
    app = FastAPI()
    app.add_api_route("/features/trace", lambda: {}, methods=["GET"])
    app.add_api_route("/live-client/bridge/headless", lambda: {}, methods=["POST"])
    cases = [
        {"id": "trace", "route": "/features/trace", "method": "GET"},
        {"id": "save", "route": "/live-client/bridge/headless", "method": "POST"},
        {"id": "unsupported", "route": "/live-client/bridge/headless", "method": "GET"},
        {"id": "missing", "route": "/absent", "method": "GET"},
    ]
    rows = smoke.route_registration(app, cases)
    assert [row["mounted"] for row in rows] == [True, True, False, False]


def test_only_get_probes_are_dispatched_and_mismatches_fail():
    app = FastAPI()
    mutations = []
    @app.get("/safe")
    def safe():
        return PlainTextResponse("safe marker")
    @app.post("/danger")
    def danger():
        mutations.append("called")
        return {"success": True}
    results = smoke.read_only_http(
        app, probes=(("/safe", 200, "safe marker"),
                     ("/safe", 404, "safe marker"),
                     ("/danger", 200, "success"))
    )
    assert results[0]["passed"]
    assert not results[1]["passed"]
    assert not results[2]["passed"]
    assert mutations == [], "No POST route may be called by a read-only smoke"


def test_manifest_contract_only_has_bounded_get_post_workflows():
    cases = smoke._manifest(smoke.ROOT)
    assert len(cases) == 11
    assert {row["id"] for row in cases} >= {
        "trace-query", "wiki-scrape-job", "capture-review-navigation"
    }
    assert all(row["method"] in {"GET", "POST"} for row in cases)
    assert all(row["route"].startswith("/") for row in cases)
