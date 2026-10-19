import pytest
from fastapi import HTTPException

from workbench.server_admin.feature_testing import supervisor


def test_supervisor_off_by_default(monkeypatch):
    monkeypatch.delenv("MISSION_TOOLKIT_SUPERVISOR_TOKEN", raising=False)
    with pytest.raises(HTTPException) as exc:
        supervisor.health(authorization=None)
    assert exc.value.status_code == 403


def test_supervisor_denies_wrong_token(monkeypatch):
    monkeypatch.setenv("MISSION_TOOLKIT_SUPERVISOR_TOKEN", "a" * 64)
    with pytest.raises(HTTPException) as exc:
        supervisor.test_runs(authorization="Bearer " + "b" * 64)
    assert exc.value.status_code == 403


def test_supervisor_read_only_empty_state(monkeypatch):
    monkeypatch.setenv("MISSION_TOOLKIT_SUPERVISOR_TOKEN", "a" * 64)
    monkeypatch.delenv("MISSION_TOOLKIT_TEST_RESULTS_DB", raising=False)
    token = "Bearer " + "a" * 64
    assert supervisor.health(authorization=token)["execution_enabled"] is False
    assert supervisor.test_runs(authorization=token)["runs"] == []
    assert supervisor.failed_assertions(authorization=token)["results"] == []


def test_supervisor_routes_are_get_only():
    assert {method for route in supervisor.router.routes for method in route.methods} == {"GET"}
