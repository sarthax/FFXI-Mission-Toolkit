import sqlite3
from pathlib import Path

import pytest

from workbench.runtime.server_profiles import (
    create_profile,
    delete_profile,
    get_active_profile,
    list_profiles,
    seed_legacy_profiles,
    set_active_profile,
    update_profile,
)


def _con():
    con = sqlite3.connect(":memory:")
    con.row_factory = sqlite3.Row
    return con


def test_profiles_can_switch_between_live_test_and_backup():
    con = _con()
    live = create_profile(
        con,
        name="Live",
        server_root="C:/servers/lsb-live",
        family="lsb",
        environment="live",
        make_active=True,
    )
    test = create_profile(
        con,
        name="Test",
        server_root="C:/servers/lsb-test",
        family="lsb",
        environment="test",
    )
    backup = create_profile(
        con,
        name="Backup",
        server_root="D:/backup/dsp",
        family="dsp",
        environment="backup",
    )

    assert get_active_profile(con).profile_id == live.profile_id
    assert set_active_profile(con, test.profile_id).name == "Test"
    assert get_active_profile(con).server_root == "C:/servers/lsb-test"
    assert set_active_profile(con, backup.profile_id).family == "dsp"
    assert get_active_profile(con).environment == "backup"


def test_disabled_profile_cannot_be_selected_and_disabling_active_clears_selection():
    con = _con()
    profile = create_profile(
        con,
        name="Scratch",
        server_root="C:/servers/scratch",
        family="auto",
        environment="dev",
        make_active=True,
    )
    updated = update_profile(
        con,
        profile.profile_id,
        name="Scratch",
        server_root="C:/servers/scratch",
        family="auto",
        environment="dev",
        enabled=False,
    )
    assert updated.enabled is False
    assert get_active_profile(con) is None
    with pytest.raises(ValueError, match="Disabled"):
        set_active_profile(con, profile.profile_id)


def test_profile_names_are_unique_case_insensitively():
    con = _con()
    create_profile(con, name="Live", server_root="C:/one")
    with pytest.raises(sqlite3.IntegrityError):
        create_profile(con, name="live", server_root="C:/two")


def test_legacy_seed_is_idempotent_and_can_select_prior_active_server():
    con = _con()
    candidates = [
        ("Topaz", Path("C:/topaz"), "topaz"),
        ("DSP", Path("D:/dsp"), "dsp"),
    ]
    first = seed_legacy_profiles(con, candidates, active_name="DSP")
    second = seed_legacy_profiles(con, candidates, active_name="DSP")

    assert len(first) == 2
    assert len(second) == 2
    assert get_active_profile(con).name == "DSP"


def test_delete_active_profile_clears_selection():
    con = _con()
    profile = create_profile(con, name="Temp", server_root="C:/temp", make_active=True)
    delete_profile(con, profile.profile_id)
    assert get_active_profile(con) is None
    assert list_profiles(con) == []


def test_rejects_unknown_family_and_environment():
    con = _con()
    with pytest.raises(ValueError, match="family"):
        create_profile(con, name="Bad", server_root="C:/bad", family="unknown")
    with pytest.raises(ValueError, match="environment"):
        create_profile(con, name="Bad", server_root="C:/bad", environment="productionish")
