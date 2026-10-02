"""Transitional package-safe access to the legacy root ``settings.py`` module.

This bridge exists only while settings/configuration is being moved into the src layout.
Package code should import the specific functions it needs from here instead of relying on the
repository root being on ``sys.path``.
"""
from __future__ import annotations

import importlib.util
import sqlite3
from functools import lru_cache
from types import ModuleType

from workbench.runtime.paths import REPO_ROOT


@lru_cache(maxsize=1)
def _module() -> ModuleType:
    path = REPO_ROOT / "settings.py"
    spec = importlib.util.spec_from_file_location("_mission_toolkit_legacy_settings", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load legacy settings module from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def get_active_server_root():
    return _module().get_active_server_root()


def get_active_sql_prefix():
    return _module().get_active_sql_prefix()


def get_topaz_root():
    return _module().get_topaz_root()


def get_dsp_root():
    return _module().get_dsp_root()


def get_ffxi_install():
    return _module().get_ffxi_install()


def get_zoneplot_server() -> str:
    """Return the persisted Zone Plot server target using legacy settings semantics."""
    module = _module()
    con = sqlite3.connect(str(module.DB_PATH))
    try:
        value = module.get(con, "zoneplot_server")
    finally:
        con.close()
    return value if value in ("topaz", "dsp") else "topaz"


def set_zoneplot_server(server: str) -> None:
    """Persist the Zone Plot server target without exposing generic settings mutation."""
    if server not in ("topaz", "dsp"):
        raise ValueError('server must be "topaz" or "dsp"')
    module = _module()
    con = sqlite3.connect(str(module.DB_PATH))
    try:
        module.set_many(con, {"zoneplot_server": server})
    finally:
        con.close()
