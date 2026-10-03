"""Active-environment adapter for the mature Zone Plot backend.

The underlying Zone Plot implementation still accepts explicit ``topaz``/``dsp`` selectors for
legacy callers and comparison workflows.  Generic GUI/admin callers should import this module
instead: with no explicit server argument it resolves the named active server profile introduced
by the Server Environments work.

Importing this adapter patches the mature module's runtime globals in-place so existing Zone Plot
functions (``zone_data``, ``zone_list``, ``_db``, nav helpers, etc.) all resolve the same active
profile without duplicating the backend implementation.
"""
from __future__ import annotations

import sys

from workbench.devtools.spatial import zone_plot as _impl
from workbench.runtime import legacy_settings

_LEGACY_SERVER_ROOT = _impl._server_root
_LEGACY_SET_SERVER = _impl.set_server


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


def _server_root(server=None):
    profile = _profile_from_selector(server)
    if profile is not None:
        return profile.root_path

    if server is None or server == "" or server == "active":
        return legacy_settings.get_active_server_root()

    family = str(server).strip().lower()
    if family in ("topaz", "dsp"):
        return _LEGACY_SERVER_ROOT(family)
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
        _LEGACY_SET_SERVER(family)
        return None
    raise ValueError("No enabled LSB server environment is configured")


# Patch the mature implementation's runtime globals so all of its existing functions use the
# active-profile resolver when invoked through this adapter (and by later imports in this process).
_impl._server_root = _server_root
_impl.get_server = get_server
_impl.set_server = set_server
_impl.get_environment = get_environment
_impl.get_environment_key = get_environment_key

# Make this module a true compatibility alias to the patched mature implementation.
sys.modules[__name__] = _impl
