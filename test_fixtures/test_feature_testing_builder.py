from pathlib import Path

import pytest
from fastapi import HTTPException

from workbench.server_admin.feature_testing.router import dashboard_view, test_builder_plan as builder_plan_route


def test_builder_tab_is_available():
    assert dashboard_view(tab="builder")["tab"] == "builder"
    html = (Path(__file__).resolve().parents[1] / "gui/templates/feature_testing.html").read_text(encoding="utf-8")
    assert 'tab=builder' in html
    assert 'name="charid"' in html
    assert "Review test plan (JSON)" in html


def test_builder_plan_is_read_only_and_allowlisted(monkeypatch):
    monkeypatch.setenv("MISSION_TOOLKIT_SUPERVISOR_TEST_CHARIDS", "21836")
    plan = builder_plan_route(account="xitest07", charid=21836, supervisor_port=8420)
    assert plan["character_approved"] is True
    assert plan["browser_execution_enabled"] is False
    assert plan["model_execution_enabled"] is False
    assert plan["launch_mode"] == "local_cli_only"
    assert plan["required_operator_confirmation"] == "--approve-mog09"
    assert builder_plan_route(account="xitest07", charid=1)["character_approved"] is False


@pytest.mark.parametrize("account,charid,port", [("invalid name", 21836, 8420), ("ok", -1, 8420), ("ok", 21836, 0)])
def test_builder_rejects_invalid_inputs(account, charid, port):
    with pytest.raises(HTTPException) as exc:
        builder_plan_route(account=account, charid=charid, supervisor_port=port)
    assert exc.value.status_code == 400


@pytest.mark.parametrize("query", ["", "account=a%20b&charid=1", "account=ok&charid=-5",
                                   "account=ok&charid=1&supervisor_port=99999"])
def test_builder_plan_http_rejects_invalid_inputs_without_500(query):
    host = pytest.importorskip("workbench.app.host", exc_type=Exception)
    from fastapi.testclient import TestClient
    response = TestClient(host.app, raise_server_exceptions=False).get("/feature-testing/builder/plan?" + query)
    assert response.status_code == 400


def test_builder_host_route_renders_when_available(monkeypatch, tmp_path):
    host = pytest.importorskip("workbench.app.host", exc_type=Exception)
    from fastapi.testclient import TestClient
    monkeypatch.setenv("MISSION_TOOLKIT_TEST_RESULTS_DB", str(tmp_path / "missing.sqlite"))
    response = TestClient(host.app).get("/feature-testing?tab=builder")
    assert response.status_code == 200
    assert "Run a test" in response.text
