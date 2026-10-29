"""#1484: per-run bot switches. Offline only; nothing is launched and no subprocess runs."""
import sqlite3

import pytest

from workbench.server_admin.feature_testing import execution_jobs, run_options
from workbench.server_admin.feature_testing.run_outcome import describe_outcome


def test_defaults_have_every_shortcut_off():
    chosen = run_options.normalize(None)
    assert not any(chosen[s["env"]] for s in run_options.switches() if s["shortcut"])
    assert run_options.shortcuts_enabled(None) == []


@pytest.mark.parametrize("bad", [{"NOT_A_FLAG": True}, {"XIBOT_QUICK_TRAVEL": "1"}, {"XIBOT_QUICK_TRAVEL": 1}, ["x"]])
def test_normalize_refuses_unknown_names_and_non_booleans(bad):
    with pytest.raises(ValueError):
        run_options.normalize(bad)


def test_apply_sets_one_and_removes_inherited_shortcuts():
    env = {"XIBOT_GRIND_HERE": "1", "XIBOT_QUICK_TRAVEL": "1", "XI_POS_TRACE": "1"}
    run_options.apply_to_env(env, {"XIBOT_QUICK_TRAVEL": True, "XI_POS_TRACE": False})
    assert env["XIBOT_QUICK_TRAVEL"] == "1"
    assert "XIBOT_GRIND_HERE" not in env and "XI_POS_TRACE" not in env  # operator-shell values must not leak through
    assert env["XIBOT_VERBOSE"] == "0"  # unset would mean verbose, so off is explicit


def test_shortcuts_enabled_names_only_shortcuts():
    names = run_options.shortcuts_enabled({"XIBOT_ALLOW_GM_WARP": True, "XI_RDM_SHADOW_TRACE": True})
    assert names == ["Allow GM warps"]


@pytest.fixture
def jobs_db(tmp_path, monkeypatch):
    monkeypatch.setenv("MISSION_TOOLKIT_TEST_JOBS_DB", str(tmp_path / "jobs.db"))
    return tmp_path / "jobs.db"


def _insert(db_path, run_id, options_json=None, **extra):
    with sqlite3.connect(str(db_path)) as db:
        db.execute("CREATE TABLE IF NOT EXISTS feature_test_jobs (id TEXT PRIMARY KEY, created_at TEXT NOT NULL, "
                   "updated_at TEXT NOT NULL, case_id TEXT NOT NULL, status TEXT NOT NULL, account TEXT NOT NULL, "
                   "charid INTEGER NOT NULL, run_id TEXT, verdict TEXT, error TEXT)")
        db.execute("INSERT INTO feature_test_jobs (id,created_at,updated_at,case_id,status,account,charid,run_id) "
                   "VALUES (?,?,?,?,?,?,?,?)", ("j" + run_id, "t", "t", "MOG-09", "COMPLETED", "acct", 1, run_id))


def test_old_job_rows_migrate_and_report_options_as_not_recorded(jobs_db):
    _insert(jobs_db, "old-run")
    job = execution_jobs.job_for_run("old-run")
    assert job["run_options"] is None  # never "defaults"
    summary = describe_outcome({"verdict": "PASS", "evidence": {}}, job)["job"]["run_options"]
    assert summary == {"recorded": False, "shortcuts": [], "on": []}


def test_recorded_options_round_trip_and_flag_shortcuts(jobs_db):
    _insert(jobs_db, "new-run")
    with sqlite3.connect(str(jobs_db)) as db:
        db.execute("ALTER TABLE feature_test_jobs ADD COLUMN run_options TEXT")
        db.execute("UPDATE feature_test_jobs SET run_options=? WHERE run_id=?",
                   ('{"XIBOT_QUICK_TRAVEL": true, "XI_POS_TRACE": true}', "new-run"))
    job = execution_jobs.job_for_run("new-run")
    summary = describe_outcome({"verdict": "PASS", "evidence": {}}, job)["job"]["run_options"]
    assert summary["recorded"] and summary["shortcuts"] == ["Quick travel"]
    assert summary["on"] == ["Quick travel", "Position trace"]


def test_enqueue_refuses_bad_options_before_touching_the_store(jobs_db):
    with pytest.raises(ValueError):
        execution_jobs.enqueue("acct", 1, 8420, {"NOPE": True})
    assert not jobs_db.exists()
