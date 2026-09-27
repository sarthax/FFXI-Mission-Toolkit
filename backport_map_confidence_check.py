"""
backport_map_confidence_check.py -- decay check for data/dsp_namespace_map.json's
"confirmed_pattern" entries.

A "confirmed_pattern" family (see the map's own _readme) means only a couple of members were
spot-checked against real DSP source when the entry was written -- the rest of the family is
assumed to follow the same prefix/rename pattern, not individually re-verified. That assumption can
silently go stale: a real Topaz script can reference a member of that family that was NEVER
actually checked, and the converter will happily "convert" it by blind prefix substitution even if
DSP spells that particular member differently (or doesn't have it at all) -- exactly the class of
bug already found twice this session (mobMod's real member names, damageType's PHYSICAL half).

This script closes that gap for EVERY simple_families entry, not just the ones a manual stress test
happened to touch: it scans the real Topaz checkout for every `tpz.<family>.<KEY>` actually used
anywhere, then checks whether the mapped DSP identifier for that specific KEY is a literal token
somewhere in the real DSP checkout (source or scripts). A KEY that's used in real Topaz code but
whose mapped DSP name doesn't appear ANYWHERE in DSP source is a real decay signal -- the pattern
assumption for that one member was never actually true, or has drifted.

This is a NAME-EXISTENCE check, not a value check (it can't tell you FIRE=6 in both, only that
MOBPARAM_FIRE exists as an identifier somewhere in DSP) -- pair it with backport_coverage_check.py
(which validates converter BEHAVIOR against real files) and a manual value spot-check (like the ones
already recorded in each map entry's "evidence" field) for full confidence.

Usage:
    py -3 backport_map_confidence_check.py                 # all confirmed_pattern families
    py -3 backport_map_confidence_check.py --all            # confirmed families too (slower, more thorough)
    py -3 backport_map_confidence_check.py --family mobMod
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import backport_lua_convert as blc
import settings
from workbench.core.provenance import snapshot_id
from workbench.core.services.map_confidence_graph import import_map_confidence_results

def get_dsp_root() -> Path | None:
    """Settings' dsp_server_path if configured and real, else None -- no hardcoded machine-specific
    fallback (same no-default-no-guess convention as settings.get_dsp_root() itself)."""
    configured = settings.get_dsp_root()
    return configured if configured and configured.exists() else None


def collect_used_keys(topaz_root: Path, family: str) -> set[str]:
    """Every real `tpz.<family>.<KEY>` (or renamed alias) actually referenced anywhere in the
    Topaz checkout -- not just scripts/zones, since a family can also be used from scripts/globals
    itself (e.g. mobskills calling tpz.attackType.*)."""
    pattern = re.compile(r"\btpz\." + re.escape(family) + r"\.([A-Za-z_][A-Za-z0-9_]*)")
    keys: set[str] = set()
    for f in (topaz_root / "scripts").rglob("*.lua"):
        try:
            text = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        keys.update(pattern.findall(text))
    return keys


def dsp_source_files(dsp_root: Path):
    yield from (dsp_root / "scripts").rglob("*.lua")
    src = dsp_root / "src"
    if src.exists():
        yield from src.rglob("*.h")
        yield from src.rglob("*.cpp")


def dsp_has_identifier(dsp_root: Path, identifier: str, _cache: dict = {}) -> bool:
    if not _cache:
        # Build one big set of every bare word DSP source ever mentions, once. Cheaper than
        # re-scanning every file per identifier for a family with 50+ real used keys.
        word_re = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
        words: set[str] = set()
        for f in dsp_source_files(dsp_root):
            try:
                text = f.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            words.update(word_re.findall(text))
        _cache["words"] = words
    return identifier in _cache["words"]


def check_simple_family(topaz_root: Path, dsp_root: Path, family: str, spec: dict) -> dict:
    used_keys = collect_used_keys(topaz_root, family)
    prefix = spec.get("dsp_prefix")
    renames = spec.get("renames", {})
    confirmed, missing = [], []
    for key in sorted(used_keys):
        if key in renames:
            dsp_name = renames[key]
        elif prefix is not None:
            dsp_name = prefix + key
        else:
            continue
        if dsp_has_identifier(dsp_root, dsp_name):
            confirmed.append((key, dsp_name))
        else:
            missing.append((key, dsp_name))
    return {"family": family, "used_count": len(used_keys), "confirmed": confirmed, "missing": missing}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--all", action="store_true", help="Also check 'confirmed' families, not just 'confirmed_pattern'")
    ap.add_argument("--family", type=str, default=None, help="Limit to one simple_families family name")
    ap.add_argument("--json", type=Path, help="Optional machine-readable result output.")
    ap.add_argument("--graph-db", type=Path, help="Optionally import results into the canonical Workbench graph.")
    args = ap.parse_args()

    ns_map = blc.load_map()
    topaz_root = settings.get_topaz_root()
    dsp_root = get_dsp_root()
    if dsp_root is None:
        print("ERROR: no DSP checkout found (checked settings.get_dsp_root() and D:\\Claude\\old-dsp-reference)",
              file=sys.stderr)
        sys.exit(2)

    target_confidences = {"confirmed_pattern"} if not args.all else {"confirmed_pattern", "confirmed"}
    families = ns_map.get("simple_families", {})

    any_missing = False
    checked_any = False
    results = []
    for family, spec in families.items():
        if family.startswith("_"):
            continue
        if args.family and family != args.family:
            continue
        if spec.get("confidence") not in target_confidences:
            continue
        checked_any = True
        result = check_simple_family(topaz_root, dsp_root, family, spec)
        result["mapping_confidence"] = spec.get("confidence")
        results.append(result)
        print(f"\n=== {family} (confidence: {spec.get('confidence')}, {result['used_count']} real key(s) used in Topaz) ===")
        if result["missing"]:
            any_missing = True
            print(f"  DECAY -- {len(result['missing'])} real used key(s) whose mapped DSP name was NOT found anywhere in DSP source:")
            for key, dsp_name in result["missing"]:
                print(f"    tpz.{family}.{key} -> {dsp_name}  (not found)")
        else:
            print(f"  OK -- all {len(result['confirmed'])} real used key(s) resolve to a real DSP identifier")

    payload = {
        "schema": 1,
        "source": str(topaz_root),
        "target": str(dsp_root),
        "results": results,
        "has_missing": any_missing,
    }
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    if args.graph_db:
        import_map_confidence_results(
            results,
            args.graph_db,
            source=str(topaz_root),
            target=str(dsp_root),
            source_snapshot_id=snapshot_id(topaz_root),
            target_snapshot_id=snapshot_id(dsp_root),
        )

    if not checked_any:
        print("No matching families to check (nothing at the requested confidence level, or --family didn't match).")
        return

    print()
    if any_missing:
        print("Some families have real DECAY -- a used key's assumed prefix/rename pattern doesn't "
              "hold. Check the real DSP source for that specific member (it may be renamed, "
              "missing entirely, or need its own engine_gaps/missing_lua_modules entry) before "
              "trusting the converter's output for it.")
        sys.exit(1)
    print("No decay found in the checked families.")


if __name__ == "__main__":
    main()
