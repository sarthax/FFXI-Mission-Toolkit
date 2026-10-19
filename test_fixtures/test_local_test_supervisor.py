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


def test_isolated_openapi_contains_only_read_only_supervisor_tools():
    spec = supervisor.supervisor_openapi()
    assert spec["servers"] == [{"url": "http://127.0.0.1:8420"}]
    assert set(spec["paths"]) == {
        "/api/supervisor/health",
        "/api/supervisor/test-runs",
        "/api/supervisor/failed-assertions",
        "/api/supervisor/log-errors",
    }
    assert all(set(methods) == {"get"} for methods in spec["paths"].values())
    assert "/wiki" not in str(spec["paths"])


def test_supervisor_log_errors_redacts_credentials(tmp_path, monkeypatch):
    file = tmp_path / "dsp.log"
    file.write_text("INFO start\\nERROR authorization: BearerTokenExample\\nException password=letmein\\n")
    monkeypatch.setenv("MISSION_TOOLKIT_SUPERVISOR_DSP_LOG", str(file))
    monkeypatch.setenv("MISSION_TOOLKIT_SUPERVISOR_TOKEN", "a" * 64)
    result = supervisor.log_errors(source="dsp", authorization="Bearer " + "a" * 64)
    assert result["configured"]
    assert len(result["lines"]) == 2
    assert all("[REDACTED]" in line for line in result["lines"])
    assert "letmein" not in repr(result)


def test_supervisor_log_errors_requires_authentication(tmp_path, monkeypatch):
    monkeypatch.setenv("MISSION_TOOLKIT_SUPERVISOR_DSP_LOG", str(tmp_path / "secret.log"))
    monkeypatch.delenv("MISSION_TOOLKIT_SUPERVISOR_TOKEN", raising=False)
    with pytest.raises(HTTPException) as exc:
        supervisor.log_errors(source="dsp", authorization=None)
    assert exc.value.status_code == 403
