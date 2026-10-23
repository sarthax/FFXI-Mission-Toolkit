"""P0 #1333: isolate supervisor provenance before any readiness or operator launch.

Every path, credential and character is synthetic and local to pytest tmp_path.
No live process, DB, HTTP service, packet, client or Headless invocation.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from unittest import mock

import pytest

from workbench.server_admin.feature_testing import test_execution_settings as settings
from workbench.server_admin.feature_testing.execution_preflight import preflight
from workbench.server_admin.feature_testing.execution_jobs import authorize_operator
from workbench.server_admin.feature_testing.execution_cli import execute_mog09


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    # Explicitly simulate a separate Toolkit process; remove inherited test
    # configuration first so this fixture doesn't depend on the CI runner.
    for k in list(os.environ):
        if k.startswith(("MISSION_TOOLKIT_TEST_", "MISSION_TOOLKIT_SUPERVISOR_")):
            monkeypatch.delenv(k, raising=False)
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()
    local = tmp_path / "production-localappdata"
    local.mkdir()
    monkeypatch.setenv("LOCALAPPDATA", str(local))
    monkeypatch.setenv("MISSION_TOOLKIT_TEST_DATA_DIR", str(sandbox))
    yield sandbox
    settings.apply_to_environ(settings._empty())


def _headless(tmp_path):
    root = tmp_path / "synthetic-headless"
    (root / "tools").mkdir(parents=True)
    (root / "bin" / "mcp").mkdir(parents=True)
    (root / "tools" / "observation_runner.py").write_text("# synthetic", encoding="utf-8")
    (root / "bin" / "mcp" / "XiHeadless.dll").write_bytes(b"synthetic-no-execution")
    return root


def _shell(monkeypatch, sandbox, root, token="p" * 40, charid="17"):
    values = {
        "MISSION_TOOLKIT_TEST_HEADLESS_ROOT": str(root),
        "MISSION_TOOLKIT_TEST_RESULTS_DB": str(sandbox / "results.db"),
        "MISSION_TOOLKIT_TEST_DRAFTS_DB": str(sandbox / "drafts.db"),
        "MISSION_TOOLKIT_TEST_JOBS_DB": str(sandbox / "jobs.db"),
        "MISSION_TOOLKIT_TEST_ARTIFACTS_ROOT": str(sandbox / "artifacts"),
        "MISSION_TOOLKIT_SUPERVISOR_TEST_CHARIDS": charid,
        "MISSION_TOOLKIT_SUPERVISOR_TOKEN": token,
        "MISSION_TOOLKIT_TEST_OPERATOR_TOKEN": token,
        "MISSION_TOOLKIT_SUPERVISOR_DB_USER": "synthetic_reader",
        "MISSION_TOOLKIT_SUPERVISOR_DB_PASSWORD": "synthetic_password",
        "MISSION_TOOLKIT_SUPERVISOR_DB_NAME": "synthetic_db",
        "MISSION_TOOLKIT_SUPERVISOR_DB_PORT": "3306",
    }
    for key, value in values.items():
        monkeypatch.setenv(key, value)


def _valid_sandbox_settings(isolated, root, token="s" * 40):
    # No access to a real supervisor service; this is an explicit local
    # synthetic setup record to test provenance matching only.
    cfg = settings._empty()
    cfg.update(enabled=True, headless_root=str(root), charids=[23])
    cfg["tokens"].update(operator=token, supervisor="v" * 40)
    cfg["db"].update(user="sandbox_reader", password="sandbox_only", name="sandbox_db")
    settings._save(cfg)
    settings.apply_to_environ(cfg)
    return cfg


def test_isolated_missing_settings_cannot_inherit_prod_supervisor(isolated, monkeypatch, tmp_path):
    root = _headless(tmp_path)
    local_settings = tmp_path / "production-localappdata" / "MissionToolkit" / "test_execution"
    local_settings.mkdir(parents=True)
    (local_settings / "settings.json").write_text(json.dumps({
        "enabled": True,
        "tokens": {"operator": "p" * 40, "supervisor": "p" * 40},
        "charids": [17], "headless_root": str(root),
    }), encoding="utf-8")
    _shell(monkeypatch, isolated, root)
    # The inherited env is otherwise enough for the old preflight to show
    # Ready to run, so a pass here proves the missing isolation gate is caught.
    result = preflight("moghancement", "MOG-09")
    assert {x["id"] for x in result["checks"] if not x["ok"]} == {"sandbox_isolation"}
    assert result["ready_for_operator_review"] is False
    assert result["execution_enabled"] is False
    assert not settings.ui_mode_active()
    shown = settings.status()
    assert shown["ready_to_run"] is False
    assert shown["selected_root"] == ""  # not inherited from production env
    assert not next(x for x in shown["steps"] if x["id"] == "characters")["ok"]
    redacted = repr(shown) + repr(settings.sandbox_execution_check())
    assert "p" * 40 not in redacted and "synthetic_password" not in redacted
    with pytest.raises(PermissionError, match="Isolated"):
        authorize_operator("p" * 40)


def test_isolated_launch_refuses_inherited_prod_before_any_subprocess(isolated, monkeypatch, tmp_path):
    root = _headless(tmp_path)
    _shell(monkeypatch, isolated, root)
    out = isolated / "artifacts" / "run"
    with mock.patch("workbench.server_admin.feature_testing.execution_cli.subprocess.run") as run:
        with pytest.raises(ValueError, match="sandbox_isolation"):
            execute_mog09(account="synthetic_account", charid=17, out_dir=out,
                          supervisor="http://127.0.0.1:8420", approved=True)
        run.assert_not_called()
    assert not out.exists()


def test_linked_prod_settings_inside_sandbox_are_rejected(isolated, monkeypatch, tmp_path):
    root = _headless(tmp_path)
    external = tmp_path / "production-localappdata" / "MissionToolkit" / "test_execution"
    external.mkdir(parents=True)
    (external / "settings.json").write_text(json.dumps({
        "enabled": True, "tokens": {"operator": "p" * 40, "supervisor": "v" * 40},
        "headless_root": str(root), "charids": [23],
        "db": {"user": "synthetic", "password": "synthetic", "name": "fake", "port": 3306}
    }), encoding="utf-8")
    (isolated / "settings.json").symlink_to(external / "settings.json")
    _shell(monkeypatch, isolated, root)
    assert settings.sandbox_operator_check()["ok"] is False
    assert settings.sandbox_execution_check()["ok"] is False
    assert preflight("moghancement", "MOG-09")["ready_for_operator_review"] is False
    with pytest.raises(PermissionError):
        authorize_operator("p" * 40)


def test_partial_sandbox_settings_fail_closed(isolated, monkeypatch, tmp_path):
    root = _headless(tmp_path)
    _shell(monkeypatch, isolated, root)
    cfg = settings._empty()
    cfg["enabled"] = True
    cfg["charids"] = [17]
    settings._save(cfg)
    assert settings.sandbox_execution_check()["ok"] is False
    assert preflight("moghancement", "MOG-09")["ready_for_operator_review"] is False
    # Deliberately malformed settings must not crash the readiness route.
    (isolated / "settings.json").write_text(
        json.dumps({"enabled": True, "charids": 17, "tokens": {"operator": 5}}),
        encoding="utf-8",
    )
    assert settings.sandbox_execution_check()["ok"] is False


def test_sandbox_drafts_can_be_authorized_without_supervisor_execution(isolated, tmp_path):
    cfg = settings._empty()
    cfg.update(enabled=True)
    cfg["tokens"]["operator"] = "d" * 40  # synthetic sandbox-owned UI token
    settings._save(cfg)
    settings.apply_to_environ(cfg)
    assert settings.sandbox_operator_check()["ok"] is True
    assert settings.ui_mode_active()
    authorize_operator("d" * 40)  # authorization for drafts, NOT execution
    assert settings.sandbox_execution_check()["ok"] is False
    assert preflight("moghancement", "MOG-09")["ready_for_operator_review"] is False


def test_explicit_sandbox_config_matches_and_does_not_promote_execution(isolated, tmp_path):
    root = _headless(tmp_path)
    cfg = _valid_sandbox_settings(isolated, root)
    state = settings.sandbox_execution_check()
    assert state["isolated"] and state["ok"]
    pre = preflight("moghancement", "MOG-09")
    assert pre["ready_for_operator_review"] is True
    assert pre["execution_enabled"] is False and pre["launch_implemented"] is False
    assert settings.ui_mode_active()
    authorize_operator(cfg["tokens"]["operator"])
    with pytest.raises(PermissionError):
        authorize_operator("wrong-synthetic-operator-token")


@pytest.mark.parametrize("field,value", [
    ("MISSION_TOOLKIT_SUPERVISOR_TOKEN", "p" * 40),
    ("MISSION_TOOLKIT_TEST_OPERATOR_TOKEN", "p" * 40),
    ("MISSION_TOOLKIT_SUPERVISOR_TEST_CHARIDS", "17"),
    ("MISSION_TOOLKIT_SUPERVISOR_DB_PASSWORD", "production_password"),
])
def test_wrong_sandbox_credential_or_allowlist_blocks(isolated, tmp_path, monkeypatch, field, value):
    root = _headless(tmp_path)
    cfg = _valid_sandbox_settings(isolated, root)
    monkeypatch.setenv(field, value)
    assert settings.sandbox_execution_check()["ok"] is False
    assert preflight("moghancement", "MOG-09")["ready_for_operator_review"] is False
    assert settings.status()["ready_to_run"] is False
    if field == "MISSION_TOOLKIT_TEST_OPERATOR_TOKEN":
        with pytest.raises(PermissionError, match="Isolated"):
            authorize_operator(cfg["tokens"]["operator"])
    else:
        # Draft-only operator authorization must be independent of
        # unavailable supervisor execution credentials.
        authorize_operator(cfg["tokens"]["operator"])


def test_tampered_disposable_allowlist_and_reused_tokens_block(isolated, tmp_path):
    root = _headless(tmp_path)
    cfg = _valid_sandbox_settings(isolated, root)
    for invalid in ([0], [23, 23], ["23"], [-1]):
        bad = dict(cfg)
        bad["charids"] = invalid
        settings._save(bad)
        # Test-only direct JSON changes cannot elevate the old environment.
        assert settings.sandbox_execution_check()["ok"] is False
    bad = dict(cfg)
    bad["charids"] = [23]
    bad["tokens"] = dict(cfg["tokens"])
    bad["tokens"]["supervisor"] = bad["tokens"]["operator"]
    settings._save(bad)
    assert settings.sandbox_execution_check()["ok"] is False
    assert preflight("moghancement", "MOG-09")["ready_for_operator_review"] is False


def test_shared_results_or_artifacts_path_blocks(isolated, tmp_path, monkeypatch):
    root = _headless(tmp_path)
    _valid_sandbox_settings(isolated, root)
    for key in ("MISSION_TOOLKIT_TEST_RESULTS_DB", "MISSION_TOOLKIT_TEST_DRAFTS_DB",
                "MISSION_TOOLKIT_TEST_JOBS_DB", "MISSION_TOOLKIT_TEST_ARTIFACTS_ROOT"):
        with monkeypatch.context() as m:
            m.setenv(key, str(tmp_path / "outside-sandbox" / "db"))
            assert settings.sandbox_execution_check()["ok"] is False


def test_production_shell_precedence_unmodified_without_test_data_dir(isolated, tmp_path, monkeypatch):
    root = _headless(tmp_path)
    _shell(monkeypatch, isolated, root)
    monkeypatch.delenv("MISSION_TOOLKIT_TEST_DATA_DIR")
    check = settings.sandbox_execution_check()
    assert check["isolated"] is False and check["ok"] is True
    pre = preflight("moghancement", "MOG-09")
    assert pre["ready_for_operator_review"] is True
    assert not any(x["id"] == "sandbox_isolation" for x in pre["checks"])
    assert pre["execution_enabled"] is False
    authorize_operator("p" * 40)


def test_sandbox_cannot_select_default_production_settings_directory(monkeypatch, tmp_path):
    local = tmp_path / "localappdata"
    monkeypatch.setenv("LOCALAPPDATA", str(local))
    monkeypatch.setenv("MISSION_TOOLKIT_TEST_DATA_DIR", str(local / "MissionToolkit" / "test_execution"))
    state = settings.sandbox_execution_check()
    assert state["isolated"] and not state["ok"]


def test_builder_template_never_advertises_inherited_preflight_as_launch_authority():
    template = (Path(__file__).resolve().parents[1] / "gui" / "templates" /
                "feature_testing.html").read_text(encoding="utf-8")
    assert "Prerequisites detected — operator approval still required" in template
    assert '{% if not builder_preflight.ready_for_operator_review %}disabled' in template
    assert 'aria-disabled="true"' in template
    assert 'id="ft-run-approval"' in template
