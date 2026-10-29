"""Operator launch controls never appear in model tools and fail closed."""
import pytest
from fastapi.testclient import TestClient


def test_operator_token_required(monkeypatch):
    from workbench.server_admin.feature_testing.execution_jobs import authorize_operator
    monkeypatch.delenv("MISSION_TOOLKIT_TEST_OPERATOR_TOKEN", raising=False)
    with pytest.raises(PermissionError):
        authorize_operator("a" * 64)
    monkeypatch.setenv("MISSION_TOOLKIT_TEST_OPERATOR_TOKEN", "a" * 64)
    with pytest.raises(PermissionError):
        authorize_operator("b" * 64)
    authorize_operator("a" * 64)


def test_operator_routes_require_auth_and_approval(monkeypatch):
    host = pytest.importorskip("workbench.app.host", exc_type=Exception)
    monkeypatch.setenv("MISSION_TOOLKIT_TEST_OPERATOR_TOKEN", "a" * 64)
    client = TestClient(host.app, client=("127.0.0.1", 50000))
    body = {"account": "xitest07", "charid": 21836, "supervisor_port": 8420, "approval": True}
    assert client.post("/feature-testing/builder/launch", json=body).status_code == 403
    headers = {"X-Test-Operator-Token": "a" * 64}
    assert client.post("/feature-testing/builder/launch", json={**body, "approval": False}, headers=headers).status_code == 400
    assert client.get("/feature-testing/builder/jobs").status_code == 403


def test_supervisor_contract_does_not_expose_execution():
    from workbench.server_admin.feature_testing.supervisor import supervisor_openapi
    from workbench.server_admin.feature_testing import router
    spec = supervisor_openapi()
    assert all("launch" not in route for route in spec["paths"])
    assert all("builder/jobs" not in route for route in spec["paths"])


def test_gui_has_explicit_approval():
    from pathlib import Path
    html = (Path(__file__).resolve().parents[1] / "gui/templates/feature_testing.html").read_text(encoding="utf-8")
    assert 'id="ft-run-approval"' in html
    assert 'id="ft-operator-token"' in html
    assert 'builder/launch' in html
