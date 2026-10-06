#!/usr/bin/env python3
"""
settings.py -- small key/value config store for the Mission Toolkit GUI.

Single-user local tool, so settings live server-side in the same consolidated DB rather than
per-browser cookies/localStorage -- one source of truth, no flash-of-wrong-theme on load.

Named Server Environments are now authoritative for generic live/admin tooling.  The historical
Topaz/DSP path settings remain supported as bootstrap/fallback inputs and for lineage-specific
reference/index workflows.  This root module is itself a compatibility surface, so its generic
``get_active_*`` helpers also honor the named profile store when the packaged runtime is available.
"""
import sqlite3
try:
    import winreg
except ImportError:  # Non-Windows CI/research environments cannot access the Windows registry.
    winreg = None
from pathlib import Path

TOOLS_ROOT = Path(__file__).parent
DB_PATH = TOOLS_ROOT / "ffxi_zone_database.db"

DEFAULT_TOPAZ_ROOT = "C:/topaz"
# Bundled turnkey scaffold (backport-workspace/README.md) -- real folder shape + one small, real,
# already-verified example package, but none of a real backport project's own content. A user
# pointing backport_root at their own real checkout overrides this via the setting below.
DEFAULT_BACKPORT_ROOT = TOOLS_ROOT / "backport-workspace"

DEFAULTS = {
    "theme": "light",              # light | dark
    "shell_brand_enabled": "1",     # 1 = show shell brand, 0 = hide it
    "shell_brand_text": "ValhallaXI",
    "shell_brand_icon": "/static/valhalla_logo.png",
    "topaz_server_path": "",       # legacy bootstrap/fallback + Topaz-specific reference root
    "dsp_server_path": "",         # legacy bootstrap/fallback + DSP-specific reference root
    "zoneplot_server": "topaz",    # legacy topaz|dsp selector retained for compatibility only
    "backport_root": "",           # empty = use bundled backport-workspace scaffold
    "ffxi_install_path": "",       # empty = detect via Windows registry
    "item_dat_target": "live",     # "live" | "pivot" -- see item_dat_tools.dat_target()
    "xi_pivot_root": "",           # empty = bundled default, see item_dat_tools.pivot_root()
    "xi_model_viewer_url": "http://localhost:5173",
    "port": "8420",
    "backup_retention_count": "10",
    "llm_base_url": "http://127.0.0.1:3000",
    "llm_default_model": "qwen2.5-coder:7b",
    # Auction House write gates. Each can also be forced by an environment variable of the same
    # purpose (the variable wins when set); see AH_FLAGS and get_ah_flag().
    "ah_legacy_test_writes": "0",       # 1 = allow guarded DSP/Topaz Test-environment AH writes
    "ah_dsp_myisam_test_writes": "0",   # 1 = allow DSP MyISAM listing/purchase test writes
    "ah_preview_ttl_seconds": "300",    # how long an AH preview stays valid (30-86400)
}

# setting key -> environment variable that overrides it
AH_FLAGS = {
    "ah_legacy_test_writes": "FFXI_MISSION_TOOLKIT_AH_LEGACY_TEST_WRITES",
    "ah_dsp_myisam_test_writes": "FFXI_MISSION_TOOLKIT_AH_DSP_MYISAM_TEST_WRITES",
    "ah_preview_ttl_seconds": "FFXI_MISSION_TOOLKIT_AH_PREVIEW_TTL_SECONDS",
}


def get_ah_flag(key: str) -> str:
    """Effective value of an AH setting: the environment variable if set, else the stored setting."""
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
    """Best-effort named active profile for root-level compatibility callers.

    Keep this import lazy so the legacy root settings module still works in narrow bootstrap/test
    contexts where the packaged ``workbench`` namespace is not importable yet.
    """
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
    """Legacy/reference Topaz checkout root; named active environments do not replace this.

    Generic live/admin code should call :func:`get_active_server_root` instead.
    """
    con = sqlite3.connect(str(DB_PATH))
    try:
        value = get(con, "topaz_server_path")
    finally:
        con.close()
    return Path(value) if value else Path(DEFAULT_TOPAZ_ROOT)


def get_dsp_root() -> Path | None:
    """Legacy/reference DSP checkout root, or ``None`` when not configured."""
    con = sqlite3.connect(str(DB_PATH))
    try:
        value = get(con, "dsp_server_path")
    finally:
        con.close()
    return Path(value) if value else None


def get_server_roots() -> list[Path]:
    """Configured server roots, with the named active environment first.

    Named enabled profiles are authoritative and may include multiple environments of the same
    family (for example LSB Live and LSB Test).  Legacy Topaz/DSP roots are appended only as
    compatibility/reference roots and are de-duplicated by normalized path.
    """
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

    # Compatibility/reference roots are intentionally lower priority than named environments.
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
    """Root of the currently administered named environment, with legacy fallback."""
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

    for sub in (r"SOFTWARE\PlayOnlineUS\InstallFolder", r"SOFTWARE\PlayOnline\InstallFolder",
                r"SOFTWARE\PlayOnlineEU\InstallFolder"):
        try:
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, sub, 0,
                                  winreg.KEY_READ | winreg.KEY_WOW64_32KEY)
            val, _ = winreg.QueryValueEx(key, "0001")
            if Path(val).exists():
                return val
        except (FileNotFoundError, OSError):
            continue
    return None


def get_active_sql_prefix() -> str:
    """Parsed SQL/Lua table prefix for the active administered environment.

    LSB uses the historical ``sql_`` tables; Topaz/DSP use their lineage-specific prefixes.
    ``auto`` profiles retain legacy prefix behavior until their family is explicitly classified.
    """
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
