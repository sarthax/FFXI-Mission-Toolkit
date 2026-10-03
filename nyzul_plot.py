"""Compatibility alias for the packaged Nyzul domain plot backend.

Canonical implementation: ``workbench.devtools.domains.nyzul_plot``.

The GUI imports this compatibility module. Named server environments are now authoritative, but
the current Nyzul parser still expects the DSP/Topaz-era Nyzul data layout. Resolve that layout
from configured server profiles instead of relying only on the deprecated ``dsp_server_path``.
"""
from __future__ import annotations

import sys
from pathlib import Path

from workbench.devtools.domains import nyzul_plot as _canonical
from workbench.runtime.legacy_settings import (
    get_active_server_profile,
    get_dsp_root,
    get_server_profiles,
)


def _has_nyzul_layout(root: Path) -> bool:
    """Return whether *root* contains the file set understood by the current Nyzul parser."""
    return all(
        path.is_file()
        for path in (
            root / "scripts/globals/nyzul/floor_layouts.lua",
            root / "scripts/globals/nyzul.lua",
            root / "scripts/zones/Nyzul_Isle/IDs.lua",
            root / "navmeshes/Nyzul_Isle.nav",
        )
    )


def _configured_server_root() -> Path:
    """Prefer the active compatible environment, then another configured compatible profile."""
    candidates: list[Path] = []
    active = get_active_server_profile()
    if active is not None and active.enabled:
        candidates.append(Path(active.root_path))

    for profile in get_server_profiles(include_disabled=False):
        root = Path(profile.root_path)
        if root not in candidates:
            candidates.append(root)

    legacy_dsp = get_dsp_root()
    if legacy_dsp is not None:
        root = Path(legacy_dsp)
        if root not in candidates:
            candidates.append(root)

    for root in candidates:
        if _has_nyzul_layout(root):
            return root

    raise ValueError(
        "No configured server environment contains the DSP/Topaz-style Nyzul layout files required by this editor"
    )


# Transitional GUI compatibility: the packaged backend still names this private resolver
# ``_dsp_root``. Keep the root module as a true alias while teaching GUI requests about named
# environments. Modern LSB uses a different floor_generation.lua/ID layout and is deliberately
# not treated as equivalent until that parser is implemented.
_canonical._has_nyzul_layout = _has_nyzul_layout
_canonical._configured_server_root = _configured_server_root
_canonical._dsp_root = _configured_server_root

sys.modules[__name__] = _canonical
