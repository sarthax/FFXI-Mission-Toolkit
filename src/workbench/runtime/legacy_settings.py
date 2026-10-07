"""Compatibility accessors for historical Mission Toolkit settings.

The canonical key/value store now lives in :mod:`workbench.runtime.settings_store`. Package code
should prefer named server/environment profiles and specific runtime services; these helpers retain
the legacy Topaz/DSP settings contract for old callers and bootstrap fallback behavior.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from types import ModuleType

from workbench.runtime import settings_store


def _module() -> ModuleType:
    """Return the canonical settings module while preserving the legacy monkeypatch seam."""
    return settings_store


def _configured_legacy_profile_candidates():
    module = _module()
    con = sqlite3.connect(str(module.DB_PATH))
    try:
        topaz = module.get(con, "topaz_server_path")
        dsp = module.get(con, "dsp_server_path")
        active = module.get(con, "zoneplot_server")
    finally:
        con.close()
    candidates = []
    if topaz:
        candidates.append(("Topaz", topaz, "topaz"))
    if dsp:
        candidates.append(("DSP", dsp, "dsp"))
    active_name = "DSP" if active == "dsp" else "Topaz"
    return candidates, active_name


def ensure_server_profiles_seeded():
    from workbench.runtime import server_profiles

    con = server_profiles.connect()
    try:
        profiles = server_profiles.list_profiles(con)
        if not profiles:
            candidates, active_name = _configured_legacy_profile_candidates()
            if candidates:
                profiles = server_profiles.seed_legacy_profiles(con, candidates, active_name=active_name)
        return profiles
    finally:
        con.close()


def get_server_profiles(*, include_disabled: bool = True):
    from workbench.runtime import server_profiles

    ensure_server_profiles_seeded()
    con = server_profiles.connect()
    try:
        return server_profiles.list_profiles(con, include_disabled=include_disabled)
    finally:
        con.close()


def get_active_server_profile():
    from workbench.runtime import server_profiles

    ensure_server_profiles_seeded()
    con = server_profiles.connect()
    try:
        return server_profiles.get_active_profile(con)
    finally:
        con.close()


def set_active_server_profile(profile_id: int | None):
    from workbench.runtime import server_profiles

    ensure_server_profiles_seeded()
    con = server_profiles.connect()
    try:
        return server_profiles.set_active_profile(con, profile_id)
    finally:
        con.close()


def get_active_server_root():
    profile = get_active_server_profile()
    if profile is not None:
        return profile.root_path
    return _module().get_active_server_root()


def get_active_server_identity() -> dict:
    profile = get_active_server_profile()
    if profile is not None:
        return {
            "profile_id": profile.profile_id,
            "name": profile.name,
            "environment": profile.environment,
            "family": profile.family,
            "server_root": str(profile.root_path),
            "enabled": profile.enabled,
            "is_active": True,
            "legacy": False,
        }

    root = _module().get_active_server_root()
    family = get_zoneplot_server()
    return {
        "profile_id": None,
        "name": family.upper(),
        "environment": "legacy",
        "family": family,
        "server_root": str(root),
        "enabled": True,
        "is_active": True,
        "legacy": True,
    }


def get_active_sql_prefix():
    profile = get_active_server_profile()
    if profile is not None:
        if profile.family in ("topaz", "dsp"):
            return f"{profile.family}_"
        if profile.family == "lsb":
            return "sql_"
    return _module().get_active_sql_prefix()


def get_server_roots(*, include_disabled: bool = False) -> list[Path]:
    roots: list[Path] = []
    seen: set[str] = set()

    active = get_active_server_profile()
    profiles = get_server_profiles(include_disabled=include_disabled)
    ordered = ([active] if active is not None else []) + [
        profile for profile in profiles if active is None or profile.profile_id != active.profile_id
    ]
    for profile in ordered:
        if profile is None or (not include_disabled and not profile.enabled):
            continue
        root = profile.root_path
        key = str(root).casefold()
        if key not in seen and root.is_dir():
            roots.append(root)
            seen.add(key)

    for root in (get_topaz_root(), get_dsp_root()):
        if root is None:
            continue
        root = Path(root)
        key = str(root).casefold()
        if key not in seen and root.is_dir():
            roots.append(root)
            seen.add(key)
    return roots


def get_topaz_root():
    return _module().get_topaz_root()


def get_dsp_root():
    return _module().get_dsp_root()


def get_ffxi_install():
    return _module().get_ffxi_install()


def get_backport_root():
    return _module().get_backport_root()


def get_zoneplot_server() -> str:
    profile = get_active_server_profile()
    if profile is not None and profile.family in ("topaz", "dsp"):
        return profile.family
    module = _module()
    con = sqlite3.connect(str(module.DB_PATH))
    try:
        value = module.get(con, "zoneplot_server")
    finally:
        con.close()
    return value if value in ("topaz", "dsp") else "topaz"


def set_zoneplot_server(server: str) -> None:
    if server not in ("topaz", "dsp"):
        raise ValueError('server must be "topaz" or "dsp"')
    module = _module()
    con = sqlite3.connect(str(module.DB_PATH))
    try:
        module.set_many(con, {"zoneplot_server": server})
    finally:
        con.close()
