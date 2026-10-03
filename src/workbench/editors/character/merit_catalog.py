"""Read merit definitions from the selected server checkout.

Modern LandSandBoat exposes an authoritative ``data/merits.yaml`` dataset containing category
limits, merit IDs, per-upgrade effects, costs, and job/skill applicability. Older DSP/Topaz
checkouts do not consistently expose the same structured dataset, so this module deliberately
returns an unavailable catalog instead of applying current-LSB definitions to a legacy database.
"""
from __future__ import annotations

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

    missing = candidates[0] if candidates else None
    return {
        "source": _source("merit-catalog", missing, False),
        "categories": [],
        "items": {},
        "family": family,
        "note": "This checkout does not expose a supported structured merit definition catalog; stored merit IDs remain visible without guessed names or limits.",
    }
