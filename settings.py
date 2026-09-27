#!/usr/bin/env python3
"""
settings.py -- small key/value config store for the Mission Toolkit GUI.

Single-user local tool, so settings live server-side in the same consolidated DB rather than
per-browser cookies/localStorage -- one source of truth, no flash-of-wrong-theme on load.

`topaz_server_path` and `ffxi_install_path` are consumed by get_topaz_root()/get_ffxi_install()
below -- lookup_entity.py, build_sql_index.py, entity_profile.py, wiki_compile.py, and
build_zone_topdown.py all resolve their real root through these instead of a hardcoded
`C:/topaz`/registry lookup. Each module reads its root at import time, so a change on the
Settings page takes effect on gui_server.py's next restart, not the next request -- same
one-time-resolution model as TOOLS_ROOT itself, not a bug.
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
    "topaz_server_path": "",       # empty = use DEFAULT_TOPAZ_ROOT, see get_topaz_root()
    "dsp_server_path": "",         # empty = DSP cross-reference disabled, see get_dsp_root()
    "zoneplot_server": "topaz",    # "topaz" | "dsp" -- which live DB Zone Plot's level editor targets
    "backport_root": "",           # empty = use the bundled backport-workspace/ scaffold, see get_backport_root()
    "ffxi_install_path": "",       # empty = detect via Windows registry, see get_ffxi_install()
    "item_dat_target": "live",     # "live" | "pivot" -- see item_dat_tools.dat_target()
    "xi_pivot_root": "",           # empty = bundled default, see item_dat_tools.pivot_root()
    # xi-model-viewer's own dev server (npm run dev, ui/vite.config.js) -- default matches its
    # documented default port (5173). Used to build "?npc=<file_id>" deep links (see
    # xi-model-viewer/ui/js/launch.js) from Entity Lookup's own real per-entity model_file_id.
    "xi_model_viewer_url": "http://localhost:5173",
    # Read once at gui_server.py's own startup (uvicorn.run), not per-request -- same
    # one-time-resolution model as topaz_server_path/ffxi_install_path above, so a change here
    # needs a restart (Settings' own Restart button) to take effect, not just a Save.
    "port": "8420",
    # Read fresh on every backup_database_file() call (build_database.py), not cached at import
    # time -- a change here should apply to the very next backup, not need a restart. Each backup
    # is a full copy of ffxi_zone_database.db (~1.3GB in a fully-built install), so this is a real
    # disk-space knob, not just a cosmetic list-length limit.
    "backup_retention_count": "10",
    # Local Open WebUI/Ollama instance (see llm_client.py) -- base URL and default model only.
    # The API key itself deliberately does NOT live here: this settings table lives inside
    # ffxi_zone_database.db, which is routinely stripped/backed-up/rebuilt-from-scratch (see
    # DIST_PACKAGING.md) -- a secret has no business riding along in that file. The key lives in
    # its own gitignored .openwebui_key file instead (llm_client.save_api_key()/has_api_key()).
    "llm_base_url": "http://127.0.0.1:3000",
    "llm_default_model": "qwen2.5-coder:7b",
}


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
            continue  # ignore unknown keys rather than letting a form typo create silent cruft
        con.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
    con.commit()


def get_topaz_root() -> Path:
    """The Topaz server checkout root -- Settings' topaz_server_path if set, else the same
    C:/topaz default every module used to hardcode. Opens its own short-lived connection since
    this is called once at each module's import time, before that module has any connection of
    its own to reuse."""
    con = sqlite3.connect(str(DB_PATH))
    try:
        value = get(con, "topaz_server_path")
    finally:
        con.close()
    return Path(value) if value else Path(DEFAULT_TOPAZ_ROOT)


def get_dsp_root() -> Path | None:
    """The old-DSP server checkout root, if configured -- unlike LandSandBoat (bundled/downloaded
    into this toolkit's own folder), a real DSP checkout is something the user already has
    somewhere on disk, so this is a plain path setting with no default and no auto-download.
    Returns None (not a guessed path) when unset, so build_dsp_index.py can tell "not configured"
    apart from "configured but wrong"."""
    con = sqlite3.connect(str(DB_PATH))
    try:
        value = get(con, "dsp_server_path")
    finally:
        con.close()
    return Path(value) if value else None


def get_backport_root() -> Path:
    """The backport checkout root (holds mission-packages/, dsp-engine-changes/, reports/) --
    Settings' backport_root if set (point this at your own real backport project), else the
    bundled backport-workspace/ scaffold (real folder shape + one small, real, verified example
    package, no project-specific content) so the --all-packages CLI tools work turnkey with zero
    configuration. Unlike get_dsp_root(), this never returns None -- the bundled default always
    exists on disk (shipped with this repo), so there's always something real to point at."""
    con = sqlite3.connect(str(DB_PATH))
    try:
        value = get(con, "backport_root")
    finally:
        con.close()
    return Path(value) if value else DEFAULT_BACKPORT_ROOT


def get_ffxi_install() -> str | None:
    """The FFXI client install directory -- Settings' ffxi_install_path if set, else the same
    Windows-registry autodetection build_zone_topdown.py already used (PlayOnline's InstallFolder
    key, tried under each region's subkey). Returns None if neither resolves to a real directory."""
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
