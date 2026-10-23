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
from fastapi import HTTPException

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
    assert settings.load()["tokens"]["operator"] == ""  # never read linked production JSON
    assert settings.status()["charids"] == []  # never disclose production allowlist
    assert preflight("moghancement", "MOG-09")["ready_for_operator_review"] is False
    before = (external / "settings.json").read_bytes()
    with pytest.raises(ValueError, match="safe for writes"):
        settings.set_enabled(True)
    assert (external / "settings.json").read_bytes() == before
    with pytest.raises(PermissionError):
        authorize_operator("p" * 40)


def test_http_launch_refuses_inherited_token_before_job_enqueue(
        isolated, monkeypatch, tmp_path):
    from workbench.server_admin.feature_testing.router import (
        LaunchRequest, launch_test
    )
    root = _headless(tmp_path)
    _shell(monkeypatch, isolated, root)
    req = mock.Mock()
    req.client.host = "127.0.0.1"
    req.base_url = "http://127.0.0.1:8420/"
    req.headers = {"sec-fetch-site": "same-origin",
                   "x-requested-with": "toolkit-ui"}
    request = LaunchRequest(
        account="synthetic_account", charid=17, supervisor_port=8420,
        approval=True,
    )
    with mock.patch(
            "workbench.server_admin.feature_testing.execution_jobs.enqueue"
    ) as enqueue:
        with pytest.raises(HTTPException) as rejected:
            launch_test(req, request, x_test_operator_token="p" * 40)
        assert rejected.value.status_code == 403
        enqueue.assert_not_called()


def test_predictable_temporary_symlink_cannot_overwrite_external_file(isolated, tmp_path):
    # An attacker-controlled legacy settings.tmp is never followed by sandbox
    # writes. The production/default writer is deliberately not exercised.
    outside = tmp_path / "outside-sandbox-settings.json"
    outside.write_text("synthetic original production sentinel", encoding="utf-8")
    (isolated / "settings.tmp").symlink_to(outside)
    cfg = settings._empty()
    cfg["enabled"] = True
    settings._save(cfg)
    assert outside.read_text(encoding="utf-8") == "synthetic original production sentinel"
    assert (isolated / "settings.tmp").is_symlink()
    assert (isolated / "settings.json").is_file()
    assert settings.load()["enabled"] is True
    assert list(isolated.glob(".settings-*.tmp")) == []


def test_symlinked_parent_of_selected_sandbox_rejected_without_writes(
        tmp_path, monkeypatch):
    outside = tmp_path / "external-parent"
    outside.mkdir()
    alias = tmp_path / "linked-parent"
    alias.symlink_to(outside, target_is_directory=True)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "production-localappdata"))
    monkeypatch.setenv("MISSION_TOOLKIT_TEST_DATA_DIR", str(alias / "sandbox"))
    assert settings.sandbox_operator_check()["ok"] is False
    assert settings.sandbox_execution_check()["ok"] is False
    assert settings.load()["enabled"] is False
    with pytest.raises(ValueError, match="safe for writes"):
        settings.set_enabled(True)
    assert not (outside / "sandbox").exists()


def test_sandbox_inside_repo_or_production_settings_root_is_rejected(tmp_path, monkeypatch):
    prod_root = tmp_path / "local-app" / "MissionToolkit" / "test_execution"
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local-app"))
    for selected in (prod_root / "synthetic-child",
                     settings._REPO / "test_fixtures" / "unwanted-sandbox"):
        with monkeypatch.context() as m:
            m.setenv("MISSION_TOOLKIT_TEST_DATA_DIR", str(selected))
            assert settings.sandbox_execution_check()["ok"] is False
            with pytest.raises(ValueError, match="safe for writes"):
                settings.set_enabled(True)
            assert not (selected / "settings.json").exists()


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
        json.dumps({"enabled": True, "charids": 17, "headless_root": 123, "tokens": {"operator": 5}}),
        encoding="utf-8",
    )
    assert settings.sandbox_execution_check()["ok"] is False
    assert settings.status()["ready_to_run"] is False


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
    assert not any(x["id"] == "sandbox_isolation" for x in settings.status()["steps"])
    assert pre["execution_enabled"] is False
    authorize_operator("p" * 40)


