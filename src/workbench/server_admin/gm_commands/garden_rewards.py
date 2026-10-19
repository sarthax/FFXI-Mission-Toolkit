"""Read-only expected gardening rewards loaded from the DSP gardening_results.sql fixture."""
from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path

_ROW = re.compile(r"^\s*INSERT\s+INTO\s+`gardening_results`\s+VALUES\s*\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)\s*;", re.I | re.M)


def parse_results(sql: str) -> dict[tuple[int, int, int], list[dict]]:
    """Parse only explicitly supported eight-integer SQL tuples; never execute SQL."""
    if not isinstance(sql, str) or len(sql) > 5_000_000:
        raise ValueError("SQL fixture missing or too large")
    table: dict[tuple[int, int, int], list[dict]] = defaultdict(list)
    ids = set()
    for m in _ROW.finditer(sql):
        row_id, seed, c1, c2, item, minimum, maximum, weight = map(int, m.groups())
        if row_id in ids or not (1 <= seed <= 8 and 0 <= c1 <= 8 and 0 <= c2 <= 8
                                 and 0 < item <= 65535 and 0 < minimum <= maximum <= 255
                                 and 0 < weight <= 65535):
            raise ValueError(f"invalid or duplicate gardening result row {row_id}")
        ids.add(row_id)
        table[(seed, c1, c2)].append({"row_id": row_id, "item_id": item,
                                      "min_quantity": minimum, "max_quantity": maximum,
                                      "weight": weight})
    if not ids:
        raise ValueError("no gardening_results INSERT rows parsed")
    return dict(table)


def load_results(path: str | Path) -> dict[tuple[int, int, int], list[dict]]:
    return parse_results(Path(path).read_text(encoding="utf-8"))


def validate_harvest(table: dict, seed: int, crystal1: int, crystal2: int,
                     item_id: int, quantity: int) -> dict:
    """Validate an observed single-pot reward; no RNG or statistical claims."""
    key = (seed, crystal1, crystal2)
    outcomes = table.get(key)
    if not outcomes:
        return {"verdict": "BLOCKED", "reason": "no SQL outcomes for combination", "key": key}
    candidates = [x for x in outcomes if x["item_id"] == item_id]
    if not candidates:
        return {"verdict": "FAIL", "reason": "item is not an allowed SQL result", "key": key,
                "allowed_item_ids": sorted({x["item_id"] for x in outcomes})}
    if not any(x["min_quantity"] <= quantity <= x["max_quantity"] for x in candidates):
        return {"verdict": "FAIL", "reason": "quantity outside SQL bounds", "key": key,
                "allowed_ranges": [[x["min_quantity"], x["max_quantity"]] for x in candidates]}
    return {"verdict": "PASS", "reason": "item and quantity match an allowed SQL result",
            "key": key, "matching_rows": [x["row_id"] for x in candidates
                                         if x["min_quantity"] <= quantity <= x["max_quantity"]]}
