"""Server-environment resolution and live-DB access shared by client, devtools and editors.

Resolves the active named server profile (or legacy topaz/dsp selectors) to a server root and
opens the game database from that root's conf file. Lives in Core so Client code does not have to
import Devtools; ``devtools.spatial.zone_plot`` and ``active_zone_plot`` re-export these.
"""
from __future__ import annotations

import re
from pathlib import Path

from workbench.runtime import legacy_settings
from workbench.runtime.legacy_settings import get_dsp_root, get_topaz_root, get_zoneplot_server, set_zoneplot_server

# Conf filenames to try, in order, under whichever server root is active.
CONF_NAMES = ["conf/map.conf", "conf/map_darkstar.conf"]


def legacy_get_server() -> str:
    """Which server Zone Plot is currently pointed at: ``topaz`` or ``dsp``."""
    return get_zoneplot_server()


def legacy_set_server(server: str):
    if server not in ("topaz", "dsp"):
        raise ValueError('server must be "topaz" or "dsp"')
    if server == "dsp" and get_dsp_root() is None:
        raise ValueError("DSP server path isn't configured yet -- set it on the Settings page first")
    set_zoneplot_server(server)


def legacy_server_root(server=None) -> Path:
    server = server or legacy_get_server()
    if server == "dsp":
        root = get_dsp_root()
        if root is None:
            raise ValueError("DSP server path isn't configured yet -- set it on the Settings page first")
        return root
    return get_topaz_root()


def conf_path(root: Path) -> Path:
    for name in CONF_NAMES:
        p = root / name
        if p.exists():
            return p
    raise FileNotFoundError(f"no mysql conf found under {root} (tried {', '.join(CONF_NAMES)})")


def _profiles():
    return legacy_settings.get_server_profiles(include_disabled=False)


def get_environment():
    """Return the active named profile as a secret-free dict, or ``None`` in legacy mode."""
    profile = legacy_settings.get_active_server_profile()
    return profile.public_dict() if profile is not None else None


def get_environment_key() -> str:
    """Stable cache/display key for the current administered environment."""
    profile = legacy_settings.get_active_server_profile()
    if profile is not None:
        return f"profile:{profile.profile_id}"
    return f"legacy:{legacy_settings.get_zoneplot_server()}"


def get_server() -> str:
    """Compatibility family label for older callers.

    New UI should use :func:`get_environment` / ``profile_id`` rather than this family-only label,
    because multiple profiles may share the same family.
    """
    profile = legacy_settings.get_active_server_profile()
    if profile is not None:
        return profile.family
    return legacy_settings.get_zoneplot_server()


def _profile_from_selector(server):
    if server is None or server == "" or server == "active":
        return legacy_settings.get_active_server_profile()
    if isinstance(server, int):
        wanted = int(server)
    else:
        raw = str(server).strip().lower()
        if raw.startswith("profile:"):
            try:
                wanted = int(raw.split(":", 1)[1])
            except ValueError:
                raise ValueError(f"Invalid server profile selector: {server!r}")
        else:
            return None
    for profile in _profiles():
        if profile.profile_id == wanted:
            return profile
    raise ValueError(f"Unknown or disabled server profile {wanted}")


def server_root(server=None):
    profile = _profile_from_selector(server)
    if profile is not None:
        return profile.root_path

    if server is None or server == "" or server == "active":
        return legacy_settings.get_active_server_root()

    family = str(server).strip().lower()
    if family in ("topaz", "dsp"):
        return legacy_server_root(family)
    if family == "lsb":
        active = legacy_settings.get_active_server_profile()
        if active is not None and active.family == "lsb":
            return active.root_path
        matches = [p for p in _profiles() if p.family == "lsb"]
        if len(matches) == 1:
            return matches[0].root_path
        if not matches:
            raise ValueError("No enabled LSB server environment is configured")
        raise ValueError("Multiple LSB environments are configured; select a named active environment")
    return legacy_settings.get_active_server_root()


def set_server(server):
    """Compatibility selector that prefers named profiles.

    ``profile:<id>`` / integer ids are canonical.  Family selectors remain accepted only when they
    resolve unambiguously; otherwise callers must choose a named environment rather than silently
    switching between Live/Test servers of the same family.
    """
    profile = _profile_from_selector(server)
    if profile is not None:
        legacy_settings.set_active_server_profile(profile.profile_id)
        return profile

    family = str(server).strip().lower()
    if family not in ("lsb", "topaz", "dsp"):
        raise ValueError('server must be a profile id, "profile:<id>", "lsb", "topaz", or "dsp"')

    active = legacy_settings.get_active_server_profile()
    if active is not None and active.family == family:
        return active

    matches = [p for p in _profiles() if p.family == family]
    if len(matches) == 1:
        return legacy_settings.set_active_server_profile(matches[0].profile_id)
    if len(matches) > 1:
        raise ValueError(
            f"Multiple {family.upper()} environments are configured; select the named environment instead"
        )

    if family in ("topaz", "dsp"):
        legacy_set_server(family)
        return None
    raise ValueError("No enabled LSB server environment is configured")




def connect(server=None, resolver=None):
    try:
        import mysql.connector
    except ModuleNotFoundError:  # toolkit venv has no mysql-connector: borrow it from the user site-packages
        import glob, os, sys
        for d in glob.glob(os.path.expandvars(r"%APPDATA%\Python\Python3*\site-packages")):
            if os.path.isdir(os.path.join(d, "mysql")) and d not in sys.path:
                sys.path.append(d)
        import mysql.connector
    root = (resolver or server_root)(server)
    c = conf_path(root).read_text()
    g = lambda k: re.search(k + r":\s*(\S+)", c).group(1)
    return mysql.connector.connect(host=g("mysql_host"), port=int(g("mysql_port")), user=g("mysql_login"),
                                   password=g("mysql_password"), database=g("mysql_database"))


def columns(cu, table):
    cu.execute(f"describe {table}")
    return {r[0] for r in cu.fetchall()}
