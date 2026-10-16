"""Reads weapon skill parameters straight from the DSP checkout's scripts/globals/weaponskills/*.lua.

Base = params assigned outside the USE_ADOULIN_WEAPON_SKILL_CHANGES block; `adoulin` = overlay inside it.
Skills with other conditional logic list those lines under `conditionals` so they are never silently trusted."""
from __future__ import annotations

import re
from pathlib import Path

ASSIGN = re.compile(r"params\.(\w+)\s*=\s*([^;\n]+?)\s*(?:;|$|--)", re.M)
ADOULIN = re.compile(r"if\s*\(\s*USE_ADOULIN_WEAPON_SKILL_CHANGES\s*==\s*true\s*\)\s*then(.*?)\n    end", re.S)
_cache: dict = {}
SPECIAL = {"spirits_within", "myrkr", "moonlight", "starlight", "dagan", "energy_drain", "energy_steal"}
WEAPONS = {"Archery", "Marksmanship", "Axe", "Club", "Dagger", "Great Axe", "Great Katana", "Great Sword", "Hand-to-Hand", "Katana", "Polearm", "Scythe", "Staff", "Sword"}
FALLBACK = {"ranged": "Ranged", "special": "Special", "magical": "Other", "physical": "Other"}


def _parse(s: str) -> dict:
    d: dict = {}
    for k, v in ASSIGN.findall(s):
        v = v.strip()
        try:
            d[k] = float(v)
        except ValueError:
            d[k] = {"true": True, "false": False}.get(v, v)
    return d


def load(dsp_root: Path | str) -> dict:
    src = Path(dsp_root) / "scripts" / "globals" / "weaponskills"
    key = str(src)
    files = sorted(src.glob("*.lua"))
    stamp = max((f.stat().st_mtime for f in files), default=0)
    if key in _cache and _cache[key][0] == stamp:
        return _cache[key][1]
    out: dict = {}
    for f in files:
        t = f.read_text(encoding="utf-8", errors="replace")
        m = re.search(r"function onUseWeaponSkill.*", t, re.S)
        if not m:
            continue
        body = m.group(0)
        kind = ("physical" if "doPhysicalWeaponskill" in body else "magical" if "doMagicWeaponskill" in body
                else "ranged" if "doRangedWeaponskill" in body else "special" if f.stem in SPECIAL else "other")
        ha = re.search(r"^--\s*([A-Za-z\- ]+?) weapon skill", t, re.M | re.I)
        base_txt, ado = body, ""
        am = ADOULIN.search(body)
        if am:
            ado, base_txt = am.group(1), body.replace(am.group(0), "")
        conds = [l.strip() for l in re.findall(r"^\s*(?:if|elseif)\b.*$", base_txt, re.M)
                 if "damage > 0" not in l and "tpHits" not in l]
        out[f.stem] = {"name": f.stem, "kind": kind, "weapon": (ha.group(1).strip() if ha and ha.group(1).strip() in WEAPONS else None) or FALLBACK.get(kind),
                       "params": _parse(base_txt), "adoulin": _parse(ado), "conditionals": conds}
    _cache[key] = (stamp, out)
    return out
