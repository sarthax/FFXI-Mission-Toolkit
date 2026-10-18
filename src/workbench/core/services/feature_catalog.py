"""Read-only feature catalog sourced from curated Help entries.

Do not equate route presence with runtime acceptance. The catalog is an inventory
of operator-facing capabilities, not the graph Feature model or a roadmap ledger.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
CATALOG = ROOT / "feature_catalog" / "features.json"
ID_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
IMPLEMENTATION = {"implemented", "partial", "research", "planned"}
VALIDATION = {"unverified", "operator_reported", "tested"}


def load_catalog(path: Path = CATALOG) -> list[dict]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if raw.get("schema_version") != 1 or not isinstance(raw.get("features"), list):
        raise ValueError("unsupported feature catalog")
    seen = set()
    out = []
    for item in raw["features"]:
        if not isinstance(item, dict):
            raise ValueError("invalid catalog feature")
        feature_id = item.get("id")
        if not isinstance(feature_id, str) or not ID_RE.fullmatch(feature_id) or feature_id in seen:
            raise ValueError("invalid or duplicate feature ID")
        seen.add(feature_id)
        for key in ("module", "name", "summary", "route", "help"):
            if not isinstance(item.get(key), str) or not item[key].strip():
                raise ValueError(f"{feature_id}: missing {key}")
        if not item["route"].startswith("/") or not item["help"].startswith("/"):
            raise ValueError(f"{feature_id}: route/help must be local paths")
        if item.get("implementation") not in IMPLEMENTATION or item.get("validation") not in VALIDATION:
            raise ValueError(f"{feature_id}: invalid implementation or validation status")
        parent = item.get("parent_id")
        if parent is not None and (not isinstance(parent, str) or not ID_RE.fullmatch(parent)):
            raise ValueError(f"{feature_id}: invalid parent ID")
        out.append(dict(item))
    for item in out:
        if item.get("parent_id") and item["parent_id"] not in seen:
            raise ValueError(f"{item['id']}: unknown parent ID")
        if item.get("parent_id") == item["id"]:
            raise ValueError(f"{item['id']}: self-parenting feature")
    return out


def search_catalog(features: list[dict], query: str = "", module: str = "") -> list[dict]:
    needle = query.strip().casefold()
    return [f for f in features if (not module or f["module"] == module)
            and (not needle or any(needle in f[key].casefold() for key in ("name", "module", "summary", "id")))]
