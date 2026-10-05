"""Lineage-specific Nyzul source adapters.

The legacy DSP/Topaz parser remains owned by :mod:`nyzul_plot`; this module only
recognizes source layouts and implements the modern LandSandBoat representation.
Modern LSB deliberately keeps runtime-ID expressions as provenance instead of
pretending they are legacy numeric entity IDs.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

NUM = r"(-?\d+(?:\.\d+)?)"
NAVMESH_FILE = "navmeshes/Nyzul_Isle.nav"
LEGACY_SOURCE_FILES = (
    "scripts/globals/nyzul/floor_layouts.lua",
    "scripts/globals/nyzul.lua",
    "scripts/zones/Nyzul_Isle/IDs.lua",
)
LSB_SOURCE_FILES = (
    "scripts/globals/nyzul/floor_generation.lua",
    "scripts/globals/nyzul.lua",
    "scripts/zones/Nyzul_Isle/IDs.lua",
)


@dataclass(frozen=True)
class NyzulSource:
    lineage: str
    adapter: str
    root: Path


def navmesh_available(root: Path) -> bool:
    """Return whether the optional xiNavmeshes checkout is initialized for Nyzul."""
    return (Path(root) / NAVMESH_FILE).is_file()


def has_legacy_layout(root: Path) -> bool:
    root = Path(root)
    return all((root / rel).is_file() for rel in LEGACY_SOURCE_FILES)


def has_lsb_layout(root: Path) -> bool:
    root = Path(root)
    if not all((root / rel).is_file() for rel in LSB_SOURCE_FILES):
        return False
    # Fail closed: floor_generation.lua alone is not enough to identify the
    # current native LSB shape. Require the modern local-table declarations.
    text = (root / LSB_SOURCE_FILES[0]).read_text(encoding="utf-8", errors="replace")
    return bool(
        re.search(r"(?m)^local\s+lampSpawnPoints\s*=", text)
        and re.search(r"(?m)^local\s+layoutSpawnPoints\s*=", text)
    )


def classify_root(root: Path, family: str = "auto") -> NyzulSource | None:
    """Classify *root* using both its configured family and concrete source shape.

    An explicitly configured family never falls through to another lineage parser.
    ``auto`` may identify either native LSB or the historical DSP/Topaz shape.
    """
    root = Path(root)
    family = (family or "auto").strip().lower()
    if family == "lsb":
        return NyzulSource("lsb", "modern-lsb", root) if has_lsb_layout(root) else None
    if family in {"dsp", "topaz"}:
        return NyzulSource(family, f"legacy-{family}", root) if has_legacy_layout(root) else None
    if family != "auto":
        return None
    if has_lsb_layout(root):
        return NyzulSource("lsb", "modern-lsb", root)
    if has_legacy_layout(root):
        return NyzulSource("legacy", "legacy-dsp-topaz", root)
    return None


def _block(text: str, start_pat: str) -> str:
    match = re.search(start_pat, text)
    if not match:
        raise ValueError(f"required Nyzul construct not found: {start_pat}")
    try:
        i = text.index("{", match.end())
    except ValueError as exc:
        raise ValueError(f"Nyzul construct has no table body: {start_pat}") from exc
    depth = 0
    for j in range(i, len(text)):
        depth += text[j] == "{"
        depth -= text[j] == "}"
        if depth == 0:
            return text[i : j + 1]
    raise ValueError(f"unterminated Nyzul table: {start_pat}")


def _indexed_subtables(block: str) -> dict[int, str]:
    out: dict[int, str] = {}
    for match in re.finditer(r"(?m)^\s*\[(\d+)\]\s*=\s*(?:--[^\n]*\n\s*)?\{", block):
        start = match.end() - 1
        depth = 0
        for j in range(start, len(block)):
            depth += block[j] == "{"
            depth -= block[j] == "}"
            if depth == 0:
                out[int(match.group(1))] = block[start : j + 1]
                break
    return out


def _parse_lamp_points(block: str) -> dict[int, list[list[float]]]:
    out: dict[int, list[list[float]]] = {}
    item_re = re.compile(r"\{\s*" + NUM + r"\s*,\s*" + NUM + r"\s*,\s*" + NUM + r"\s*\}")
    for layout, body in _indexed_subtables(block).items():
        out[layout] = [[float(a), float(b), float(c)] for a, b, c in item_re.findall(body)]
    return out


def _parse_layout_points(block: str) -> dict[int, list[list[float]]]:
    out: dict[int, list[list[float]]] = {}
    item_re = re.compile(r"\{\s*x\s*=\s*" + NUM + r"\s*,\s*y\s*=\s*" + NUM + r"\s*,\s*z\s*=\s*" + NUM)
    for layout, body in _indexed_subtables(block).items():
        out[layout] = [[float(a), float(b), float(c)] for a, b, c in item_re.findall(body)]
    return out


def _parse_floor_layout(text: str) -> dict[int, list[float]]:
    block = _block(text, r"(?m)^xi\.nyzul\.FloorLayout\s*=")
    out: dict[int, list[float]] = {}
    for match in re.finditer(
        r"\[\s*(\d+)\s*\]\s*=\s*\{\s*" + NUM + r"\s*,\s*" + NUM + r"\s*,\s*" + NUM + r"\s*\}",
        block,
    ):
        out[int(match.group(1))] = [float(match.group(2)), float(match.group(3)), float(match.group(4))]
    if not out:
        raise ValueError("modern LSB xi.nyzul.FloorLayout contains no deterministic coordinates")
    return out


def _parse_objectives(text: str) -> dict[str, int]:
    try:
        block = _block(text, r"(?m)^xi\.nyzul\.objective\s*=")
    except ValueError:
        return {}
    return {
        key: int(value)
        for key, value in re.findall(r"(?m)^\s*([A-Z][A-Z0-9_]*)\s*=\s*(\d+)\s*,?", block)
    }


def _parse_runtime_id_provenance(ids_text: str) -> dict[str, dict[str, str]]:
    """Preserve modern LSB GetFirstID/GetTableOfIDs expressions without resolving them."""
    out: dict[str, dict[str, str]] = {"mob": {}, "npc": {}}
    for section in ("mob", "npc"):
        try:
            body = _block(ids_text, rf"(?m)^\s*{section}\s*=")
        except ValueError:
            continue
        for key, fn, name in re.findall(
            r"(?m)^\s*([A-Z][A-Z0-9_]*)\s*=\s*(GetFirstID|GetTableOfIDs)\(\s*['\"]([^'\"]+)['\"]\s*\)",
            body,
        ):
            out[section][key] = f"{fn}('{name}')"
    return out


def _parse_range_table(text: str, name: str) -> dict[int, dict[str, str]]:
    """Capture LSB runtime-ID ranges as expressions, never as invented numeric IDs."""
    try:
        block = _block(text, rf"(?m)^local\s+{re.escape(name)}\s*=")
    except ValueError:
        return {}
    out: dict[int, dict[str, str]] = {}
    for match in re.finditer(r"(?m)^\s*\[(\d+)\]\s*=\s*\{\s*([^,{}]+)\s*,\s*([^{}]+?)\s*\}\s*,?\s*(?:--\s*(.*))?$", block):
        out[int(match.group(1))] = {
            "first": match.group(2).strip(),
            "last": match.group(3).strip(),
            "note": (match.group(4) or "").strip(),
        }
    return out


def load_lsb_data(root: Path) -> dict[str, Any]:
    """Normalize deterministic modern-LSB Nyzul data into the editor view model.

    Spatial/layout semantics map directly. Entity IDs do not: current LSB obtains
    them at runtime with GetFirstID/GetTableOfIDs, so legacy numeric collections
    remain empty and the original expressions are exposed under ``lineage``.
    """
    root = Path(root)
    if not has_lsb_layout(root):
        raise ValueError(
            "Configured LSB source is not a recognized modern Nyzul layout; expected "
            "scripts/globals/nyzul/floor_generation.lua with local lampSpawnPoints/layoutSpawnPoints, "
            "scripts/globals/nyzul.lua, and scripts/zones/Nyzul_Isle/IDs.lua"
        )

    floor_path = root / "scripts/globals/nyzul/floor_generation.lua"
    nyzul_path = root / "scripts/globals/nyzul.lua"
    ids_path = root / "scripts/zones/Nyzul_Isle/IDs.lua"
    floor_text = floor_path.read_text(encoding="utf-8", errors="replace")
    nyzul_text = nyzul_path.read_text(encoding="utf-8", errors="replace")
    ids_text = ids_path.read_text(encoding="utf-8", errors="replace")

    lamps = _parse_lamp_points(_block(floor_text, r"(?m)^local\s+lampSpawnPoints\s*="))
    points = _parse_layout_points(_block(floor_text, r"(?m)^local\s+layoutSpawnPoints\s*="))
    entrances = _parse_floor_layout(nyzul_text)
    if not lamps or not points:
        raise ValueError("modern LSB Nyzul spatial tables were recognized but contained no deterministic data")

    has_nav = navmesh_available(root)
    return {
        "lamps": lamps,
        "points": points,
        "entrances": entrances,
        # The legacy editor expects these numeric collections. LSB runtime IDs
        # are intentionally not coerced into them.
        "families": {},
        "leaders": [],
        "groups": [],
        "nm": {"NM_EVEN": [], "NM_ODD": []},
        "bosses": {},
        "adapter": {
            "lineage": "lsb",
            "name": "modern-lsb",
            "capabilities": {
                "layout_spawn_points": True,
                "lamp_spawn_points": True,
                "floor_entrances": True,
                "objectives": True,
                "numeric_entity_ids": False,
                "navmesh_reachability": has_nav,
            },
            "provenance": {
                "floor_generation": str(floor_path.relative_to(root)),
                "floor_layout": str(nyzul_path.relative_to(root)),
                "ids": str(ids_path.relative_to(root)),
                "navmesh": NAVMESH_FILE if has_nav else None,
            },
        },
        "objectives": _parse_objectives(nyzul_text),
        "lineage": {
            "runtime_ids": _parse_runtime_id_provenance(ids_text),
            "enemy_leaders": _parse_range_table(floor_text, "pTableEnemyLeaders"),
            "specified_mobs": _parse_range_table(floor_text, "pTableSpecifiedMobs"),
            "nm_even": _parse_range_table(floor_text, "pTableEvenFloorRandomNMs"),
            "nm_odd": _parse_range_table(floor_text, "pTableOddFloorRandomNMs"),
            "floor_entities": _parse_range_table(floor_text, "pTableFloorRandomEntities"),
        },
    }
