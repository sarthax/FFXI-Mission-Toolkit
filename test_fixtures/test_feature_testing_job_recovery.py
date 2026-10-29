"""Offline lifecycle tests: a stale job may only be reconciled by explicit operator action."""
import sqlite3
import threading
import pytest

from workbench.server_admin.feature_testing import execution_jobs as j


def _insert(db, job_id, status="RUNNING"):
    with sqlite3.connect(db) as conn:
        conn.execute("INSERT INTO feature_test_jobs (id, created_at, updated_at, case_id, status, account, charid) VALUES (?,?,?,?,?,?,?)",
                     (job_id, "2026-10-19T00:00:00Z", "2026-10-19T00:00:00Z", "MOG-09", status, "xitest07", 21836))


def test_reconciliation_requires_acknowledgement_and_is_durable(tmp_path, monkeypatch):
    db = tmp_path / "jobs.db"
    monkeypatch.setenv("MISSION_TOOLKIT_TEST_JOBS_DB", str(db))
    with j._connect() as conn:
        pass
    job_id = "a" * 32
    _insert(db, job_id)
    with pytest.raises(ValueError, match="acknowledge"):
        j.recover_interrupted(job_id, acknowledged=False)
    assert j.jobs()[0]["status"] == "RUNNING"
    result = j.recover_interrupted(job_id, acknowledged=True)
    assert result["status"] == "INTERRUPTED"
    assert j.jobs()[0]["status"] == "INTERRUPTED"
    with pytest.raises(ValueError, match="only active"):
        j.recover_interrupted(job_id, acknowledged=True)


def test_reconciliation_refuses_running_thread(tmp_path, monkeypatch):
    db = tmp_path / "jobs.db"
    monkeypatch.setenv("MISSION_TOOLKIT_TEST_JOBS_DB", str(db))
    with j._connect():
        pass
    job_id = "b" * 32
    _insert(db, job_id)
    class FakeThread:
        def is_alive(self): return True
    monkeypatch.setitem(j._THREADS, job_id, FakeThread())
    with pytest.raises(ValueError, match="still running"):
        j.recover_interrupted(job_id, acknowledged=True)
    assert j.jobs()[0]["status"] == "RUNNING"


def test_reconciliation_http_authentication_and_approval(monkeypatch):
    host = pytest.importorskip("workbench.app.host", exc_type=Exception)
    from fastapi.testclient import TestClient
    monkeypatch.setenv("MISSION_TOOLKIT_TEST_OPERATOR_TOKEN", "a"*64)
    c = TestClient(host.app, client=("127.0.0.1", 50000))
    path = "/feature-testing/builder/jobs/" + "a"*32 + "/reconcile"
    assert c.post(path, json={"acknowledged":True}).status_code == 403
    assert c.post(path, json={"acknowledged":False},
                  headers={"X-Test-Operator-Token":"a"*64}).status_code == 400
