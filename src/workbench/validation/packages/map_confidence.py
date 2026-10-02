"""Decay validation for namespace-map confirmed-pattern entries."""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from workbench.packages.migration import lua_convert as blc
from workbench.core.provenance import snapshot_id
from workbench.core.services.map_confidence_graph import import_map_confidence_results
from workbench.runtime.legacy_settings import get_dsp_root as _configured_dsp_root, get_topaz_root


def get_dsp_root() -> Path | None:
    configured = _configured_dsp_root()
    return configured if configured and configured.exists() else None


def collect_used_keys(topaz_root: Path, family: str) -> set[str]:
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


def run_checks(topaz_root: Path, dsp_root: Path, *, include_confirmed: bool = False, family: str | None = None) -> dict:
    ns_map = blc.load_map()
    target_confidences = {"confirmed_pattern", "confirmed"} if include_confirmed else {"confirmed_pattern"}
    results = []
    for family_name, spec in ns_map.get("simple_families", {}).items():
        if family_name.startswith("_"):
            continue
        if family and family_name != family:
            continue
        if spec.get("confidence") not in target_confidences:
            continue
        result = check_simple_family(topaz_root, dsp_root, family_name, spec)
        result["mapping_confidence"] = spec.get("confidence")
        results.append(result)
    return {
        "schema": 1,
        "source": str(topaz_root),
        "target": str(dsp_root),
        "results": results,
        "has_missing": any(result["missing"] for result in results),
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--all", action="store_true", help="Also check 'confirmed' families, not just 'confirmed_pattern'")
    ap.add_argument("--family", type=str, default=None, help="Limit to one simple_families family name")
    ap.add_argument("--json", type=Path, help="Optional machine-readable result output.")
    ap.add_argument("--graph-db", type=Path, help="Optionally import results into the canonical Workbench graph.")
    args = ap.parse_args()

    topaz_root = get_topaz_root()
    dsp_root = get_dsp_root()
    if dsp_root is None:
        print("ERROR: no DSP checkout found in configured settings", file=sys.stderr)
        sys.exit(2)

    payload = run_checks(topaz_root, dsp_root, include_confirmed=args.all, family=args.family)
    for result in payload["results"]:
        print(f"\n=== {result['family']} (confidence: {result['mapping_confidence']}, {result['used_count']} real key(s) used in Topaz) ===")
        if result["missing"]:
            print(f"  DECAY -- {len(result['missing'])} real used key(s) whose mapped DSP name was NOT found anywhere in DSP source:")
            for key, dsp_name in result["missing"]:
                print(f"    tpz.{result['family']}.{key} -> {dsp_name}  (not found)")
        else:
            print(f"  OK -- all {len(result['confirmed'])} real used key(s) resolve to a real DSP identifier")

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    if args.graph_db:
        import_map_confidence_results(
            payload["results"],
            args.graph_db,
            source=str(topaz_root),
            target=str(dsp_root),
            source_snapshot_id=snapshot_id(topaz_root),
            target_snapshot_id=snapshot_id(dsp_root),
        )

    if not payload["results"]:
        print("No matching families to check.")
        return
    if payload["has_missing"]:
        print("\nSome families have real DECAY -- verify those members before trusting converter output.")
        sys.exit(1)
    print("\nNo decay found in the checked families.")


if __name__ == "__main__":
    main()
