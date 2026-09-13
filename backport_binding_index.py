#!/usr/bin/env python3
"""
backport_binding_index.py -- builds a real, full inventory of every Lua binding registered in
Topaz and in old-dsp-reference, instead of re-grepping C++ source on every lookup (what
backport_lua_convert.py's TARGET_FINGERPRINTS and backport_binding_audit.py's check_binding()
both did before this existed). Two uses:

1. A cached index (data/topaz_binding_index.json, data/old_dsp_reference_binding_index.json) that
   other tools can load once instead of re-scanning every src/map/lua/*.cpp file per call.
2. A real Topaz-vs-old-dsp-reference DIFF (`--diff`): classifies every Topaz binding name into
   "exact match" (same name registered in both -- confirmed safe as-is), "case-only match" (same
   name, different case -- the exact bug class that cost real time this session:
   SetAutoAttackEnabled/PrintToPlayer/etc.), or "topaz-only" (no matching name found in
   old-dsp-reference at all under any casing -- either old-dsp-reference spells it completely
   differently, or it's a genuine gap; this tool can't tell those apart, it only tells you WHICH
   names need a human/grep look, same "flag, don't guess" discipline as everything else in this
   project).

Neither codebase changes often, so this index is meant to be regenerated occasionally (after a
DSP engine patch adds/renames a binding), not on every single conversion run.

Usage:
    py -3 backport_binding_index.py --build              # (re)generate both cached indexes
    py -3 backport_binding_index.py --diff                # print the classified diff
    py -3 backport_binding_index.py --diff --topaz-only    # only the "needs a look" bucket
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

TOPAZ_ROOT = Path(r"C:\topaz")
DSP_ROOT = Path(r"D:\Claude\old-dsp-reference")
DATA_DIR = Path(__file__).resolve().parent / "data"

TOPAZ_INDEX_PATH = DATA_DIR / "topaz_binding_index.json"
DSP_INDEX_PATH = DATA_DIR / "old_dsp_reference_binding_index.json"

SOL_REGISTER_RE = re.compile(r'SOL_REGISTER\(\s*"([A-Za-z_][A-Za-z0-9_]*)"\s*,\s*(\w+)::')
LUNAR_DECLARE_RE = re.compile(r"LUNAR_DECLARE_METHOD\(\s*(\w+)\s*,\s*([A-Za-z_][A-Za-z0-9_]*)\s*\)")


def _lua_binding_files(root: Path) -> list[Path]:
    d = root / "src/map/lua"
    return sorted(d.glob("*.cpp")) if d.is_dir() else []


def build_topaz_index(root: Path = TOPAZ_ROOT) -> dict[str, list[dict]]:
    """name -> [{class, file, line}, ...] (a name can be registered on more than one class,
    e.g. getID on both CLuaBaseEntity and CLuaInstance)."""
    index: dict[str, list[dict]] = {}
    for f in _lua_binding_files(root):
        text = f.read_text(encoding="utf-8", errors="replace")
        for m in SOL_REGISTER_RE.finditer(text):
            name, cls = m.group(1), m.group(2)
            line_no = text[:m.start()].count("\n") + 1
            index.setdefault(name, []).append({
                "class": cls, "file": f.relative_to(root).as_posix(), "line": line_no,
            })
    return index


def build_dsp_index(root: Path = DSP_ROOT) -> dict[str, list[dict]]:
    index: dict[str, list[dict]] = {}
    for f in _lua_binding_files(root):
        text = f.read_text(encoding="utf-8", errors="replace")
        for m in LUNAR_DECLARE_RE.finditer(text):
            cls, name = m.group(1), m.group(2)
            line_no = text[:m.start()].count("\n") + 1
            index.setdefault(name, []).append({
                "class": cls, "file": f.relative_to(root).as_posix(), "line": line_no,
            })
    return index


def save_indexes():
    DATA_DIR.mkdir(exist_ok=True)
    topaz_index = build_topaz_index()
    dsp_index = build_dsp_index()
    TOPAZ_INDEX_PATH.write_text(json.dumps(topaz_index, indent=2, sort_keys=True), encoding="utf-8")
    DSP_INDEX_PATH.write_text(json.dumps(dsp_index, indent=2, sort_keys=True), encoding="utf-8")
    print(f"Topaz: {len(topaz_index)} distinct binding names -> {TOPAZ_INDEX_PATH}")
    print(f"old-dsp-reference: {len(dsp_index)} distinct binding names -> {DSP_INDEX_PATH}")


def load_index(path: Path) -> dict[str, list[dict]]:
    if not path.exists():
        raise FileNotFoundError(f"{path} doesn't exist yet -- run with --build first")
    return json.loads(path.read_text(encoding="utf-8"))


def classify_diff() -> dict[str, list]:
    topaz = load_index(TOPAZ_INDEX_PATH)
    dsp = load_index(DSP_INDEX_PATH)
    dsp_lower = {name.lower(): name for name in dsp}

    exact, case_only, topaz_only = [], [], []
    for name in sorted(topaz):
        if name in dsp:
            exact.append(name)
        elif name.lower() in dsp_lower:
            case_only.append((name, dsp_lower[name.lower()]))
        else:
            topaz_only.append(name)
    return {"exact": exact, "case_only": case_only, "topaz_only": topaz_only}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--build", action="store_true", help="(Re)generate both cached indexes from real source")
    ap.add_argument("--diff", action="store_true", help="Print the classified Topaz-vs-old-dsp-reference diff")
    ap.add_argument("--topaz-only", action="store_true", help="With --diff, only print the topaz_only bucket")
    args = ap.parse_args()

    if args.build:
        save_indexes()

    if args.diff:
        result = classify_diff()
        print(f"\n{len(result['exact'])} exact matches (same name in both -- confirmed safe as-is)")
        print(f"{len(result['case_only'])} case-only mismatches (SAME NAME, different casing -- "
              f"high-confidence rename candidates, same bug class as SetAutoAttackEnabled/PrintToPlayer):")
        for topaz_name, dsp_name in result["case_only"]:
            print(f"  {topaz_name}  ->  {dsp_name}")
        if not args.topaz_only:
            print(f"\n{len(result['topaz_only'])} Topaz-only names (no match under any casing -- "
                  f"either old-dsp-reference spells it completely differently, or it's a real gap; "
                  f"this tool can't tell which, only that it needs a human/grep look):")
            for name in result["topaz_only"]:
                print(f"  {name}")
        else:
            print(f"\n{len(result['topaz_only'])} Topaz-only names (--topaz-only requested full list):")
            for name in result["topaz_only"]:
                print(f"  {name}")

    if not args.build and not args.diff:
        ap.error("Pass --build and/or --diff")


if __name__ == "__main__":
    main()
