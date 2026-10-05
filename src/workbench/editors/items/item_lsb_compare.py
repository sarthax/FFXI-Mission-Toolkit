"""Compare one item's DSP data against the LandSandBoat reference SQL (read-only, by mod NAME,
because mod ids differ between lineages). Differences are reported, never auto-judged: either
tree can be the one that is wrong."""
from __future__ import annotations

import os
import re
from functools import lru_cache
from pathlib import Path

LSB_ROOT = Path(os.environ.get("LSB_REFERENCE_ROOT", r"D:\Claude\landsandboat-reference"))
# Same concept spelled differently in the two enums (verified by reading both enums).
ALIASES = {"SNAP_SHOT": "SNAPSHOT", "WALTZ_POTENTCY": "WALTZ_POTENCY",
           "ITEM_ADDEFFECT_TYPE": "ADDITIONAL_EFFECT"}  # 431: LSB proc type vs DSP script flag (same slot)
for _e in ("FIRE", "ICE", "WIND", "EARTH", "THUNDER", "WATER", "LIGHT", "DARK"):
    ALIASES[f"{_e}_MEVA"] = f"{_e}RES"  # elemental resistance: LSB *_MEVA == DSP *RES (Joyeuse DARK 14 checked)
_INS = re.compile(r"INSERT INTO `(\w+)` VALUES \((.*?)\);\s*(?:--\s*(.*))?$")
_ENUM = re.compile(r"^\s*([A-Z0-9_]+)\s*=\s*(\d+),")


def _norm(name):
    name = re.split(r"\s+--\s+", (name or "").strip())[0].strip()
    return ALIASES.get(name, name)


@lru_cache(maxsize=1)
def _lsb_mod_names(root: str) -> dict:
    out = {}
    p = Path(root) / "documentation" / "mods_by_id.txt"
    if p.is_file():
        for line in p.read_text(encoding="utf-8", errors="ignore").splitlines():
            m = _ENUM.match(line)
            if m:
                out[int(m.group(2))] = m.group(1)
    return out


@lru_cache(maxsize=1)
def _lsb_rows(root: str) -> dict:
    """{table: {item_id: [tuple,...]}} for item_mods and item_weapon."""
    rows = {"item_mods": {}, "item_weapon": {}}
    for table in rows:
        p = Path(root) / "sql" / f"{table}.sql"
        if not p.is_file():
            continue
        for line in p.read_text(encoding="utf-8", errors="ignore").splitlines():
            m = _INS.match(line.strip())
            if not m or m.group(1) != table:
                continue
            vals = [v.strip().strip("'") for v in m.group(2).split(",")]
            try:
                rows[table].setdefault(int(vals[0]), []).append(tuple(vals[1:]))
            except ValueError:
                pass
    return rows


def compare_with_lsb(item_id: int, dsp_data: dict, lsb_root: Path | None = None) -> dict:
    """dsp_data is get_item() output. Returns per-mod and per-weapon-field differences."""
    root = str(lsb_root or LSB_ROOT)
    if not (Path(root) / "sql" / "item_mods.sql").is_file():
        return {"available": False, "reason": f"LSB reference not found at {root}"}
    names, rows = _lsb_mod_names(root), _lsb_rows(root)
    lsb_mods = {}
    for mid, val in rows["item_mods"].get(int(item_id), []):
        lsb_mods[_norm(names.get(int(mid), f"#{mid}"))] = int(val)
    dsp_mods = {_norm(m.get("name") or f"#{m['modId']}"): int(m["value"]) for m in dsp_data.get("mods") or []}
    diffs = []
    for n in sorted(set(lsb_mods) | set(dsp_mods)):
        a, b = dsp_mods.get(n), lsb_mods.get(n)
        if a == b:
            continue
        kind = "dsp-only" if b is None else "lsb-only" if a is None else "value"
        hint = "LSB value is exactly 100x DSP (LSB stores percentages scaled)" if (a and b and b == a * 100) else ""
        diffs.append({"mod": n, "dsp": a, "lsb": b, "kind": kind, "hint": hint})
    weapon = []
    dw = (dsp_data.get("server") or {}).get("item_weapon")
    lw = rows["item_weapon"].get(int(item_id))
    if dw and lw:
        # LSB columns after itemId: name, skill, subskill, ilvl_skill, ilvl_parry, ilvl_macc, dmgType, hit, delay, dmg
        t = lw[0]
        lsb = {"skill": t[1], "dmgType": t[6], "hit": t[7], "delay": t[8], "dmg": t[9]}
        for k, v in lsb.items():
            try:
                if int(dw.get(k)) != int(v):
                    weapon.append({"field": k, "dsp": dw.get(k), "lsb": int(v)})
            except (TypeError, ValueError):
                pass
    in_lsb = int(item_id) in rows["item_mods"] or int(item_id) in rows["item_weapon"]
    return {"available": True, "in_lsb": in_lsb, "mod_differences": diffs, "weapon_differences": weapon,
            "identical": in_lsb and not diffs and not weapon}
