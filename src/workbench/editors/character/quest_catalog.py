"""Checkout-local quest name catalog for Character Editor.

Quest IDs are fork-local progression data. Parse only the selected DSP/Topaz/LSB checkout's
``scripts/globals/quests.lua`` and fall back to numeric IDs when that source is unavailable.
"""
from __future__ import annotations

from pathlib import Path
import re
from typing import Any


QUEST_LOG_IDS = {
    "SANDORIA": 0,
    "BASTOK": 1,
    "WINDURST": 2,
    "JEUNO": 3,
    "OTHER_AREAS": 4,
    "OUTLANDS": 5,
    "AHT_URHGAN": 6,
    "CRYSTAL_WAR": 7,
    "ABYSSEA": 8,
    "ADOULIN": 9,
    "COALITION": 10,
}


def _label(symbol: str) -> str:
    text = str(symbol or "").strip().replace("_", " ")
    return " ".join(word.capitalize() for word in text.split())


def quest_catalog(server_root: Path | str | None) -> dict[str, Any]:
    root = Path(server_root).resolve() if server_root else None
    path = root / "scripts" / "globals" / "quests.lua" if root else None
    source = {
        "kind": "quests.lua",
        "path": str(path) if path else None,
        "available": bool(path and path.is_file()),
    }
    if path is None or not path.is_file():
        return {"source": source, "areas": {}}

    # Supports historical ``dsp.quest.log_id`` / ``tpz.quest.log_id`` and current
    # ``xi.questLog`` spellings while still requiring an explicit known quest-log symbol.
    area_pattern = re.compile(
        r"quest\.area\[[^\n]*(?:quest\.log_id\.|questLog\.)([A-Z0-9_]+)\]\]\s*=\s*$"
    )
    value_pattern = re.compile(r"^\s*([A-Z][A-Z0-9_]*)\s*=\s*(\d+)\s*,?")

    areas: dict[int, dict[int, dict[str, Any]]] = {}
    current_area: int | None = None
    in_ids = False
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.split("--", 1)[0].rstrip()
        if not in_ids and re.search(r"quest\.id\s*=", line):
            in_ids = True
            continue
        if not in_ids:
            continue

        match = area_pattern.search(line)
        if match:
            current_area = QUEST_LOG_IDS.get(match.group(1))
            if current_area is not None:
                areas.setdefault(current_area, {})
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
        quest_id = int(raw_id)
        if not 0 <= quest_id <= 255:
            continue
        areas[current_area][quest_id] = {
            "id": quest_id,
            "symbol": symbol,
            "label": _label(symbol),
        }

    return {
        "source": source,
        "areas": {str(area_id): rows for area_id, rows in sorted(areas.items())},
    }
