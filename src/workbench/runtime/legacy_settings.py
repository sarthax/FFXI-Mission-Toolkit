"""Transitional package-safe access to the legacy root ``settings.py`` module.

This bridge exists only while settings/configuration is being moved into the src layout.
Package code should import the specific functions it needs from here instead of relying on the
repository root being on ``sys.path``.

Named server/environment profiles are now the canonical administered-server context. Legacy
Topaz/DSP path settings remain available as lineage-specific references and as a compatibility
fallback for installs that have not created named profiles yet.
"""
from __future__ import annotations

import importlib.util
import sqlite3
from functools import lru_cache
from pathlib import Path
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


def _configured_legacy_profile_candidates():
    """Return explicit legacy server paths without inventing default/fallback profiles."""
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
    """Import the old single-path settings once when no named profiles exist yet."""
    from workbench.runtime import server_profiles

    con = server_profiles.connect()
    try:
        profiles = server_profiles.list_profiles(con)
        if not profiles:
            candidates, active_name = _configured_legacy_profile_candidates()
            if candidates:
                profiles = server_profiles.seed_legacy_profiles(
                    con,
                    candidates,
                    active_name=active_name,
                )
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
    """Return the root of the currently administered server environment.

    A named active profile wins. Installs that have not migrated to profiles retain the historical
    ``settings.py``/``zoneplot_server`` behavior as a compatibility fallback.
    """
    profile = get_active_server_profile()
    if profile is not None:
        return profile.root_path
    return _module().get_active_server_root()


def get_active_server_identity() -> dict:
    """Public, secret-free identity for the current administered environment."""
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
    """Return the indexed SQL table prefix corresponding to the active environment lineage."""
    profile = get_active_server_profile()
    if profile is not None:
        if profile.family in ("topaz", "dsp"):
            return f"{profile.family}_"
        if profile.family == "lsb":
            return "sql_"
        # ``auto`` cannot safely choose a lineage-specific index without detection evidence.
        # Preserve the legacy selector until that profile has a concrete detected family.
    return _module().get_active_sql_prefix()


def get_server_roots(*, include_disabled: bool = False) -> list[Path]:
    """Return configured administered roots, active profile first, without losing legacy roots."""
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

    # Compatibility/reference paths can still be useful to tools that intentionally inspect more
    # than the active environment. Do not let them outrank the named active profile.
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
    """Lineage-specific Topaz reference root; not the generic active-environment accessor."""
    return _module().get_topaz_root()


def get_dsp_root():
    """Lineage-specific DSP reference root; not the generic active-environment accessor."""
    return _module().get_dsp_root()


def get_ffxi_install():
    return _module().get_ffxi_install()


def get_backport_root():
    return _module().get_backport_root()


def get_zoneplot_server() -> str:
    """Return the old Topaz/DSP selector for compatibility-only callers.

    New generic server tools should use ``get_active_server_profile`` / ``get_active_server_root``.
    A named Topaz/DSP profile is reflected here so older labels remain coherent during migration.
    LSB/auto profiles cannot be represented by this two-value legacy setting and therefore fall
    through to its persisted compatibility value.
    """
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
    """Persist the deprecated two-lineage Zone Plot selector for legacy callers only."""
    if server not in ("topaz", "dsp"):
        raise ValueError('server must be "topaz" or "dsp"')
    module = _module()
    con = sqlite3.connect(str(module.DB_PATH))
    try:
        module.set_many(con, {"zoneplot_server": server})
    finally:
        con.close()
