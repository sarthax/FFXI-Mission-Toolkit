"""Compatibility alias for the packaged Nyzul domain plot backend.

Canonical implementation: ``workbench.devtools.domains.nyzul_plot``.

Named server environments are authoritative. DSP/Topaz retain the historical
parser while modern LandSandBoat is handled by a dedicated native adapter.
"""
from __future__ import annotations

import sys
from pathlib import Path

from workbench.devtools.domains import nyzul_plot as _canonical
from workbench.devtools.domains.nyzul_adapters import (
    NyzulSource,
    classify_root,
    has_legacy_layout,
    has_lsb_layout,
    load_lsb_data,
)
from workbench.runtime.legacy_settings import (
    get_active_server_profile,
    get_dsp_root,
    get_server_profiles,
)


def _has_nyzul_layout(root: Path) -> bool:
    """Compatibility predicate: any supported native Nyzul layout."""
    return classify_root(Path(root)) is not None


def _candidate_roots() -> list[Path]:
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
    return candidates


def _configured_server_source() -> NyzulSource:
    """Prefer the active supported environment, then another configured profile.

    Detection is by concrete source shape rather than a guessed parser. Unsupported
    or partial custom layouts fail closed with a diagnostic listing what was seen.
    """
    candidates = _candidate_roots()
    diagnostics: list[str] = []
    for root in candidates:
        source = classify_root(root)
        if source is not None:
            return source
        markers = []
        if (root / "scripts/globals/nyzul/floor_generation.lua").is_file():
            markers.append("floor_generation.lua")
        if (root / "scripts/globals/nyzul/floor_layouts.lua").is_file():
            markers.append("floor_layouts.lua")
        diagnostics.append(f"{root}: unsupported Nyzul layout" + (f" ({', '.join(markers)})" if markers else ""))

    detail = "; ".join(diagnostics) if diagnostics else "no enabled server roots are configured"
    raise ValueError(
        "No configured server environment contains a supported Nyzul source layout. "
        "DSP/Topaz require floor_layouts.lua; modern LSB requires floor_generation.lua plus its "
        f"native local spawn tables. Checked: {detail}"
    )


def _configured_server_root() -> Path:
    return _configured_server_source().root


_legacy_load_data = _canonical.load_data


def _load_data():
    source = _configured_server_source()
    if source.adapter == "modern-lsb":
        return load_lsb_data(source.root)
    data = _legacy_load_data()
    data.setdefault("adapter", {
        "lineage": "legacy",
        "name": "legacy-dsp-topaz",
        "capabilities": {
            "layout_spawn_points": True,
            "lamp_spawn_points": True,
            "floor_entrances": True,
            "objectives": False,
            "numeric_entity_ids": True,
        },
        "provenance": {
            "floor_layouts": "scripts/globals/nyzul/floor_layouts.lua",
            "floor_layout": "scripts/globals/nyzul.lua",
            "ids": "scripts/zones/Nyzul_Isle/IDs.lua",
        },
    })
    return data


# The packaged backend still names the root resolver ``_dsp_root`` because its
# navmesh helpers predate multi-server profiles. Keep that private compatibility
# hook, but the selected root may now be DSP, Topaz, or native modern LSB.
_canonical._has_nyzul_layout = _has_nyzul_layout
_canonical._has_legacy_nyzul_layout = has_legacy_layout
_canonical._has_lsb_nyzul_layout = has_lsb_layout
_canonical._configured_server_source = _configured_server_source
_canonical._configured_server_root = _configured_server_root
_canonical._dsp_root = _configured_server_root
_canonical.load_data = _load_data

sys.modules[__name__] = _canonical
