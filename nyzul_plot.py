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
    NAVMESH_FILE,
    NyzulSource,
    classify_root,
    has_legacy_layout,
    has_lsb_layout,
    load_lsb_data,
    navmesh_available,
)
from workbench.devtools.domains.nyzul_lsb_instance import parse_instance_selection
from workbench.runtime.legacy_settings import (
    get_active_server_profile,
    get_dsp_root,
    get_server_profiles,
)

LSB_INSTANCE_FILE = "scripts/zones/Nyzul_Isle/instances/nyzul_isle_investigation.lua"


def _has_nyzul_layout(root: Path) -> bool:
    """Compatibility predicate: any supported native Nyzul layout."""
    return classify_root(Path(root)) is not None


def _markers(root: Path) -> list[str]:
    found = []
    if (root / "scripts/globals/nyzul/floor_generation.lua").is_file():
        found.append("floor_generation.lua")
    if (root / "scripts/globals/nyzul/floor_layouts.lua").is_file():
        found.append("floor_layouts.lua")
    if (root / "scripts/globals/nyzul.lua").is_file():
        found.append("nyzul.lua")
    return found


def _profile_family(profile) -> str:
    return str(getattr(profile, "family", "auto") or "auto").strip().lower()


def _configured_server_source() -> NyzulSource:
    """Resolve the active/profile source without guessing across lineages.

    An explicitly configured active DSP/Topaz/LSB profile must match that family's
    concrete source shape. A partial or contradictory active profile fails closed
    instead of silently selecting another parser. ``auto`` profiles with no Nyzul
    material may fall through to another configured environment.
    """
    diagnostics: list[str] = []
    active = get_active_server_profile()
    seen: set[Path] = set()

    if active is not None and active.enabled:
        root = Path(active.root_path)
        family = _profile_family(active)
        seen.add(root)
        source = classify_root(root, family)
        if source is not None:
            return source
        markers = _markers(root)
        if family in {"dsp", "topaz", "lsb"} or markers:
            marker_text = f"; found {', '.join(markers)}" if markers else ""
            raise ValueError(
                f"Active server profile declares family {family!r}, but {root} does not contain "
                f"the supported {family.upper() if family != 'auto' else 'Nyzul'} source layout{marker_text}. "
                "Nyzul will not fall through to a different lineage parser."
            )
        diagnostics.append(f"active {root}: no Nyzul source markers")

    for profile in get_server_profiles(include_disabled=False):
        root = Path(profile.root_path)
        if root in seen:
            continue
        seen.add(root)
        family = _profile_family(profile)
        source = classify_root(root, family)
        if source is not None:
            return source
        markers = _markers(root)
        diagnostics.append(
            f"{root} [{family}]: unsupported Nyzul layout"
            + (f" ({', '.join(markers)})" if markers else "")
        )

    legacy_dsp = get_dsp_root()
    if legacy_dsp is not None:
        root = Path(legacy_dsp)
        if root not in seen:
            source = classify_root(root, "dsp")
            if source is not None:
                return source
            diagnostics.append(f"{root} [legacy dsp setting]: unsupported Nyzul layout")

    detail = "; ".join(diagnostics) if diagnostics else "no enabled server roots are configured"
    raise ValueError(
        "No configured server environment contains a supported Nyzul source layout. "
        "DSP/Topaz require floor_layouts.lua; modern LSB requires floor_generation.lua plus its "
        f"native local spawn tables. Checked: {detail}"
    )


def _configured_server_root() -> Path:
    return _configured_server_source().root


_legacy_load_data = _canonical.load_data
_legacy_reachability = _canonical.reachability
_legacy_nav_triangles_bytes = _canonical.nav_triangles_bytes


def _lsb_selection_contract(root: Path, data: dict) -> dict:
    """Derive instance-level LSB floor/objective selection semantics from source."""
    instance_path = Path(root) / LSB_INSTANCE_FILE
    if not instance_path.is_file():
        raise ValueError(
            "Configured LSB Nyzul source is missing scripts/zones/Nyzul_Isle/instances/"
            "nyzul_isle_investigation.lua; native selection semantics cannot be verified"
        )
    selection = parse_instance_selection(instance_path.read_text(encoding="utf-8", errors="replace"))

    positive_layouts = sorted(int(k) for k in data.get("entrances", {}) if int(k) > 0)
    if not positive_layouts or positive_layouts != list(range(1, positive_layouts[-1] + 1)):
        raise ValueError("modern LSB Nyzul FloorLayout positive keys are not contiguous from 1")
    subtract = int(selection["non_boss_layout"]["floor_layout_count_subtract"])
    last_layout = positive_layouts[-1] - subtract
    first_layout = int(selection["non_boss_layout"]["first"])
    if last_layout < first_layout or last_layout not in positive_layouts:
        raise ValueError("modern LSB Nyzul non-boss layout range resolves outside FloorLayout")
    selection["non_boss_layout"]["last"] = last_layout
    return selection


def _load_data():
    source = _configured_server_source()
    if source.adapter == "modern-lsb":
        data = load_lsb_data(source.root)
        data.setdefault("generation", {})["selection"] = _lsb_selection_contract(source.root, data)
        data.setdefault("adapter", {}).setdefault("provenance", {})["instance"] = LSB_INSTANCE_FILE
        return data
    has_nav = navmesh_available(source.root)
    data = _legacy_load_data()
    data.setdefault("adapter", {
        "lineage": source.lineage,
        "name": source.adapter,
        "capabilities": {
            "layout_spawn_points": True,
            "lamp_spawn_points": True,
            "floor_entrances": True,
            "objectives": False,
            "numeric_entity_ids": True,
            "navmesh_reachability": has_nav,
        },
        "provenance": {
            "floor_layouts": "scripts/globals/nyzul/floor_layouts.lua",
            "floor_layout": "scripts/globals/nyzul.lua",
            "ids": "scripts/zones/Nyzul_Isle/IDs.lua",
            "navmesh": NAVMESH_FILE if has_nav else None,
        },
    })
    return data


def _reachability():
    """Reachability is optional evidence, not a prerequisite for opening the editor."""
    source = _configured_server_source()
    if not navmesh_available(source.root):
        return {}
    return _legacy_reachability()


def _nav_triangles_bytes(path=None):
    """Return an empty overlay when the selected checkout lacks the navmesh submodule."""
    if path is None:
        source = _configured_server_source()
        if not navmesh_available(source.root):
            return b""
    return _legacy_nav_triangles_bytes(path)


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
_canonical.reachability = _reachability
_canonical.nav_triangles_bytes = _nav_triangles_bytes

sys.modules[__name__] = _canonical
