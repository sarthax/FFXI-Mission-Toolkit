import os
from unittest import mock

import pytest
from fastapi import HTTPException

from workbench.server_admin.feature_testing import test_execution_settings as s


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("MISSION_TOOLKIT_TEST_DATA_DIR", str(tmp_path / "d"))
    for k in list(os.environ):
        if k.startswith(("MISSION_TOOLKIT_TEST_", "MISSION_TOOLKIT_SUPERVISOR_")) and k != "MISSION_TOOLKIT_TEST_DATA_DIR":
            monkeypatch.delenv(k)
    monkeypatch.setenv("MISSION_TOOLKIT_TEST_SEARCH_ROOTS", str(tmp_path / "hr"))
    yield tmp_path
    s.apply_to_environ(s._empty())


def _checkout(tmp_path):
    runner = tmp_path / "hr" / "x1" / "tools"
    runner.mkdir(parents=True)
    (runner / "observation_runner.py").write_text("")
    return str(tmp_path / "hr" / "x1")


def test_disabled_applies_nothing(env):
    assert s.apply_to_environ() == []
    assert "MISSION_TOOLKIT_TEST_OPERATOR_TOKEN" not in os.environ


def test_enable_generates_distinct_long_tokens_and_env(env):
    st = s.set_enabled(True)
    t = st["tokens"]
    assert len(t["operator"]) >= 32 and len(t["supervisor"]) >= 32 and t["operator"] != t["supervisor"]
    assert os.environ["MISSION_TOOLKIT_TEST_OPERATOR_TOKEN"] == t["operator"]
    assert s.ui_mode_active()
    s.set_enabled(False)
    assert "MISSION_TOOLKIT_TEST_OPERATOR_TOKEN" not in os.environ and not s.ui_mode_active()


def test_shell_env_wins(env, monkeypatch):
    monkeypatch.setenv("MISSION_TOOLKIT_SUPERVISOR_TEST_CHARIDS", "7")
    s.update(charids="21833")
    s.set_enabled(True)
    assert os.environ["MISSION_TOOLKIT_SUPERVISOR_TEST_CHARIDS"] == "7"


def test_headless_root_must_be_detected(env):
    with pytest.raises(ValueError):
        s.update(headless_root=str(env))
    root = _checkout(env)
    assert s.update(headless_root=root)["headless_root"] == root


@pytest.mark.parametrize("bad", ["abc", "0", "-3", "1,x"])
def test_bad_charids_rejected(env, bad):
    with pytest.raises(ValueError):
        s.parse_charids(bad)


def test_status_has_no_secrets_and_blank_password_kept(env):
    s.update(db={"user": "ro", "password": "pw-secret", "name": "dspdb"})
    s.update(db={"password": ""})
    assert s.load()["db"]["password"] == "pw-secret"
    s.set_enabled(True)
    assert "pw-secret" not in repr(s.status()) and s.load()["tokens"]["operator"] not in repr(s.status())


def test_ui_auth_requires_same_origin_headers(env):
    from workbench.server_admin.feature_testing.router import _operator_auth
    s.set_enabled(True)

    # Setup UI auth in an explicit sandbox must not reuse a production
    # operator token until this sandbox has complete, matching credentials.
    class Req:
        client = mock.Mock(host="127.0.0.1")
        base_url = "http://127.0.0.1:8420/"
        def __init__(self, h): self.headers = h
    same_origin = Req({"sec-fetch-site": "same-origin", "x-requested-with": "toolkit-ui"})
    with pytest.raises(HTTPException):
        _operator_auth(same_origin, "")
    root = _checkout(env)
    s.update(headless_root=root, charids="17",
             db={"user": "synthetic_ro", "password": "synthetic_only", "name": "synthetic_db"})
    _operator_auth(same_origin, "")  # authorized local setup, not runner execution
    for h in ({}, {"sec-fetch-site": "cross-site", "x-requested-with": "toolkit-ui"}, {"sec-fetch-site": "same-origin"}):
        with pytest.raises(HTTPException):
            _operator_auth(Req(h), None)


def test_default_data_dir_is_outside_repo(monkeypatch):
    monkeypatch.delenv("MISSION_TOOLKIT_TEST_DATA_DIR", raising=False)
    assert not s.data_dir().resolve().is_relative_to(s._REPO.resolve())