@pytest.mark.parametrize("selected", ["", "  "])
def test_explicit_empty_test_dir_never_falls_back_to_production(
        tmp_path, monkeypatch, selected):
    local = tmp_path / "production-localappdata"
    production = local / "MissionToolkit" / "test_execution"
    production.mkdir(parents=True)
    original = json.dumps({
        "enabled": True,
        "account": "synthetic-production-should-not-appear",
        "charids": [17],
        "tokens": {"operator": "p" * 40, "supervisor": "v" * 40}
    })
    (production / "settings.json").write_text(original, encoding="utf-8")
    monkeypatch.setenv("LOCALAPPDATA", str(local))
    monkeypatch.setenv("MISSION_TOOLKIT_TEST_DATA_DIR", selected)
    # All inherited supervisor inputs appear production-ready. Explicitly
    # empty test-data-dir must still block both readiness and run dispatch.
    fake_headless = _headless(tmp_path)
    _shell(monkeypatch, production, fake_headless)
    assert settings.sandbox_operator_check()["isolated"] is True
    assert settings.sandbox_operator_check()["ok"] is False
    assert settings.load()["account"] == ""
    assert settings.load()["charids"] == []
    pre = preflight("moghancement", "MOG-09")
    assert next(x for x in pre["checks"] if x["id"] == "sandbox_isolation")["ok"] is False
    assert pre["ready_for_operator_review"] is False
    assert settings.status()["ready_to_run"] is False
    with pytest.raises(PermissionError):
        authorize_operator("p" * 40)
    with mock.patch("workbench.server_admin.feature_testing.execution_cli.subprocess.run") as run:
        with pytest.raises(ValueError, match="sandbox_isolation"):
            execute_mog09(account="synthetic_account", charid=17,
                          out_dir=production / "artifacts" / "unwanted",
                          supervisor="http://127.0.0.1:8420", approved=True)
        run.assert_not_called()
    assert settings.apply_to_environ({"enabled": True}) == []
    assert not (production / "artifacts").exists()
    with pytest.raises(ValueError, match="safe for writes"):
        settings.set_enabled(True)
    assert (production / "settings.json").read_text(encoding="utf-8") == original


@pytest.mark.parametrize("prefix,suffix", [
    (" ", ""), ("", " "), ("  ", "  "), ("\t", "\t"),
])
def test_padded_absolute_sandbox_path_fails_before_any_settings_io(
        isolated, monkeypatch, tmp_path, prefix, suffix):
    # Agent A's second P0 finding: validation used .strip(), but data_dir()
    # used the raw env string. Reject both before file reads and writes.
    # Use a complete, inherited, synthetic production-like environment so
    # legacy preflight would otherwise be ready.
    root = _headless(tmp_path)
    prod = tmp_path / "production-localappdata" / "MissionToolkit" / "test_execution"
    prod.mkdir(parents=True, exist_ok=True)
    sentinel = prod / "settings.json"
    original = json.dumps({
        "enabled": True, "account": "synthetic-production-account",
        "charids": [17], "headless_root": str(root),
        "tokens": {"operator": "p" * 40, "supervisor": "v" * 40},
    })
    sentinel.write_text(original, encoding="utf-8")
    _shell(monkeypatch, isolated, root)
    monkeypatch.setenv("MISSION_TOOLKIT_TEST_DATA_DIR",
                       prefix + str(isolated) + suffix)
    scope, selected = settings._sandbox_directory_check()
    assert scope["isolated"] is True and scope["ok"] is False
    assert selected is None
    assert "whitespace" in scope["reason"]
    assert settings.load()["charids"] == []
    assert settings.load()["account"] == ""
    assert settings.sandbox_operator_check()["ok"] is False
    assert settings.sandbox_execution_check()["ok"] is False
    pre = preflight("moghancement", "MOG-09")
    assert pre["ready_for_operator_review"] is False
    assert pre["execution_enabled"] is False
    assert settings.status()["ready_to_run"] is False
    assert settings.status()["charids"] == []
    with pytest.raises(PermissionError):
        authorize_operator("p" * 40)
    # Both setup mutation paths must stop before creating settings.tmp or
    # directory trees corresponding to the unvalidated raw path.
    with pytest.raises(ValueError, match="safe for writes"):
        settings.set_enabled(True)
    with pytest.raises(ValueError, match="safe for writes"):
        settings.update(account="synthetic_test")
    assert settings.apply_to_environ({"enabled": True}) == []
    with mock.patch("workbench.server_admin.feature_testing.execution_cli.subprocess.run") as run:
        with pytest.raises(ValueError, match="sandbox_isolation"):
            execute_mog09(account="synthetic_account", charid=17,
                          out_dir=isolated / "artifacts" / "unwanted",
                          supervisor="http://127.0.0.1:8420", approved=True)
        run.assert_not_called()
    from workbench.server_admin.feature_testing.router import LaunchRequest, launch_test
    req = mock.Mock()
    req.client.host = "127.0.0.1"
    req.base_url = "http://127.0.0.1:8420/"
    req.headers = {"sec-fetch-site": "same-origin",
                   "x-requested-with": "toolkit-ui"}
    with mock.patch("workbench.server_admin.feature_testing.execution_jobs.enqueue") as enqueue:
        with pytest.raises(HTTPException) as rejected:
            launch_test(req, LaunchRequest(account="synthetic_account", charid=17,
                                         supervisor_port=8420, approval=True),
                        x_test_operator_token="p" * 40)
        assert rejected.value.status_code == 403
        enqueue.assert_not_called()
    assert sentinel.read_text(encoding="utf-8") == original
    assert sorted(isolated.iterdir()) == []  # no artifact/settings/temp files
    assert not (prod / "artifacts").exists()


