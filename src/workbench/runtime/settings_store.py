"""Canonical key/value configuration store for the Mission Toolkit.

Single-user local tool, so settings live server-side in the consolidated toolkit database rather
than per-browser cookies/localStorage. Named Server Environments are authoritative for generic
live/admin tooling; historical Topaz/DSP paths remain bootstrap/fallback and lineage-reference
settings.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

from workbench.runtime.paths import DATABASE_PATH, REPO_ROOT

try:
    import winreg
except ImportError:  # Non-Windows CI/research environments cannot access the Windows registry.
    winreg = None

TOOLS_ROOT = REPO_ROOT
DB_PATH = DATABASE_PATH

DEFAULT_TOPAZ_ROOT = "C:/topaz"
DEFAULT_BACKPORT_ROOT = REPO_ROOT / "backport-workspace"

DEFAULTS = {
    "theme": "light",
    "shell_brand_enabled": "1",
    "shell_brand_text": "ValhallaXI",
    "shell_brand_icon": "/static/valhalla_logo.png",
    "topaz_server_path": "",
    "dsp_server_path": "",
    "zoneplot_server": "topaz",
    "backport_root": "",
    "ffxi_install_path": "",
    "item_dat_target": "live",
    "xi_pivot_root": "",
    "xi_model_viewer_url": "http://localhost:5173",
    "port": "8420",
    "backup_retention_count": "10",
    "llm_base_url": "http://127.0.0.1:3000",
    "llm_default_model": "qwen2.5-coder:7b",
    "ah_legacy_test_writes": "0",
    "ah_dsp_myisam_test_writes": "0",
    "ah_preview_ttl_seconds": "300",
    "live_client_source": "disabled",
    "live_client_feed_file": "",
    "live_client_feed_client": "",
    "live_client_replay_file": "",
    "live_client_replay_client": "",
    "live_client_auto_connect": "0",
}

AH_FLAGS = {
    "ah_legacy_test_writes": "FFXI_MISSION_TOOLKIT_AH_LEGACY_TEST_WRITES",
    "ah_dsp_myisam_test_writes": "FFXI_MISSION_TOOLKIT_AH_DSP_MYISAM_TEST_WRITES",
    "ah_preview_ttl_seconds": "FFXI_MISSION_TOOLKIT_AH_PREVIEW_TTL_SECONDS",
}


def get_ah_flag(key: str) -> str:
    """Effective value of an AH setting: environment variable if set, else stored setting."""
    import os

    env = os.environ.get(AH_FLAGS[key])
    if env is not None and str(env).strip() != "":
        return str(env).strip()
    try:
        con = sqlite3.connect(DB_PATH)
        try:
            row = con.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        finally:
            con.close()
        if row and row[0] is not None:
            return str(row[0]).strip()
    except sqlite3.Error:
        pass
    return DEFAULTS[key]


def ah_flag_source(key: str) -> str:
    import os

    return "environment variable" if str(os.environ.get(AH_FLAGS[key], "")).strip() else "Settings page"


def init_db(con: sqlite3.Connection):
    con.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)
    con.commit()


def get_all(con: sqlite3.Connection) -> dict:
    init_db(con)
    stored = dict(con.execute("SELECT key, value FROM settings").fetchall())
    return {**DEFAULTS, **stored}


def get(con: sqlite3.Connection, key: str) -> str:
    return get_all(con).get(key, "")


def set_many(con: sqlite3.Connection, values: dict):
    init_db(con)
    for key, value in values.items():
        if key not in DEFAULTS:
            continue
        con.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
    con.commit()


def _active_profile():
    """Best-effort named active profile for compatibility callers."""
    try:
        from workbench.runtime import server_profiles

        con = server_profiles.connect(DB_PATH)
        try:
            return server_profiles.get_active_profile(con)
        finally:
            con.close()
    except (ImportError, ModuleNotFoundError, sqlite3.Error):
        return None


def _named_profiles():
    try:
        from workbench.runtime import server_profiles

        con = server_profiles.connect(DB_PATH)
        try:
            return server_profiles.list_profiles(con, include_disabled=False)
        finally:
            con.close()
    except (ImportError, ModuleNotFoundError, sqlite3.Error):
        return []


def get_topaz_root() -> Path:
    con = sqlite3.connect(str(DB_PATH))
    try:
        value = get(con, "topaz_server_path")
    finally:
        con.close()
    return Path(value) if value else Path(DEFAULT_TOPAZ_ROOT)


def get_dsp_root() -> Path | None:
    con = sqlite3.connect(str(DB_PATH))
    try:
        value = get(con, "dsp_server_path")
    finally:
        con.close()
    return Path(value) if value else None


def get_server_roots() -> list[Path]:
    out = []
    seen = set()

    def add(root):
        if root is None:
            return
        path = Path(root).expanduser()
        key = str(path).replace("\\", "/").casefold()
        if key in seen:
            return
        seen.add(key)
        if path.is_dir():
            out.append(path)

    active = _active_profile()
    if active is not None:
        add(active.root_path)
    for profile in _named_profiles():
        if active is not None and profile.profile_id == active.profile_id:
            continue
        add(profile.root_path)

    con = sqlite3.connect(str(DB_PATH))
    try:
        legacy_active = get(con, "zoneplot_server")
    finally:
        con.close()
    legacy = {"topaz": get_topaz_root(), "dsp": get_dsp_root()}
    order = ["dsp", "topaz"] if legacy_active == "dsp" else ["topaz", "dsp"]
    for family in order:
        add(legacy[family])
    return out


def get_active_server_root() -> Path:
    active = _active_profile()
    if active is not None:
        return active.root_path
    roots = get_server_roots()
    return roots[0] if roots else get_topaz_root()


def get_backport_root() -> Path:
    con = sqlite3.connect(str(DB_PATH))
    try:
        value = get(con, "backport_root")
    finally:
        con.close()
    return Path(value) if value else DEFAULT_BACKPORT_ROOT


def get_ffxi_install() -> str | None:
    con = sqlite3.connect(str(DB_PATH))
    try:
        value = get(con, "ffxi_install_path")
    finally:
        con.close()
    if value and Path(value).exists():
        return value

    if winreg is None:
        return None

    for sub in (
        r"SOFTWARE\PlayOnlineUS\InstallFolder",
        r"SOFTWARE\PlayOnline\InstallFolder",
        r"SOFTWARE\PlayOnlineEU\InstallFolder",
    ):
        try:
            key = winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                sub,
                0,
                winreg.KEY_READ | winreg.KEY_WOW64_32KEY,
            )
            val, _ = winreg.QueryValueEx(key, "0001")
            if Path(val).exists():
                return val
        except (FileNotFoundError, OSError):
            continue
    return None


def get_active_sql_prefix() -> str:
    active = _active_profile()
    if active is not None:
        if active.family == "lsb":
            return "sql_"
        if active.family in ("topaz", "dsp"):
            return f"{active.family}_"

    try:
        con = sqlite3.connect(str(DB_PATH))
        try:
            value = get(con, "zoneplot_server")
        finally:
            con.close()
    except Exception:
        value = None
    return "dsp_" if value == "dsp" else "topaz_"
