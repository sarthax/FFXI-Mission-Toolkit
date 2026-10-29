"""Safety and usability regression coverage for the first local test execution slice."""
from pathlib import Path

import pytest

from workbench.server_admin.feature_testing.execution_preflight import preflight
from workbench.server_admin.feature_testing.execution_cli import execute_mog09


def test_preflight_unknown_scenario_fails_closed(monkeypatch):
    monkeypatch.delenv("MISSION_TOOLKIT_TEST_HEADLESS_ROOT", raising=False)
    report = preflight("moghancement", "MOG-01")
    assert report["runner"] is None
    assert report["ready_for_operator_review"] is False
    assert report["execution_enabled"] is False
    assert report["launch_implemented"] is False


def test_preflight_checks_known_runner_and_configuration(monkeypatch, tmp_path):
    root = tmp_path / "headless"
    (root / "tools").mkdir(parents=True)
    (root / "bin" / "mcp").mkdir(parents=True)
    (root / "tools" / "observation_runner.py").write_text("pass", encoding="utf-8")
    (root / "bin" / "mcp" / "XiHeadless.dll").write_bytes(b"demo bytes")
    monkeypatch.setenv("MISSION_TOOLKIT_TEST_HEADLESS_ROOT", str(root))
    monkeypatch.setenv("MISSION_TOOLKIT_TEST_RESULTS_DB", str(tmp_path / "results.sqlite"))
    monkeypatch.setenv("MISSION_TOOLKIT_SUPERVISOR_TEST_CHARIDS", "21836")
    monkeypatch.setenv("MISSION_TOOLKIT_SUPERVISOR_TOKEN", "a" * 64)
    report = preflight("moghancement", "MOG-09")
    assert report["ready_for_operator_review"] is True
    assert report["execution_enabled"] is False
    assert all(c["ok"] for c in report["checks"])
    (root / "tools" / "observation_runner.py").unlink()
    (root / "tools" / "observation_runner.py").symlink_to(tmp_path / "outside.py")
    assert preflight("moghancement", "MOG-09")["ready_for_operator_review"] is False


def test_execution_requires_explicit_approval_without_process_launch(tmp_path):
    with pytest.raises(ValueError, match="approval"):
        execute_mog09(account="xitest07", charid=21836, out_dir=tmp_path / "new",
                      supervisor="http://127.0.0.1:8420", approved=False)


def test_execution_rejects_unapproved_identity_and_remote_urls(monkeypatch, tmp_path):
    monkeypatch.setenv("MISSION_TOOLKIT_SUPERVISOR_TEST_CHARIDS", "21836")
    with pytest.raises(ValueError, match="not approved"):
        execute_mog09(account="xitest07", charid=1, out_dir=tmp_path / "new",
                      supervisor="http://127.0.0.1:8420", approved=True)
    with pytest.raises(ValueError, match="loopback"):
        execute_mog09(account="xitest07", charid=21836, out_dir=tmp_path / "new",
                      supervisor="http://example.com:8420", approved=True)
    with pytest.raises(ValueError, match="account"):
        execute_mog09(account=";rm -rf", charid=21836, out_dir=tmp_path / "new",
                      supervisor="http://127.0.0.1:8420", approved=True)


def test_scenario_page_has_preflight_without_execution_button():
    root = Path(__file__).resolve().parents[1]
    template = (root / "gui/templates/feature_testing_scenario.html").read_text(encoding="utf-8")
    assert "preflight.checks" in template
    assert "preflight.ready_for_operator_review" in template
    assert "Execution from this page is not enabled" in template