@pytest.mark.parametrize("directory_mode", ["absent", "regular_file"])
def test_nonexistent_or_file_sandbox_root_cannot_create_settings(
        isolated, monkeypatch, tmp_path, directory_mode):
    root = _headless(tmp_path)
    _shell(monkeypatch, isolated, root)
    target = tmp_path / ("not-yet-created" if directory_mode == "absent"
                         else "file-instead-of-sandbox")
    if directory_mode == "regular_file":
        target.write_text("synthetic file sentinel", encoding="utf-8")
    monkeypatch.setenv("MISSION_TOOLKIT_TEST_DATA_DIR", str(target))
    assert settings.sandbox_operator_check()["ok"] is False
    assert settings.sandbox_execution_check()["ok"] is False
    assert settings.load()["enabled"] is False
    assert preflight("moghancement", "MOG-09")["ready_for_operator_review"] is False
    # A new, absolute sandbox directory may be initialized by Setup;
    # until it is explicitly enabled there is no authorization. An existing
    # regular file is never reinterpreted as a sandbox directory.
    if directory_mode == "regular_file":
        with pytest.raises(ValueError, match="safe for writes"):
            settings.set_enabled(True)
        assert target.read_text(encoding="utf-8") == "synthetic file sentinel"
    else:
        assert not target.exists()
        assert settings.apply_to_environ(settings._empty()) == []
        assert not target.exists()


def test_internal_spaces_in_existing_absolute_sandbox_remain_valid(
        isolated, monkeypatch, tmp_path):
    # Reject surrounding whitespace, NOT a legitimate directory name
    # containing spaces. Validated and used path must be identical.
    named = tmp_path / "synthetic sandbox with spaces"
    named.mkdir()
    monkeypatch.setenv("MISSION_TOOLKIT_TEST_DATA_DIR", str(named))
    assert settings._sandbox_directory_check()[1] == settings.data_dir()
    cfg = settings._empty()
    cfg["enabled"] = True
    cfg["tokens"]["operator"] = "d" * 40
    settings._save(cfg)
    settings.apply_to_environ(cfg)
    assert settings.settings_path() == named / "settings.json"
    assert settings.sandbox_operator_check()["ok"] is True
    assert settings.sandbox_execution_check()["ok"] is False
    assert settings.load()["tokens"]["operator"] == "d" * 40
    assert not (isolated / "settings.json").exists()


def test_sandbox_cannot_select_default_production_settings_directory(monkeypatch, tmp_path):
    local = tmp_path / "localappdata"
    monkeypatch.setenv("LOCALAPPDATA", str(local))
    monkeypatch.setenv("MISSION_TOOLKIT_TEST_DATA_DIR", str(local / "MissionToolkit" / "test_execution"))
    state = settings.sandbox_execution_check()
    assert state["isolated"] and not state["ok"]
    with pytest.raises(ValueError, match="safe for writes"):
        settings.set_enabled(True)


def test_builder_template_never_advertises_inherited_preflight_as_launch_authority():
    template = (Path(__file__).resolve().parents[1] / "gui" / "templates" /
                "feature_testing.html").read_text(encoding="utf-8")
    assert "Prerequisites detected — operator approval still required" in template
    assert '{% if not builder_preflight.ready_for_operator_review %}disabled' in template
    assert 'aria-disabled="true"' in template
    assert 'id="ft-run-approval"' in template
