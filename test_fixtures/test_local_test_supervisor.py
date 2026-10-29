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
        "/api/supervisor/run-evidence/{run_id}",
        "/api/supervisor/search-source",
        "/api/supervisor/investigation/{run_id}",
        "/api/supervisor/failed-assertions",
        "/api/supervisor/log-errors",
        "/api/supervisor/service-health",
        "/api/supervisor/test-character-inventory",
        "/api/supervisor/test-character-inventory-v2",
        "/api/supervisor/test-character-progression",
        "/api/supervisor/test-character-keyitems",
        "/api/supervisor/test-character-vars",
        "/api/supervisor/test-character-selected-jobs",
    }
    assert all(set(methods) == {"get"} for methods in spec["paths"].values())
    assert all(operation["operationId"].startswith("supervisor_")
               for methods in spec["paths"].values()
               for operation in methods.values())
    assert spec["paths"]["/api/supervisor/test-character-inventory-v2"]["get"]["operationId"] == (
        "supervisor_test_character_inventory_v2")
    assert spec["paths"]["/api/supervisor/test-character-progression"]["get"]["operationId"] == (
        "supervisor_test_character_progression")
    assert spec["components"]["securitySchemes"]["bearerAuth"] == {"type": "http", "scheme": "bearer"}
    assert all(operation["security"] == [{"bearerAuth": []}]
               and all(param.get("name", "").lower() != "authorization"
                       for param in operation.get("parameters", []))
               for methods in spec["paths"].values()
               for operation in methods.values())
    assert "/wiki" not in str(spec["paths"])


def test_supervisor_log_errors_redacts_credentials(tmp_path, monkeypatch):
    file = tmp_path / "dsp.log"
    file.write_text("INFO start\nERROR authorization: BearerTokenExample\nException password=letmein\n")
    monkeypatch.setenv("MISSION_TOOLKIT_SUPERVISOR_DSP_LOG", str(file))
    monkeypatch.setenv("MISSION_TOOLKIT_SUPERVISOR_TOKEN", "a" * 64)
    result = supervisor.log_errors(source="dsp", authorization="Bearer " + "a" * 64)
    assert result["configured"]
    assert len(result["lines"]) == 2  # INFO excluded; both physical error lines remain
    assert all("[REDACTED]" in line for line in result["lines"])
    assert result["lines"][0].startswith("ERROR authorization:")
    assert result["lines"][1].startswith("Exception password=")
    assert "letmein" not in repr(result)
    assert "BearerTokenExample" not in repr(result)


def test_supervisor_log_errors_requires_authentication(tmp_path, monkeypatch):
    monkeypatch.setenv("MISSION_TOOLKIT_SUPERVISOR_DSP_LOG", str(tmp_path / "secret.log"))
    monkeypatch.delenv("MISSION_TOOLKIT_SUPERVISOR_TOKEN", raising=False)
    with pytest.raises(HTTPException) as exc:
        supervisor.log_errors(source="dsp", authorization=None)
    assert exc.value.status_code == 403


def test_service_health_rejects_remote_hosts(monkeypatch):
    from workbench.server_admin.feature_testing.service_health import service_health
    monkeypatch.setenv("MISSION_TOOLKIT_SUPERVISOR_DB_HOST", "192.168.1.1")
    with pytest.raises(ValueError, match="loopback"):
        service_health("database")


def test_service_health_reports_unconfigured_dsp(monkeypatch):
    from workbench.server_admin.feature_testing.service_health import service_health
    monkeypatch.delenv("MISSION_TOOLKIT_SUPERVISOR_DSP_PORT", raising=False)
    assert service_health("dsp_map")["configured"] is False


def test_service_health_only_allows_known_services(monkeypatch):
    from workbench.server_admin.feature_testing.service_health import service_health
    with pytest.raises(ValueError, match="unknown"):
        service_health("arbitrary")


def test_inventory_disallows_unapproved_characters(monkeypatch):
    from workbench.server_admin.feature_testing.database_diagnostics import inventory_snapshot
    monkeypatch.setenv("MISSION_TOOLKIT_SUPERVISOR_TEST_CHARIDS", "101,102")
    with pytest.raises(ValueError, match="not approved"):
        inventory_snapshot(103)


def test_inventory_requires_db_config_and_never_guesses_credentials(monkeypatch):
    from workbench.server_admin.feature_testing.database_diagnostics import inventory_snapshot
    monkeypatch.setenv("MISSION_TOOLKIT_SUPERVISOR_TEST_CHARIDS", "101")
    for variable in ("MISSION_TOOLKIT_SUPERVISOR_DB_USER", "MISSION_TOOLKIT_SUPERVISOR_DB_PASSWORD",
                     "MISSION_TOOLKIT_SUPERVISOR_DB_NAME"):
        monkeypatch.delenv(variable, raising=False)
    assert inventory_snapshot(101) == {"configured": False, "charid": 101, "items": []}


