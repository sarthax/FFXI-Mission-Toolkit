"""Durable job phase regression coverage without local XiHeadless execution."""
import sqlite3
from workbench.server_admin.feature_testing import execution_jobs as jobs


def test_progress_schema_migrates_old_database(tmp_path, monkeypatch):
    dbpath = tmp_path / "jobs.sqlite"
    monkeypatch.setenv("MISSION_TOOLKIT_TEST_JOBS_DB", str(dbpath))
    with sqlite3.connect(dbpath) as db:
        db.execute("""CREATE TABLE feature_test_jobs (
            id TEXT PRIMARY KEY, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
            case_id TEXT NOT NULL, status TEXT NOT NULL, account TEXT NOT NULL,
            charid INTEGER NOT NULL, run_id TEXT, verdict TEXT, error TEXT)""")
        db.execute("INSERT INTO feature_test_jobs VALUES (?,?,?,?,?,?,?,?,?,?)",
                   ("a"*32, "2026-10-19T01:00:00Z", "2026-10-19T01:00:00Z",
                    "MOG-09", "RUNNING", "xitest07", 21836, None, None, None))
    rows = jobs.jobs()
    assert rows[0]["phase"] == "not_started"
    jobs._set_phase("a"*32, "runner_invoked")
    assert jobs.jobs()[0]["phase"] == "runner_invoked"
    jobs._set_phase("a"*32, "report_validated")
    assert jobs.jobs()[0]["phase"] == "report_validated"
    jobs.recover_interrupted("a"*32, acknowledged=True)
    assert jobs.jobs()[0]["phase"] == "operator_reconciled"
    assert jobs.jobs()[0]["status"] == "INTERRUPTED"


def test_progress_rejects_unknown_phase(tmp_path, monkeypatch):
    import pytest
    monkeypatch.setenv("MISSION_TOOLKIT_TEST_JOBS_DB", str(tmp_path/"jobs.sqlite"))
    with pytest.raises(ValueError, match="unknown"):
        jobs._set_phase("a"*32, "client_passed")
