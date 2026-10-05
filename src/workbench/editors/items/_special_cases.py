"""Read-only 'where else does this item matter' lookups for the Item Editor.

Covers behavior that is NOT stored as item_mods/item_latents rows: gear-set bonuses,
food/use bonuses written in item scripts, and item ids special-cased in server C++/Lua.
Everything is parsed from the active server tree; nothing is invented.
"""
from __future__ import annotations

import re
import threading
from pathlib import Path

_lock = threading.Lock()
_cache: dict[str, dict] = {}

_SET_RE = re.compile(r"\{\s*id\s*=\s*(\d+)\s*,\s*items\s*=\s*\{([^}]*)\}\s*,\s*matches\s*=\s*(\d+)(.*?)\}\s*,?\s*(?:--([^\n]*))?$", re.M)
_MODROW_RE = re.compile(r"\{\s*((?:xi\.mod\.|tpz\.mod\.|MOD_)?[A-Za-z_0-9]+)\s*,\s*(-?[\d.]+)\s*,\s*(-?[\d.]+)\s*,\s*(-?[\d.]+)\s*\}")
_ADDMOD_RE = re.compile(r"addMod\(\s*((?:xi\.mod\.|tpz\.mod\.|MOD_)?[A-Za-z_0-9]+)\s*,\s*(-?[\d.]+)\s*\)")
_NUM_RE = re.compile(r"(?<![\d.])(\d{3,5})(?![\d.])")
_CTX_CPP = re.compile(r"getID\(\)|getEquip|itemid|ItemID|PItem|PWeapon|PAmmo|case\s+\d+\s*:", re.I)
_CTX_LUA = re.compile(r"getEquipID|hasItem|ItemID|itemid|getID\(\)|equip|item", re.I)


def _root_key(root: Path) -> str:
    return str(root)


def _build_index(root: Path) -> dict:
    refs: dict[int, list[dict]] = {}
    srcs = list((root / "src" / "map").rglob("*.cpp"))
    gl = root / "scripts" / "globals"
    srcs += [p for p in gl.glob("*.lua")] if gl.is_dir() else []
    for p in srcs:
        is_cpp = p.suffix == ".cpp"
        ctx = _CTX_CPP if is_cpp else _CTX_LUA
        try:
            lines = p.read_text(encoding="utf-8", errors="ignore").splitlines()
        except Exception:
            continue
        for n, line in enumerate(lines, 1):
            if line.lstrip().startswith(("//", "--")) or not ctx.search(line):
                continue
            if "INSERT INTO" in line or len(line) > 400:
                continue
            for m in _NUM_RE.finditer(line):
                refs.setdefault(int(m.group(1)), []).append({
                    "file": str(p.relative_to(root)).replace("\\", "/"), "line": n, "text": line.strip()[:200]})
    return refs


def _gear_sets(root: Path) -> list[dict]:
    p = root / "scripts" / "globals" / "gear_sets.lua"
    if not p.is_file():
        return []
    txt = p.read_text(encoding="utf-8", errors="ignore")
    out = []
    for m in _SET_RE.finditer(txt):
        items = [int(x) for x in re.findall(r"\d+", m.group(2))]
        mods = [{"mod": r.group(1), "value": float(r.group(2)), "per_extra_match": float(r.group(3)), "full_set_bonus": float(r.group(4))}
                for r in _MODROW_RE.finditer(m.group(4))]
        out.append({"set_id": int(m.group(1)), "items": items, "matches_required": int(m.group(3)),
                    "mods": mods, "comment": (m.group(5) or "").strip()})
    return out


def special_cases(root: Path, item_id: int, name: str = "") -> dict:
    root = Path(root)
    key = _root_key(root)
    with _lock:
        if key not in _cache:
            _cache[key] = {"refs": _build_index(root), "sets": _gear_sets(root)}
        c = _cache[key]
    sets = [s for s in c["sets"] if item_id in s["items"]]
    internal = re.sub(r"[^a-z0-9_+]", "", (name or "").lower())
    food = []
    for rel in (f"scripts/globals/items/{internal}.lua", f"scripts/items/{internal}.lua"):
        p = root / rel
        if internal and p.is_file():
            txt = p.read_text(encoding="utf-8", errors="ignore")
            m = re.search(r"function\s+(?:\w+[.:])?onEffectGain\b(.*?)\nend", txt, re.S)
            if m:
                food = [{"mod": a.group(1), "value": float(a.group(2))} for a in _ADDMOD_RE.finditer(m.group(1))]
            break
    return {"item_id": item_id, "gear_sets": sets, "effect_gain_mods": food,
            "code_references": c["refs"].get(item_id, [])[:12]}


def clear_cache() -> None:
    with _lock:
        _cache.clear()
