from __future__ import annotations

import sqlite3

from workbench.runtime import legacy_settings


class _FakeSettings:
    def __init__(self, db_path):
        self.DB_PATH = db_path

    def get(self, con, key):
        con.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)")
        row = con.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        return row[0] if row else "topaz"

    def set_many(self, con, values):
        con.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)")
        for key, value in values.items():
            con.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
        con.commit()


def test_zoneplot_server_bridge_reads_and_writes_existing_store(tmp_path, monkeypatch):
    fake = _FakeSettings(tmp_path / "settings.db")
    monkeypatch.setattr(legacy_settings, "_module", lambda: fake)

    assert legacy_settings.get_zoneplot_server() == "topaz"
    legacy_settings.set_zoneplot_server("dsp")
    assert legacy_settings.get_zoneplot_server() == "dsp"


def test_zoneplot_server_bridge_preserves_topaz_fallback(tmp_path, monkeypatch):
    fake = _FakeSettings(tmp_path / "settings.db")
    monkeypatch.setattr(legacy_settings, "_module", lambda: fake)

    con = sqlite3.connect(str(fake.DB_PATH))
    fake.set_many(con, {"zoneplot_server": "unexpected"})
    con.close()

    assert legacy_settings.get_zoneplot_server() == "topaz"


def test_zoneplot_server_bridge_rejects_invalid_values(tmp_path, monkeypatch):
    fake = _FakeSettings(tmp_path / "settings.db")
    monkeypatch.setattr(legacy_settings, "_module", lambda: fake)

    try:
        legacy_settings.set_zoneplot_server("lsb")
    except ValueError as exc:
        assert 'server must be "topaz" or "dsp"' in str(exc)
    else:
        raise AssertionError("invalid Zone Plot server must be rejected")
