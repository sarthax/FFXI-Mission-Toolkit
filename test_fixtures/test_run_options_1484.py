"""#1484: headless bot run options are allow-listed, safe by default, passed to the env and stored with the run."""
import subprocess
from pathlib import Path

import pytest

from workbench.server_admin.feature_testing import execution_jobs, run_options
from workbench.server_admin.feature_testing.run_outcome import describe_outcome

SHORTCUTS = ("XIBOT_QUICK_TRAVEL", "XIBOT_ALLOW_GM_WARP", "XIBOT_GRIND_HERE")


def test_defaults_are_safe():
    d = run_options.resolve_run_options(None)
    assert set(d) == set(run_options.RUN_OPTIONS) and len(d) == 7
    assert not any(d[n] for n in SHORTCUTS)
    assert d["XI_POS_TRACE"] is True
    assert run_options.shortcuts_enabled(d) == []


@pytest.mark.parametrize("bad", [{"PATH": True}, {"XIBOT_QUICK_TRAVEL": "1"}, {"XIBOT_QUICK_TRAVEL": 1}, ["x"]])
def test_rejects_unknown_or_non_bool(bad):
    with pytest.raises(ValueError):
        run_options.resolve_run_options(bad)


def test_env_and_json_roundtrip():
    o = run_options.resolve_run_options({"XIBOT_QUICK_TRAVEL": True, "XI_POS_TRACE": False})
    env = run_options.env_for(o)
    assert env["XIBOT_QUICK_TRAVEL"] == "1" and env["XI_POS_TRACE"] == "0" and env["XIBOT_ALLOW_GM_WARP"] == "0"
    assert run_options.from_json(run_options.to_json(o)) == o
    assert run_options.from_json(None) is None and run_options.from_json("garbage") is None


def test_job_stores_options_and_rejects_bad(monkeypatch, tmp_path):
    monkeypatch.setenv("MISSION_TOOLKIT_TEST_JOBS_DB", str(tmp_path / "jobs.db"))
    monkeypatch.setenv("MISSION_TOOLKIT_TEST_ARTIFACTS_ROOT", str(tmp_path))
    monkeypatch.setattr(execution_jobs.threading.Thread, "start", lambda self: None)
    import workbench.server_admin.feature_testing.test_builder as tb
    monkeypatch.setattr(tb, "build_plan", lambda *a, **k: {"ready_for_operator_review": True})
    with pytest.raises(ValueError):
        execution_jobs.enqueue("acct", 1, 8420, {"BOGUS": True})
    assert execution_jobs.jobs() == []
    job_id = execution_jobs.enqueue("acct", 1, 8420, {"XIBOT_ALLOW_GM_WARP": True})
    row = execution_jobs.jobs()[0]
    assert row["id"] == job_id and row["run_options"]["XIBOT_ALLOW_GM_WARP"] is True
    assert row["run_options"]["XIBOT_QUICK_TRAVEL"] is False


def test_run_context_shows_shortcuts():
    rec = {"verdict": "PASS", "evidence": {}}
    opts = run_options.resolve_run_options({"XIBOT_QUICK_TRAVEL": True})
    out = describe_outcome(rec, {"status": "COMPLETED", "run_options": opts})
    assert out["shortcuts_enabled"] == ["XIBOT_QUICK_TRAVEL"]
    assert "shortcuts_enabled" not in describe_outcome(rec, {"status": "COMPLETED"})


def test_subprocess_env_gets_switches(monkeypatch, tmp_path):
    from workbench.server_admin.feature_testing import execution_cli as cli
    captured = {}

    def fake_run(args, **kw):
        captured["env"] = kw["env"]
        raise RuntimeError("stop")

    root = tmp_path / "hl"
    root.mkdir()
    monkeypatch.setenv("MISSION_TOOLKIT_TEST_HEADLESS_ROOT", str(root))
    monkeypatch.setenv("MISSION_TOOLKIT_SUPERVISOR_TEST_CHARIDS", "5")
    monkeypatch.setenv("XIBOT_QUICK_TRAVEL", "1")  # ambient value must be overridden by the explicit default
    monkeypatch.setattr(cli, "preflight", lambda *a: {"ready_for_operator_review": True, "checks": []})
    monkeypatch.setattr(subprocess, "run", fake_run)
    out = tmp_path / "out"
    with pytest.raises(RuntimeError):
        cli.execute_mog09(account="a", charid=5, out_dir=out, supervisor="http://127.0.0.1:8420",
                          approved=True, run_options={"XIBOT_VERBOSE": True})
    assert captured["env"]["XIBOT_VERBOSE"] == "1" and captured["env"]["XIBOT_QUICK_TRAVEL"] == "0"


def test_launch_rejects_unknown_option(monkeypatch):
    from fastapi.testclient import TestClient
    host = pytest.importorskip("workbench.app.host", exc_type=Exception)
    monkeypatch.setenv("MISSION_TOOLKIT_TEST_OPERATOR_TOKEN", "a" * 64)
    body = {"account": "xitest07", "charid": 21836, "approval": True, "run_options": {"EVIL": True}}
    r = TestClient(host.app).post("/feature-testing/builder/launch", json=body,
                                  headers={"X-Test-Operator-Token": "a" * 64})
    assert r.status_code in (400, 403)


def test_gui_has_run_options():
    html = (Path(__file__).resolve().parents[1] / "gui/templates/feature_testing.html").read_text(encoding="utf-8")
    assert "ft-run-option" in html and "run_options:" in html
