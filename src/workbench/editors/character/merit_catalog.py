"""Read merit definitions from the selected server checkout.

Modern LandSandBoat exposes an authoritative ``data/merits.yaml`` dataset containing category
limits, merit IDs, per-upgrade effects, costs, and job/skill applicability. Older DSP/Topaz
checkouts do not expose that dataset, so they are read from their *own* definition files
(``sql/merits.sql`` plus ``src/map/merit.h``/``merit.cpp``). If those are missing too, an
unavailable catalog is returned instead of applying current-LSB definitions to a legacy database.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml


def _label(value: str) -> str:
    text = str(value or "").strip().replace("_", " ")
    replacements = {"hp": "HP", "mp": "MP", "str": "STR", "dex": "DEX", "vit": "VIT", "agi": "AGI", "int": "INT", "mnd": "MND", "chr": "CHR"}
    return " ".join(replacements.get(word.lower(), word.capitalize()) for word in text.split())


def _source(kind: str, path: Path | None, available: bool) -> dict[str, Any]:
    return {"kind": kind, "path": str(path) if path else None, "available": available}


def _normalize_tokens(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def _parse_lsb_yaml(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8", errors="replace")) or {}
    merits = payload.get("merits") or {}
    costs = merits.get("upgrade_costs") or {}
    categories = merits.get("categories") or {}

    category_rows: list[dict[str, Any]] = []
    items: dict[str, dict[str, Any]] = {}
    for category_key, category in categories.items():
        if not isinstance(category, dict):
            continue
        category_id = int(category.get("id", 0) or 0)
        merit_rows: list[dict[str, Any]] = []
        for merit_key, merit in (category.get("merits") or {}).items():
            if not isinstance(merit, dict) or merit.get("id") is None:
                continue
            merit_id = int(merit["id"])
            cost_key = str(merit.get("upgrade_cost") or "")
            cost_schedule = [int(value) for value in (costs.get(cost_key) or [])]
            row = {
                "id": merit_id,
                "symbol": str(merit_key),
                "label": _label(str(merit_key)),
                "category": str(category_key),
                "category_id": category_id,
                "category_label": _label(str(category_key)),
                "value_per_upgrade": int(merit.get("value", 0) or 0),
                "upgrade_cost": cost_key or None,
                "costs": cost_schedule,
                "max_upgrades": len(cost_schedule) if cost_schedule else None,
                "jobs": _normalize_tokens(merit.get("jobs")),
                "skills": _normalize_tokens(merit.get("skills")),
                "weapon_skill": merit.get("weapon_skill"),
            }
            merit_rows.append(row)
            items[str(merit_id)] = row
        merit_rows.sort(key=lambda row: row["id"])
        category_rows.append(
            {
                "key": str(category_key),
                "id": category_id,
                "label": _label(str(category_key)),
                "max_upgrades": int(category.get("max_upgrades", 0) or 0),
                "merits": merit_rows,
            }
        )

    category_rows.sort(key=lambda row: row["id"])
    return {
        "source": _source("merits.yaml", path, True),
        "categories": category_rows,
        "items": items,
        "upgrade_costs": {str(key): [int(value) for value in values] for key, values in costs.items() if isinstance(values, list)},
    }


# FFXI job ids 1-22 (job mask bit is ``1 << (job_id - 1)``, verified against DSP merit.cpp's
# ``PMerit->jobs & (1 << (PChar->GetMJob() - 1))``).
_JOB_ABBR = ("WAR", "MNK", "WHM", "BLM", "RDM", "THF", "PLD", "DRK", "BST", "BRD", "RNG", "SAM",
             "NIN", "DRG", "SMN", "BLU", "COR", "PUP", "DNC", "SCH", "GEO", "RUN")
_ALL_JOBS_MASK = (1 << 20) - 1  # DSP/Topaz "every job" value (WAR..SCH)


def _job_tokens(mask: int) -> list[str]:
    """Job abbreviations for a legacy job bitmask; empty when the merit applies to every job."""
    if mask & _ALL_JOBS_MASK == _ALL_JOBS_MASK:
        return []
    return [abbr for bit, abbr in enumerate(_JOB_ABBR) if mask & (1 << bit)]


def _category_label(name: str) -> str:
    return {"HP_MP": "Start (HP/MP)", "WS": "Weapon Skills"}.get(name, _label(name))


def _parse_dsp_legacy(root: Path) -> dict[str, Any] | None:
    """Build the catalog from a DSP/Topaz checkout's own merit definition files.

    Uses only that checkout: ``sql/merits.sql`` (id, name, max rank, value, job mask, cost group,
    category index), ``src/map/merit.h`` (``MCATEGORY_*`` names; category index is ``(id >> 6) - 1``)
    and ``src/map/merit.cpp`` (per-category point cap and the per-rank upgrade cost table).
    Returns None when any of those files is absent so callers keep the honest "unavailable" result.
    """
    sql_path = root / "sql" / "merits.sql"
    header_path = root / "src" / "map" / "merit.h"
    source_path = root / "src" / "map" / "merit.cpp"
    if not (sql_path.is_file() and header_path.is_file() and source_path.is_file()):
        return None

    header = header_path.read_text(encoding="utf-8", errors="replace")
    source = source_path.read_text(encoding="utf-8", errors="replace")

    cat_names: dict[int, str] = {}
    for name, value in re.findall(r"MCATEGORY_(\w+)\s*=\s*0x([0-9A-Fa-f]+)", header):
        # Several enum names alias one value (HP_MP/START, RNG_1/GEO_2, SAM_1/RUN_2); the first
        # definition is the real category, the later ones are compatibility aliases.
        if name != "COUNT":
            cat_names.setdefault((int(value, 16) >> 6) - 1, name)

    # Rows like ``{4,10,7},  //MCATEGORY_DNC_2`` -> (merits in category, max points, cost group)
    cat_caps = {
        name: (int(count), int(points), int(group))
        for count, points, group, name in re.findall(r"\{\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\}\s*,?\s*//\s*MCATEGORY_(\w+)", source)
    }

    upgrade_block = re.search(r"static\s+uint8\s+upgrade\[[^\]]*\]\[[^\]]*\]\s*=\s*\{(.*?)\};", source, re.S)
    cost_groups: list[list[int]] = []
    if upgrade_block:
        for row in re.findall(r"\{([^{}]*)\}", upgrade_block.group(1)):
            cost_groups.append([int(v) for v in re.findall(r"\d+", row)])

    sql_text = sql_path.read_text(encoding="utf-8", errors="replace")
    rows = re.findall(r"INSERT INTO `merits` VALUES \((\d+),'([^']*)',(\d+),(-?\d+),(\d+),(\d+),(\d+)\);", sql_text)
    if not rows or not cat_names:
        return None

    items: dict[str, dict[str, Any]] = {}
    by_category: dict[int, list[dict[str, Any]]] = {}
    for merit_id, symbol, max_rank, value, jobs, group, cat_index in rows:
        merit_id, max_rank, group, cat_index = int(merit_id), int(max_rank), int(group), int(cat_index)
        cat_name = cat_names.get(cat_index, f"CATEGORY_{cat_index}")
        schedule = cost_groups[group][:max_rank] if 0 <= group < len(cost_groups) else []
        row = {
            "id": merit_id,
            "symbol": symbol,
            "label": _label(symbol),
            "category": cat_name.lower(),
            "category_id": cat_index,
            "category_label": _category_label(cat_name),
            "value_per_upgrade": int(value),
            "upgrade_cost": f"group_{group}",
            "costs": schedule,
            "max_upgrades": max_rank or None,
            "jobs": _job_tokens(int(jobs)),
            "skills": [],
            "weapon_skill": None,
        }
        by_category.setdefault(cat_index, []).append(row)
        items[str(merit_id)] = row

    categories = []
    for cat_index in sorted(by_category):
        cat_name = cat_names.get(cat_index, f"CATEGORY_{cat_index}")
        merits = sorted(by_category[cat_index], key=lambda r: r["id"])
        categories.append({
            "key": cat_name.lower(),
            "id": cat_index,
            "label": _category_label(cat_name),
            "max_upgrades": cat_caps.get(cat_name, (0, 0, 0))[1],
            "merits": merits,
        })
    return {
        "source": _source("dsp-merits-sql", sql_path, True),
        "categories": categories,
        "items": items,
        "upgrade_costs": {f"group_{i}": costs for i, costs in enumerate(cost_groups)},
    }


def merit_catalog(server_root: Path | str | None, adapter_family: str) -> dict[str, Any]:
    root = Path(server_root).resolve() if server_root else None
    family = str(adapter_family or "unknown").strip().lower()

    candidates: list[Path] = []
    if root is not None:
        # Current LSB dataset. Some forks keep the same data layout even when their adapter was
        # detected as auto/unknown; parsing the checkout itself is safer than assuming by family.
        candidates.append(root / "data" / "merits.yaml")

    for path in candidates:
        if not path.is_file():
            continue
        try:
            return _parse_lsb_yaml(path)
        except (OSError, TypeError, ValueError, yaml.YAMLError) as exc:
            return {
                "source": _source("merits.yaml", path, False),
                "categories": [],
                "items": {},
                "error": str(exc),
                "family": family,
            }

    if root is not None:
        legacy = _parse_dsp_legacy(root)
        if legacy is not None:
            legacy["family"] = family
            return legacy

    missing = candidates[0] if candidates else None
    return {
        "source": _source("merit-catalog", missing, False),
        "categories": [],
        "items": {},
        "family": family,
        "note": "This checkout does not expose a supported structured merit definition catalog; stored merit IDs remain visible without guessed names or limits.",
    }
