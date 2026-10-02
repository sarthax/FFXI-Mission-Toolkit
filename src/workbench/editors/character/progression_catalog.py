"""Parse progression/unlock names from the configured DSP/Topaz/LSB checkout.

The connected server checkout is the catalog authority. This intentionally avoids treating a
current LSB enum as valid for an older DSP/Topaz database whose IDs can differ materially.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any


_LOG_IDS = {
    "SANDORIA": 0,
    "BASTOK": 1,
    "WINDURST": 2,
    "ZILART": 3,
    "TOAU": 4,
    "WOTG": 5,
    "COP": 6,
    "ASSAULT": 7,
    "CAMPAIGN": 8,
    "ACP": 9,
    "AMK": 10,
    "ASA": 11,
    "SOA": 12,
    "ROV": 13,
    "TVR": 14,
}


def _label(symbol: str) -> str:
    text = str(symbol or "").strip().replace("_", " ")
    return " ".join(word.capitalize() for word in text.split())


def _source_label(name: str) -> str:
    """Make SQL names readable without destroying useful mixed-case zone spellings."""
    text = str(name or "").strip().replace("_", " ")
    if any(ch.isupper() for ch in text[1:]):
        return text
    return " ".join(word.capitalize() for word in text.split())


@dataclass(frozen=True)
class CatalogSource:
    kind: str
    path: Path | None
    available: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "path": str(self.path) if self.path else None,
            "available": self.available,
        }


def mission_catalog(server_root: Path | str | None) -> dict[str, Any]:
    root = Path(server_root).resolve() if server_root else None
    path = root / "scripts" / "globals" / "missions.lua" if root else None
    result: dict[int, dict[int, dict[str, Any]]] = {}
    if path is None or not path.is_file():
        return {"source": CatalogSource("missions.lua", path, False).as_dict(), "areas": {}}

    current_area: int | None = None
    in_ids = False
    area_pattern = re.compile(r"mission\.area\[[^\n]*mission\.log_id\.([A-Z0-9_]+)\]\]\s*=\s*$")
    value_pattern = re.compile(r"^\s*([A-Z][A-Z0-9_]*)\s*=\s*(\d+)\s*,?")
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.split("--", 1)[0].rstrip()
        if not in_ids and re.search(r"mission\.id\s*=", line):
            in_ids = True
            continue
        if not in_ids:
            continue
        match = area_pattern.search(line)
        if match:
            current_area = _LOG_IDS.get(match.group(1))
            if current_area is not None:
                result.setdefault(current_area, {})
            continue
        if current_area is None:
            continue
        if line.strip().startswith("},") or line.strip() == "}":
            current_area = None
            continue
        match = value_pattern.match(line)
        if not match:
            continue
        symbol, raw_id = match.groups()
        if symbol == "NONE":
            continue
        mission_id = int(raw_id)
        result[current_area][mission_id] = {
            "id": mission_id,
            "symbol": symbol,
            "label": _label(symbol),
        }

    return {
        "source": CatalogSource("missions.lua", path, True).as_dict(),
        "areas": {str(area): rows for area, rows in sorted(result.items())},
    }


def _parse_lua_keyitems(path: Path) -> dict[int, dict[str, Any]]:
    value_pattern = re.compile(r"^\s*([A-Z][A-Z0-9_]*)\s*=\s*(\d+)\s*,?")
    out: dict[int, dict[str, Any]] = {}
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.split("--", 1)[0]
        match = value_pattern.match(line)
        if not match:
            continue
        symbol, raw_id = match.groups()
        key_id = int(raw_id)
        out[key_id] = {"id": key_id, "symbol": symbol, "label": _label(symbol)}
    return out


def _parse_yaml_keyitems(path: Path) -> dict[int, dict[str, Any]]:
    value_pattern = re.compile(r"^\s{2}([A-Za-z][A-Za-z0-9_]*)\s*:\s*(\d+)\s*(?:#.*)?$")
    out: dict[int, dict[str, Any]] = {}
    in_values = False
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if raw.strip() == "values:":
            in_values = True
            continue
        if not in_values:
            continue
        if raw and not raw.startswith(" "):
            break
        match = value_pattern.match(raw)
        if not match:
            continue
        symbol, raw_id = match.groups()
        key_id = int(raw_id)
        out[key_id] = {"id": key_id, "symbol": symbol, "label": _label(symbol)}
    return out


def key_item_catalog(server_root: Path | str | None, adapter_family: str) -> dict[str, Any]:
    root = Path(server_root).resolve() if server_root else None
    family = str(adapter_family or "unknown").lower()
    candidates: list[tuple[str, Path]] = []
    if root:
        if family == "lsb":
            candidates.append(("key_item.yaml", root / "data" / "enums" / "key_item.yaml"))
        candidates.append(("keyitems.lua", root / "scripts" / "globals" / "keyitems.lua"))

    for kind, path in candidates:
        if not path.is_file():
            continue
        rows = _parse_yaml_keyitems(path) if kind.endswith(".yaml") else _parse_lua_keyitems(path)
        return {
            "source": CatalogSource(kind, path, True).as_dict(),
            "items": {str(key_id): row for key_id, row in sorted(rows.items())},
        }

    missing = candidates[0][1] if candidates else None
    return {"source": CatalogSource("key-items", missing, False).as_dict(), "items": {}}


def _parse_lua_enum(path: Path) -> dict[int, dict[str, Any]]:
    value_pattern = re.compile(r"^\s*([A-Z][A-Z0-9_]*)\s*=\s*(\d+)\s*,?")
    out: dict[int, dict[str, Any]] = {}
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.split("--", 1)[0]
        match = value_pattern.match(line)
        if not match:
            continue
        symbol, raw_id = match.groups()
        item_id = int(raw_id)
        out[item_id] = {"id": item_id, "symbol": symbol, "label": _label(symbol)}
    return out


def _catalog_from_lua_candidates(root: Path | None, kind: str, relative_paths: tuple[str, ...]) -> dict[str, Any]:
    candidates = [root / rel for rel in relative_paths] if root else []
    for path in candidates:
        if not path.is_file():
            continue
        rows = _parse_lua_enum(path)
        if rows:
            return {
                "source": CatalogSource(path.name, path, True).as_dict(),
                "items": {str(item_id): row for item_id, row in sorted(rows.items())},
            }
    missing = candidates[0] if candidates else None
    return {"source": CatalogSource(kind, missing, False).as_dict(), "items": {}}


def ability_catalog(server_root: Path | str | None) -> dict[str, Any]:
    """Label learned-ability bits from this checkout's ``sql/abilities.sql`` table."""
    root = Path(server_root).resolve() if server_root else None
    path = root / "sql" / "abilities.sql" if root else None
    if path is None or not path.is_file():
        return {"source": CatalogSource("abilities.sql", path, False).as_dict(), "items": {}}

    pattern = re.compile(r"INSERT\s+INTO\s+`abilities`\s+VALUES\s*\(\s*(\d+)\s*,\s*'([^']*)'", re.I)
    rows: dict[int, dict[str, Any]] = {}
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        match = pattern.search(raw)
        if not match:
            continue
        raw_id, name = match.groups()
        item_id = int(raw_id)
        rows[item_id] = {"id": item_id, "symbol": name.upper(), "label": _source_label(name)}
    return {
        "source": CatalogSource("abilities.sql", path, True).as_dict(),
        "items": {str(item_id): row for item_id, row in sorted(rows.items())},
    }


