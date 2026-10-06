from __future__ import annotations

import importlib
import sqlite3
from pathlib import Path

from workbench.runtime import legacy_settings, paths, settings_store


def test_root_settings_is_exact_canonical_alias():
    root_settings = importlib.import_module("settings")
    assert root_settings is settings_store


def test_settings_store_uses_canonical_runtime_paths():
    assert settings_store.DB_PATH == paths.DATABASE_PATH
    assert settings_store.TOOLS_ROOT == paths.REPO_ROOT
    assert settings_store.DEFAULT_BACKPORT_ROOT == paths.REPO_ROOT / "backport-workspace"


def test_settings_store_preserves_crud_contract(tmp_path, monkeypatch):
    db_path = tmp_path / "settings.db"
    monkeypatch.setattr(settings_store, "DB_PATH", db_path)

    con = sqlite3.connect(str(db_path))
    try:
        settings_store.init_db(con)
        assert settings_store.get(con, "theme") == "light"
        settings_store.set_many(con, {"theme": "dark", "not_a_setting": "ignored"})
        assert settings_store.get(con, "theme") == "dark"
        assert settings_store.get(con, "not_a_setting") == ""
    finally:
        con.close()


def test_legacy_settings_bridge_targets_packaged_store():
    assert legacy_settings._module() is settings_store
    source = Path(legacy_settings.__file__).read_text(encoding="utf-8")
    assert "importlib.util" not in source
    assert 'REPO_ROOT / "settings.py"' not in source
