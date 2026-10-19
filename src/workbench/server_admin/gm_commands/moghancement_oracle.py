"""Read-only DSP Moghancement layout oracle, using item_furnishing.sql metadata.

This predicts CCharEntity::UpdateMoghancement, *not* client furnishing behavior.
Input layout is an ordered list of installed furniture items, in server container/slot
scan order (Mog Safe then Mog Safe 2). Never submit GM commands here.
"""
from __future__ import annotations
import re
from pathlib import Path

_ROW = re.compile(r"^\s*INSERT\s+INTO\s+`item_furnishing`\s+VALUES\s*\(\s*(\d+)\s*,\s*'((?:[^'\\]|\\.)*)'\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)\s*;", re.M | re.I)


def parse_furnishings(sql: str) -> dict[int, dict]:
    if not isinstance(sql, str) or len(sql) > 3_000_000:
        raise ValueError("invalid item_furnishing SQL")
    rows = {}
    for m in _ROW.finditer(sql):
        item, name, storage, ki, element, aura = m.groups()
        item, storage, ki, element, aura = map(int, (item, storage, ki, element, aura))
        if item in rows or not 0 <= element <= 7 or not 0 <= aura <= 255:
            raise ValueError(f"invalid or repeated furnishing {item}")
        rows[item] = {"item_id": item, "name": name, "storage": storage,
                      "key_item": ki, "element": element, "aura": aura}
    if not rows:
        raise ValueError("no item_furnishing records")
    return rows


def load_furnishings(path: str | Path) -> dict[int, dict]:
    return parse_furnishings(Path(path).read_text(encoding="utf-8"))


def predict_moghancement(furnishings: dict[int, dict], layout: list[dict]) -> dict:
    """Return expected KI and element sums; no installed item or tied elements -> 0.

    Layout entries: item_id, container, slot, installed. The server iterates
    Mog Safe then Safe 2 in ascending slot order; caller cannot spoof order.
    """
    if not isinstance(layout, list):
        raise ValueError("layout must be a list")
    aura = [0] * 8
    installed = []
    seen = set()
    for entry in layout:
        if not isinstance(entry, dict) or set(entry) != {"item_id", "container", "slot", "installed"}:
            raise ValueError("invalid furniture entry")
        item, container, slot, flag = (entry[k] for k in ("item_id", "container", "slot", "installed"))
        if type(item) is not int or item not in furnishings:
            raise ValueError(f"unknown furnishing item {item}")
        if type(container) is not int or container not in (1, 2):
            raise ValueError("container must be 1 or 2 (logical Safe numbering)")
        if type(slot) is not int or not 0 <= slot <= 255 or type(flag) is not bool:
            raise ValueError("invalid slot or installed flag")
        identity = (container, slot)
        if identity in seen:
            raise ValueError("duplicate slot")
        seen.add(identity)
        if flag:
            meta = furnishings[item]
            aura[meta["element"]] += meta["aura"]
            installed.append((container, slot, meta))
    strongest = max(aura)
    if strongest == 0 or aura.count(strongest) != 1:
        return {"key_item": 0, "dominant_element": None, "aura": aura,
                "winning_item": None, "reason": "no aura or tied dominant elements"}
    element = aura.index(strongest)
    winner = None
    best = 0
    for container, slot, meta in sorted(installed, key=lambda v: (v[0], v[1])):
        if meta["element"] == element and meta["aura"] > best and meta["key_item"] != 0:
            winner = {"container": container, "slot": slot, "item_id": meta["item_id"]}
            best = meta["aura"]
            key_item = meta["key_item"]
    return {"key_item": key_item if winner else 0, "dominant_element": element,
            "aura": aura, "winning_item": winner, "reason": "selected" if winner else "no eligible furniture"}


def check_transition(before: int, after: int, held: list[int], expected: int) -> dict:
    """Assert one current furniture KI and no stale prior KI after furnishing menu closes."""
    if any(type(v) is not int for v in (before, after, expected)) or not isinstance(held, list):
        raise ValueError("invalid transition")
    expected_held = [] if expected == 0 else [expected]
    ok = after == expected and sorted(held) == expected_held
    return {"verdict": "PASS" if ok else "FAIL", "expected": expected,
            "observed": after, "held": held, "prior_removed": before == expected or before not in held}
