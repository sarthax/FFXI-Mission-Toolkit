"""Regression for #1302: /scenario-developer must render through the real host app."""
from fastapi.testclient import TestClient


def test_scenario_developer_renders_through_real_host(tmp_path, monkeypatch):
    monkeypatch.setenv("MISSION_TOOLKIT_TEST_DRAFTS_DB", str(tmp_path / "drafts.sqlite"))
    from workbench.app.host import app

    client = TestClient(app, raise_server_exceptions=True)
    response = client.get("/scenario-developer")
    assert response.status_code == 200
    assert 'id="sd-handoff"' in response.text
