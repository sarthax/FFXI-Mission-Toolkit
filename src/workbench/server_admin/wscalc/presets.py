"""Server augment presets (Mog Pell sets A-H, NQ/HQ) parsed from the worksheet CSV (augment_presets_tier5.csv).

Only the lines that map to a calculator stat are given numeric effects; every other line is kept as text and shown
as 'not modeled'. One CSV per tier (augment_presets_tierN.csv, first cell 'Tier N')."""
from __future__ import annotations

import csv
import re
from functools import lru_cache
from pathlib import Path

_STATS = {"STR": "str", "DEX": "dex", "VIT": "vit", "AGI": "agi", "INT": "int", "MND": "mnd", "CHR": "chr"}
# (regex, stat key); searched case-insensitively in each cell
_PATS = [
    (r"Dbl\.Atk\.\s*\+(\d+)", "da"), (r"Crit\.\s*hit rate\s*\+(\d+)", "crit_rate"), (r"Crit Hit Chance\s*\+(\d+)", "crit_rate"),
    (r"Crit\.\s*hit (?:damage|dmg)\s*\+(\d+)", "crit_dmg"), (r"Triple Atk\.\W*\+(\d+)", "ta"),
    (r"Quadruple Attack\s*\+(\d+)", "qa"), (r"^Attack\s*\+(\d+)", "att"), (r"^Accuracy\s*\+(\d+)", "acc"),
    (r"Mag\.Acc\.\s*\+(\d+)", "macc"), (r"Mag\.Atk\.Bns\.\W*\+(\d+)", "matt"),
    (r"Weapon skill damage\s*\+(\d+)", "wsd"), (r"^(?:Magic Damage|M\.DMG)\s*\+(\d+)", "mdmg"),
    (r"Magic Burst Damage\s*\+(\d+)", "burst"), (r"Elem\. magic skill\s*\+(\d+)", "elem_skill"),
    (r"^Affinity\s*\+(\d+)", "aff_all"),
    (r"Cure potency\s*\+(\d+)", "cure_pot"), (r"Fast Cast\s*\+(\d+)", "fastcast"), (r"Healing magic skill\s*\+(\d+)", "heal_skill"),
    (r"^Mag\.\s*Eva\.?\s*\+(\d+)", "meva"), (r"^Evasion\s*\+(\d+)", "eva"), (r"^Defense\s*\+(\d+)", "def"),
    (r"Magic def\.? bonus\s*\+(\d+)", "mdef_self"), (r"^HP\s*\+(\d+)", "hp"), (r"^MP\s*\+(\d+)", "mp"),
    (r"^Physical damage taken\s*-(\d+)", "dmg_phys_neg"), (r"^Magic damage taken\s*-(\d+)", "dmg_magic_neg"), (r"^Damage taken\s*-(\d+)", "dmg_neg"),
]
_LIST = re.compile(r"^([A-Z]{3}(?:/[A-Z]{3})*)\s*\+(\d+)\s*$")


def _cell(text: str) -> tuple[dict, bool]:
    t = text.strip().strip("“”")
    if not t:
        return {}, True
    m = _LIST.match(t)
    if m and all(s in _STATS for s in m.group(1).split("/")):
        return {_STATS[s]: int(m.group(2)) for s in m.group(1).split("/")}, True
    if "pet" in t.lower():
        return {}, False
    if "ninj" in t.lower():
        n = re.search(r"Ninj\w*\s*DMG:?\s*\+(\d+)", t, re.I)
        a = re.search(r"Mag\.Acc\.\s*\+(\d+)", t, re.I)
        e = {}
        if n:
            e["nin_mab"] = int(n.group(1))
        if a:
            e["nin_macc"] = int(a.group(1))
        return e, bool(e)
    eff: dict[str, int] = {}
    for rx, key in _PATS:
        for hit in re.finditer(rx, t, re.I):
            eff[key] = eff.get(key, 0) + int(hit.group(1))
    return eff, bool(eff)


@lru_cache(maxsize=1)
def load() -> list[dict]:
    out = []
    for path in sorted(Path(__file__).parent.glob("augment_presets_tier*.csv"), reverse=True):
        _load_file(path, out)
    return out


def _load_file(path: Path, out: list) -> None:
    with path.open(encoding="utf-8-sig", newline="") as f:
        rows = [[c.replace("�", "") for c in r] for r in csv.reader(f)]
    tier = int(re.search(r"(\d+)", rows[0][0]).group(1))
    for r in rows[1:]:
        r = r + [""] * (8 - len(r))
        if r[1] not in ("NQ", "HQ") or not r[2].strip():
            continue
        pm = re.search(r"(\w+) Mog Pell \((\w+)\)", r[0])
        if not pm:
            continue
        eff: dict[str, int] = {}
        lines = []
        for c in r[3:7]:
            if not c.strip():
                continue
            e, ok = _cell(c)
            for k, v in e.items():
                eff[k] = eff.get(k, 0) + v
            lines.append({"text": " ".join(c.split()), "modeled": ok})
        out.append({"id": f"T{tier}-{pm.group(1)}-{r[1]}-{r[2].strip()}", "tier": tier, "pell": pm.group(1), "stat": pm.group(2),
                    "quality": r[1], "letter": r[2].strip(), "lines": lines, "effects": eff, "comment": r[7].strip()})


def by_id() -> dict[str, dict]:
    return {p["id"]: p for p in load()}
