from pathlib import Path

from workbench.runtime import settings_store as settings
from workbench.runtime import server_profiles


def _configure_db(tmp_path, monkeypatch):
    db = tmp_path / "settings.db"
    monkeypatch.setattr(settings, "DB_PATH", db)
    con = server_profiles.connect(db)
    return db, con


def test_root_settings_active_server_root_prefers_named_profile(tmp_path, monkeypatch):
    _db, con = _configure_db(tmp_path, monkeypatch)
    try:
        profile = server_profiles.create_profile(
            con,
            name="LSB Test",
            server_root=str(tmp_path / "lsb-test"),
            family="lsb",
            environment="test",
            make_active=True,
        )
    finally:
        con.close()

    assert settings.get_active_server_root() == profile.root_path
    assert settings.get_active_sql_prefix() == "sql_"


def test_root_settings_server_roots_prioritize_active_and_keep_same_family_profiles(tmp_path, monkeypatch):
    _db, con = _configure_db(tmp_path, monkeypatch)
    live = tmp_path / "lsb-live"
    test = tmp_path / "lsb-test"
    topaz = tmp_path / "topaz-reference"
    for path in (live, test, topaz):
        path.mkdir()
    try:
        server_profiles.create_profile(
            con, name="Live", server_root=str(live), family="lsb", environment="live"
        )
        selected = server_profiles.create_profile(
            con, name="Test", server_root=str(test), family="lsb", environment="test", make_active=True
        )
    finally:
        con.close()

    legacy = settings.sqlite3.connect(str(settings.DB_PATH))
    try:
        settings.set_many(legacy, {"topaz_server_path": str(topaz)})
    finally:
        legacy.close()

    roots = settings.get_server_roots()
    assert roots[0] == selected.root_path
    assert roots[:2] == [test, live]
    assert topaz in roots


def test_root_settings_explicit_lineage_getters_remain_legacy_reference_paths(tmp_path, monkeypatch):
    _db, con = _configure_db(tmp_path, monkeypatch)
    topaz = tmp_path / "topaz-reference"
    dsp = tmp_path / "dsp-reference"
    try:
        server_profiles.create_profile(
            con,
            name="LSB Dev",
            server_root=str(tmp_path / "lsb-dev"),
            family="lsb",
            environment="dev",
            make_active=True,
        )
    finally:
        con.close()

    legacy = settings.sqlite3.connect(str(settings.DB_PATH))
    try:
        settings.set_many(
            legacy,
            {"topaz_server_path": str(topaz), "dsp_server_path": str(dsp)},
        )
    finally:
        legacy.close()

    assert settings.get_topaz_root() == topaz
    assert settings.get_dsp_root() == dsp
    assert settings.get_active_server_root() == tmp_path / "lsb-dev"
