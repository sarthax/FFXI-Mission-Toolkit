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


# --- Exact oracle: port of gardenutils.cpp CalculateResults (deterministic given pinned pot strength) ---
_PLANT_ELEMENT = {2: 3, 3: 1, 4: 4, 1: 6, 5: 7, 6: 2, 7: 8, 8: 5}  # plant id -> FLOWERPOT_ELEMENT_*
_TREE_PLANTS = {1, 5, 6, 7}
_POT_ELEMENT = {216: 3, 217: 1, 218: 4, 219: 6, 220: 7, 221: 8}


def _f32(v: float) -> float:
    import struct
    return struct.unpack("f", struct.pack("f", v))[0]


def expected_result(table: dict, plant: int, crystal1: int, crystal2: int, pot_strength: int,
                    *, pot_item_id: int | None = None, pot_matters: bool = False,
                    day_element: int | None = None, moon_bonus: int = 0,
                    aura_dominant: int = 0) -> dict:
    """Exact (item_id, quantity) the server yields for one pot. Optional bonuses mirror the garden_*_matters
    config flags (all 0 on the running server); pass them only when the matching flag is enabled.
    Row order within a combo follows the SQL file order (the server loads without ORDER BY: UNVERIFIED)."""
    if not (0 <= pot_strength <= 31):
        raise ValueError("pot_strength must be 0-31")
    el = [0] * 9
    el[crystal1] += 10
    tree = plant in _TREE_PLANTS
    if tree:
        el[crystal2] += 10
    el[_PLANT_ELEMENT.get(plant, 0)] += 10
    if day_element is not None:
        el[day_element] += 10
    if pot_matters and pot_item_id in _POT_ELEMENT:
        el[_POT_ELEMENT[pot_item_id]] += 10
    strength = max(el) if crystal1 == 0 else el[crystal1]
    if tree:
        strength += max(el) if crystal2 == 0 else el[crystal2]
    strength += moon_bonus + aura_dominant // 10
    strength += int((100 - strength) * (pot_strength / 32.0))
    key = (plant, crystal1, crystal2)
    rows = table.get(key)
    if not rows:
        return {"verdict": "BLOCKED", "reason": "no SQL outcomes for combination", "key": key}
    cum, pick = 0, None
    for r in rows:
        cum += r["weight"]
        if strength < cum:
            pick = r
            break
    if pick is None:
        pick = rows[-1]
    # C++: float percentage = (strength - base) / float(weight); int((max-min) * percentage + 0.1) -- 32-bit float math,
    # which matters at boundaries (e.g. 0.9f + 0.1 < 1.0 so quantity truncates down). Verified live 2026-10-18 (fruit tree, strength 98).
    pct = _f32((strength - (cum - pick["weight"])) / _f32(pick["weight"]))
    qty = pick["min_quantity"] + int(_f32((pick["max_quantity"] - pick["min_quantity"]) * pct) + 0.1)
    return {"verdict": "EXPECTED", "key": key, "strength": strength, "item_id": pick["item_id"],
            "quantity": qty, "row_id": pick["row_id"]}


def validate_harvest_exact(table: dict, plant: int, crystal1: int, crystal2: int, pot_strength: int,
                           item_id: int, quantity: int, **bonuses) -> dict:
    exp = expected_result(table, plant, crystal1, crystal2, pot_strength, **bonuses)
    if exp["verdict"] == "BLOCKED":
        return exp
    ok = exp["item_id"] == item_id and exp["quantity"] == quantity
    return {**exp, "verdict": "PASS" if ok else "FAIL",
            "reason": "exact match" if ok else "differs from deterministic expectation",
            "observed": {"item_id": item_id, "quantity": quantity}}