def weaponskill_unlock_catalog(server_root: Path | str | None) -> dict[str, Any]:
    """Label learned-weaponskill bits only from explicit unlock-ID enums.

    Normal weaponskill action IDs are a different domain and are intentionally never substituted.
    """
    root = Path(server_root).resolve() if server_root else None
    return _catalog_from_lua_candidates(
        root,
        "weaponskill-unlock-enum",
        (
            "scripts/enum/ws_unlock.lua",
            "scripts/globals/ws_unlock.lua",
            "scripts/globals/weaponskill_unlocks.lua",
        ),
    )


def title_catalog(server_root: Path | str | None) -> dict[str, Any]:
    root = Path(server_root).resolve() if server_root else None
    return _catalog_from_lua_candidates(
        root,
        "title-enum",
        (
            "scripts/enum/title.lua",
            "scripts/globals/titles.lua",
            "scripts/globals/title.lua",
        ),
    )


def visited_zone_catalog(server_root: Path | str | None) -> dict[str, Any]:
    """Label visited-zone bits from this checkout's zone_settings rows."""
    root = Path(server_root).resolve() if server_root else None
    path = root / "sql" / "zone_settings.sql" if root else None
    if path is None or not path.is_file():
        return {"source": CatalogSource("zone_settings.sql", path, False).as_dict(), "items": {}}

    pattern = re.compile(
        r"INSERT\s+INTO\s+`zone_settings`\s+VALUES\s*\(\s*(\d+)\s*,[^,]*,\s*'[^']*'\s*,[^,]*,\s*'([^']*)'",
        re.I,
    )
    rows: dict[int, dict[str, Any]] = {}
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        match = pattern.search(raw)
        if not match:
            continue
        raw_id, name = match.groups()
        item_id = int(raw_id)
        rows[item_id] = {"id": item_id, "symbol": name, "label": _source_label(name)}
    return {
        "source": CatalogSource("zone_settings.sql", path, True).as_dict(),
        "items": {str(item_id): row for item_id, row in sorted(rows.items())},
    }


def progression_catalog(server_root: Path | str | None, adapter_family: str) -> dict[str, Any]:
    return {
        "missions": mission_catalog(server_root),
        "key_items": key_item_catalog(server_root, adapter_family),
        "abilities": ability_catalog(server_root),
        "weaponskills": weaponskill_unlock_catalog(server_root),
        "titles": title_catalog(server_root),
        "visited_zones": visited_zone_catalog(server_root),
    }
