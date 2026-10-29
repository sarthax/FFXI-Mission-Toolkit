"""Setup checklist: the checkout step must reflect a checkout the page can actually offer."""
from pathlib import Path

import pytest

from workbench.server_admin.feature_testing import test_execution_settings as setup


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.delenv("MISSION_TOOLKIT_TEST_DATA_DIR", raising=False)
    monkeypatch.delenv("MISSION_TOOLKIT_TEST_HEADLESS_ROOT", raising=False)
    monkeypatch.setattr(setup, "data_dir", lambda: tmp_path / "data")
    root = tmp_path / "xh-ready"
    (root / "bin" / "mcp").mkdir(parents=True)
    (root / "bin" / "mcp" / "XiHeadless.dll").write_bytes(b"x")
    info = {"path": str(root), "name": "xh-ready", "commit": "abc", "has_dll": True, "clean": True}
    monkeypatch.setattr(setup, "detect_headless_roots", lambda: [info])
    return root


def _step(status, step_id):
    return next(s for s in status["steps"] if s["id"] == step_id)


def test_picking_a_detected_built_checkout_turns_both_steps_ok(env):
    before = setup.status()
    assert not _step(before, "checkout")["ok"] and not _step(before, "dll")["ok"]
    setup.update(headless_root=str(env))
    after = setup.status()
    assert _step(after, "checkout")["ok"] and _step(after, "dll")["ok"]


def test_saved_checkout_that_is_no_longer_detected_is_not_reported_as_chosen(env, tmp_path):
    gone = tmp_path / "gone"
    settings = setup.load()
    settings["headless_root"] = str(gone)
    setup._save(settings)
    step = _step(setup.status(), "checkout")
    assert not step["ok"] and "no longer found" in step["fix"]
