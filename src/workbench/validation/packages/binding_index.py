"""Validation-owned Lua binding cache, provenance, and source/target diff policy.

Deterministic C++ binding source inspection remains owned by
``workbench.devtools.server.binding_index``. This module adds the repository cache files,
cache provenance checks, and Topaz-vs-DSP name classification used by package validation.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from workbench.devtools.server import binding_index as source_index
from workbench.runtime.paths import DATA_ROOT

DATA_DIR = DATA_ROOT
TOPAZ_INDEX_PATH = DATA_DIR / "topaz_binding_index.json"
DSP_INDEX_PATH = DATA_DIR / "old_dsp_reference_binding_index.json"
TOPAZ_INDEX_META_PATH = DATA_DIR / "topaz_binding_index.meta.json"
DSP_INDEX_META_PATH = DATA_DIR / "old_dsp_reference_binding_index.meta.json"

SOL_REGISTER_RE = source_index.SOL_REGISTER_RE
LUNAR_DECLARE_RE = source_index.LUNAR_DECLARE_RE
_lua_binding_files = source_index.lua_binding_files
binding_source_fingerprint = source_index.binding_source_fingerprint
build_topaz_index = source_index.build_topaz_index
build_dsp_index = source_index.build_dsp_index


def write_index_metadata(path: Path, root: Path, binding_count: int) -> None:
    payload = {
        "schema": 1,
        "source_fingerprint": binding_source_fingerprint(root),
        "binding_file_count": len(_lua_binding_files(root)),
        "binding_name_count": binding_count,
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def cache_matches_root(meta_path: Path, root: Path) -> bool:
    if not meta_path.exists():
        return False
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    expected = meta.get("source_fingerprint")
    return bool(expected) and expected == binding_source_fingerprint(root)


def save_indexes(topaz_root: Path, dsp_root: Path | None) -> None:
    if dsp_root is None:
        raise SystemExit(
            "No DSP checkout configured -- set it on the Settings page (dsp_server_path) or "
            "pass --dsp-root."
        )
    DATA_DIR.mkdir(exist_ok=True)
    topaz_index = build_topaz_index(topaz_root)
    dsp_index = build_dsp_index(dsp_root)
    TOPAZ_INDEX_PATH.write_text(json.dumps(topaz_index, indent=2, sort_keys=True), encoding="utf-8")
    DSP_INDEX_PATH.write_text(json.dumps(dsp_index, indent=2, sort_keys=True), encoding="utf-8")
    write_index_metadata(TOPAZ_INDEX_META_PATH, topaz_root, len(topaz_index))
    write_index_metadata(DSP_INDEX_META_PATH, dsp_root, len(dsp_index))
    print(f"Topaz: {len(topaz_index)} distinct binding names -> {TOPAZ_INDEX_PATH}")
    print(f"old-dsp-reference: {len(dsp_index)} distinct binding names -> {DSP_INDEX_PATH}")


def load_index(path: Path) -> dict[str, list[dict]]:
    if not path.exists():
        raise FileNotFoundError(f"{path} doesn't exist yet -- run with --build first")
    return json.loads(path.read_text(encoding="utf-8"))


def classify_diff(
    topaz_path: Path = TOPAZ_INDEX_PATH,
    dsp_path: Path = DSP_INDEX_PATH,
) -> dict[str, list]:
    topaz = load_index(topaz_path)
    dsp = load_index(dsp_path)
    dsp_lower = {name.lower(): name for name in dsp}

    exact: list[str] = []
    case_only: list[tuple[str, str]] = []
    topaz_only: list[str] = []
    for name in sorted(topaz):
        if name in dsp:
            exact.append(name)
        elif name.lower() in dsp_lower:
            case_only.append((name, dsp_lower[name.lower()]))
        else:
            topaz_only.append(name)
    return {"exact": exact, "case_only": case_only, "topaz_only": topaz_only}


def main() -> None:
    import settings

    topaz_root = settings.get_topaz_root()
    dsp_root = settings.get_dsp_root()

    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--build", action="store_true", help="(Re)generate both cached indexes from real source")
    ap.add_argument("--diff", action="store_true", help="Print the classified Topaz-vs-old-dsp-reference diff")
    ap.add_argument("--topaz-only", action="store_true", help="With --diff, only print the topaz_only bucket")
    ap.add_argument("--topaz-root", type=Path, default=topaz_root, help="Override Settings' Topaz path")
    ap.add_argument("--dsp-root", type=Path, default=dsp_root, help="Override Settings' DSP path")
    args = ap.parse_args()

    if args.build:
        save_indexes(args.topaz_root, args.dsp_root)

    if args.diff:
        result = classify_diff()
        print(f"\n{len(result['exact'])} exact matches (same name in both -- confirmed safe as-is)")
        print(f"{len(result['case_only'])} case-only mismatches:")
        for topaz_name, dsp_name in result["case_only"]:
            print(f"  {topaz_name}  ->  {dsp_name}")
        print(f"\n{len(result['topaz_only'])} Topaz-only names:")
        for name in result["topaz_only"]:
            print(f"  {name}")

    if not args.build and not args.diff:
        ap.error("Pass --build and/or --diff")


if __name__ == "__main__":
    main()