def _fake_driver_env(monkeypatch):
    monkeypatch.setenv("MISSION_TOOLKIT_SUPERVISOR_TEST_CHARIDS", "101")
    monkeypatch.setenv("MISSION_TOOLKIT_SUPERVISOR_DB_USER", "ro")
    monkeypatch.setenv("MISSION_TOOLKIT_SUPERVISOR_DB_PASSWORD", "pw")
    monkeypatch.setenv("MISSION_TOOLKIT_SUPERVISOR_DB_NAME", "dspdb")


class _FakeCursor:
    def __init__(self, log):
        self.log = log

    def execute(self, sql, params=None):
        self.log.append(sql.split()[0] + " " + sql.split()[1])

    def fetchall(self):
        return [{"location": 0, "slot": 1, "itemId": 536, "quantity": 1}]

    def close(self):
        self.log.append("cursor.close")


class _FakeConn:
    def __init__(self, log):
        self.log = log

    def cursor(self, **kwargs):
        return _FakeCursor(self.log)

    def rollback(self):
        self.log.append("rollback")

    def close(self):
        self.log.append("conn.close")


def test_inventory_falls_back_to_mysql_connector_when_pymysql_missing(monkeypatch):
    import sys, types
    from workbench.server_admin.feature_testing.database_diagnostics import inventory_snapshot
    _fake_driver_env(monkeypatch)
    log = []
    connector = types.ModuleType("mysql.connector")
    connector.connect = lambda **kw: log.append("connect " + kw["host"]) or _FakeConn(log)
    package = types.ModuleType("mysql")
    package.connector = connector
    monkeypatch.setitem(sys.modules, "pymysql", None)  # forces ImportError
    monkeypatch.setitem(sys.modules, "mysql", package)
    monkeypatch.setitem(sys.modules, "mysql.connector", connector)
    result = inventory_snapshot(101)
    assert result["configured"] is True and result["items"][0]["itemId"] == 536
    assert log[:4] == ["connect 127.0.0.1", "SET TRANSACTION", "START TRANSACTION", "SELECT location,"]
    assert log[-3:] == ["rollback", "cursor.close", "conn.close"]


def test_inventory_reports_missing_driver_as_runtime_error(monkeypatch):
    import sys
    from workbench.server_admin.feature_testing.database_diagnostics import inventory_snapshot
    _fake_driver_env(monkeypatch)
    monkeypatch.setitem(sys.modules, "pymysql", None)
    monkeypatch.setitem(sys.modules, "mysql", None)
    monkeypatch.setitem(sys.modules, "mysql.connector", None)
    with pytest.raises(RuntimeError, match="no MySQL driver"):
        inventory_snapshot(101)


def test_inventory_requires_gateway_auth_before_character_lookup(monkeypatch):
    monkeypatch.setenv("MISSION_TOOLKIT_SUPERVISOR_TEST_CHARIDS", "101")
    monkeypatch.delenv("MISSION_TOOLKIT_SUPERVISOR_TOKEN", raising=False)
    with pytest.raises(HTTPException) as exc:
        supervisor.test_character_inventory(charid=101, authorization=None)
    assert exc.value.status_code == 403


def test_run_evidence_exact_lookup_preserves_assertions_and_evaluation(tmp_path, monkeypatch):
    from workbench.server_admin.feature_testing.results import append_result
    token = "Bearer " + "a" * 64
    monkeypatch.setenv("MISSION_TOOLKIT_SUPERVISOR_TOKEN", "a" * 64)
    db = tmp_path / "results.sqlite"
    monkeypatch.setenv("MISSION_TOOLKIT_TEST_RESULTS_DB", str(db))
    base = {"run_id": "obs-older-run", "case_id": "MOG-09", "feature_id": "moghancement",
            "stage": "key_item", "verdict": "PASS", "observed_at": "2026-10-19T08:00:00Z",
            "dsp_commit": "d" * 40, "headless_commit": "h" * 40, "toolkit_commit": "t" * 40}
    append_result(db, {**base, "evidence": {"assertions": [{"name": "inventory", "ok": True, "expected": [1], "observed": [1]}],
                                           "observations": {"provenance": {"headless_dll_sha256": "f" * 64}}}})
    append_result(db, {**base, "case_id": "MOG-10", "stage": "modifier", "verdict": "FAIL",
                       "evidence": {"evaluation": {"reason": "mismatch"}}})
    result = supervisor.run_evidence("obs-older-run", authorization=token)
    assert result["count"] == 2
    assert result["execution_enabled"] is False
    assert result["records"][0]["assertions"][0]["name"] == "inventory"
    assert result["records"][1]["evaluation"]["reason"] == "mismatch"
    assert "headless_dll_sha256" in str(result)
    with pytest.raises(HTTPException) as exc:
        supervisor.run_evidence("different-run", authorization=token)
    assert exc.value.status_code == 404


def test_run_evidence_fails_closed_and_disallows_invalid_run_ids(monkeypatch, tmp_path):
    token = "Bearer " + "a" * 64
    monkeypatch.setenv("MISSION_TOOLKIT_SUPERVISOR_TOKEN", "a" * 64)
    monkeypatch.setenv("MISSION_TOOLKIT_TEST_RESULTS_DB", str(tmp_path / "missing.db"))
    with pytest.raises(HTTPException) as exc:
        supervisor.run_evidence("any", authorization=None)
    assert exc.value.status_code == 403
    with pytest.raises(HTTPException) as exc:
        supervisor.run_evidence("x" * 257, authorization=token)
    assert exc.value.status_code == 400
    with pytest.raises(HTTPException) as exc:
        supervisor.run_evidence("unseen", authorization=token)
    assert exc.value.status_code == 404


def test_run_evidence_rejects_malformed_stored_json(tmp_path, monkeypatch):
    import sqlite3
    from workbench.server_admin.feature_testing.results import append_result
    monkeypatch.setenv("MISSION_TOOLKIT_SUPERVISOR_TOKEN", "a" * 64)
    db = tmp_path / "bad.sqlite"
    monkeypatch.setenv("MISSION_TOOLKIT_TEST_RESULTS_DB", str(db))
    append_result(db, {"run_id": "bad", "case_id": "MOG-01", "feature_id": "moghancement",
                       "stage": "key_item", "verdict": "FAIL", "observed_at": "2026-10-19T00:00:00Z",
                       "dsp_commit": "d", "headless_commit": "h", "toolkit_commit": "t",
                       "evidence": {"evaluation": "present"}})
    with sqlite3.connect(db) as conn:
        conn.execute("UPDATE feature_test_results SET evidence_json = ? WHERE run_id = ?", ("{broken", "bad"))
    with pytest.raises(HTTPException) as exc:
        supervisor.run_evidence("bad", authorization="Bearer " + "a" * 64)
    assert exc.value.status_code == 400


def test_supervisor_source_search_scoped_and_authenticated(tmp_path, monkeypatch):
    root = tmp_path / "src"
    root.mkdir()
    (root / "handler.py").write_text("def SaveKeyItems(): pass\npassword = 'hidden' # SaveKeyItems\n", encoding="utf-8")
    (root / "secret.env").write_text("SaveKeyItems", encoding="utf-8")
    (root / "hidden.py").symlink_to(root / "handler.py")
    monkeypatch.setenv("MISSION_TOOLKIT_SUPERVISOR_DSP_SOURCE_ROOT", str(root))
    monkeypatch.setenv("MISSION_TOOLKIT_SUPERVISOR_TOKEN", "a" * 64)
    token = "Bearer " + "a" * 64
    result = supervisor.supervisor_search_source("SaveKeyItems", repository="dsp", authorization=token)
    assert [(row["path"], row["line"]) for row in result["matches"]] == [("handler.py", 1)]
    assert result["source_revision"] == "local_checkout_unverified"
    assert all("password" not in row["excerpt"].lower() for row in result["matches"])
    assert all(not row["path"].endswith((".env", "hidden.py")) for row in result["matches"])
    with pytest.raises(HTTPException) as exc:
        supervisor.supervisor_search_source("SaveKeyItems", repository="dsp", authorization=None)
    assert exc.value.status_code == 403
    with pytest.raises(HTTPException) as exc:
        supervisor.supervisor_search_source("SaveKeyItems", repository="remote", authorization=token)
    assert exc.value.status_code == 400


def test_run_evidence_explains_assertion_count_and_ki_semantics(tmp_path, monkeypatch):
    from workbench.server_admin.feature_testing.results import append_result
    db = tmp_path / "runs.db"
    monkeypatch.setenv("MISSION_TOOLKIT_TEST_RESULTS_DB", str(db))
    monkeypatch.setenv("MISSION_TOOLKIT_SUPERVISOR_TOKEN", "a" * 64)
    append_result(db, {"run_id": "r1", "case_id": "MOG-09", "feature_id": "moghancement",
                       "stage": "key_item", "verdict": "PASS", "observed_at": "2026-10-19T00:00:00Z",
                       "dsp_commit": "d", "headless_commit": "h", "toolkit_commit": "t",
                       "evidence": {"assertions": [{"ok": True}, {"ok": True}],
                                    "observations": {"client_key_items": [387], "oracle": {"key_item": 0}}}})
    response = supervisor.run_evidence("r1", authorization="Bearer " + "a" * 64)
    assert response["result_records"] == 1 and response["assertion_count"] == 2
    assert any("held key items" in note for note in response["interpretation_notes"])
