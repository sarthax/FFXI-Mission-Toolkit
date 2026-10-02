#!/usr/bin/env python3
r"""Package item/content validation for legacy DSP targets."""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

LINE_COMMENT_RE = re.compile(r"--(?!\[\[).*$", re.MULTILINE)
BLOCK_COMMENT_RE = re.compile(r"--\[\[.*?\]\]", re.DOTALL)
ITEM_CONST_RE = re.compile(r"local\s+[A-Z][A-Z0-9_]*_ITEM\w*\s*=\s*(\d+)")
ITEM_CALL_RE = re.compile(r"\b(?:addItem|addTempItem|giveItem|hasItem|hasItemQty|tradeHas|addTreasure|delItem)\(\s*(?:player,\s*)?(\d+)")
KEYITEM_CALL_RE = re.compile(r"\b(?:hasKeyItem|addKeyItem|delKeyItem)\(\s*([A-Z][A-Z0-9_]*)\s*\)|\bgiveKeyItem\(\s*player,\s*([A-Z][A-Z0-9_]*)\s*\)")
REQUIRE_RE = re.compile(r'require\(\s*"([^"]+)"\s*\)')
BAD_CALL_SHAPE_RE = re.compile(r"GetNPCByID\([^,()]+,\s*instance\)")
_ITEM_BASIC_ROW_RE = re.compile(r"INSERT INTO `item_basic` VALUES \((\d+),\d+,'([^']*)'")
_KEYITEM_DECL_RE = re.compile(r"^\s*([A-Z][A-Z0-9_]*)\s*=", re.MULTILINE)


def _strip_comments(text: str) -> str:
    return LINE_COMMENT_RE.sub("", BLOCK_COMMENT_RE.sub("", text))


def collect_item_ids(pkg_lua_dsp: Path) -> dict[int, list[Path]]:
    ids: dict[int, list[Path]] = {}
    for f in pkg_lua_dsp.rglob("*.lua"):
        text = _strip_comments(f.read_text(encoding="utf-8", errors="replace"))
        found = {int(m) for m in ITEM_CONST_RE.findall(text)} | {int(m) for m in ITEM_CALL_RE.findall(text)}
        for item_id in found:
            ids.setdefault(item_id, []).append(f)
    return ids


def collect_keyitem_names(pkg_lua_dsp: Path) -> dict[str, list[Path]]:
    names: dict[str, list[Path]] = {}
    for f in pkg_lua_dsp.rglob("*.lua"):
        for a, b in KEYITEM_CALL_RE.findall(_strip_comments(f.read_text(encoding="utf-8", errors="replace"))):
            names.setdefault(a or b, []).append(f)
    return names


def collect_requires(pkg_lua_dsp: Path) -> dict[str, list[Path]]:
    paths: dict[str, list[Path]] = {}
    for f in pkg_lua_dsp.rglob("*.lua"):
        for req in REQUIRE_RE.findall(_strip_comments(f.read_text(encoding="utf-8", errors="replace"))):
            paths.setdefault(req, []).append(f)
    return paths


def load_item_basic(dsp_root: Path) -> dict[int, str]:
    sql_path = dsp_root / "sql" / "item_basic.sql"
    if not sql_path.is_file():
        return {}
    text = sql_path.read_text(encoding="utf-8", errors="replace")
    return {int(i): name for i, name in _ITEM_BASIC_ROW_RE.findall(text)}


def load_keyitem_names(dsp_root: Path) -> set[str]:
    path = dsp_root / "scripts" / "globals" / "keyitems.lua"
    if not path.is_file():
        return set()
    return set(_KEYITEM_DECL_RE.findall(path.read_text(encoding="utf-8", errors="replace")))


def resolve_require(req_path: str, pkg_lua_dsp: Path, dsp_root: Path) -> str | None:
    if not req_path.startswith("scripts/"):
        return None
    rel = Path(req_path + ".lua")
    if (pkg_lua_dsp / rel).is_file() or (dsp_root / rel).is_file():
        return None
    return f"not found in package lua-dsp/ or in {dsp_root.name}"


def audit_package(pkg_lua_dsp: Path, dsp_root: Path) -> dict:
    item_basic = load_item_basic(dsp_root)
    keyitem_names = load_keyitem_names(dsp_root)
    items_dir = dsp_root / "scripts" / "globals" / "items"

    missing_item_rows, missing_item_scripts = [], []
    for item_id, files in sorted(collect_item_ids(pkg_lua_dsp).items()):
        real_name = item_basic.get(item_id)
        if real_name is None:
            missing_item_rows.append((item_id, files))
            continue
        if not (items_dir / f"{real_name}.lua").is_file():
            missing_item_scripts.append((item_id, real_name, files))

    missing_keyitems = [
        (name, files)
        for name, files in sorted(collect_keyitem_names(pkg_lua_dsp).items())
        if name not in keyitem_names
    ]

    dangling_requires = []
    for req_path, files in sorted(collect_requires(pkg_lua_dsp).items()):
        reason = resolve_require(req_path, pkg_lua_dsp, dsp_root)
        if reason:
            dangling_requires.append((req_path, reason, files))

    bad_call_shapes = []
    for f in pkg_lua_dsp.rglob("*.lua"):
        text = _strip_comments(f.read_text(encoding="utf-8", errors="replace"))
        bad_call_shapes.extend((m.group(0), f) for m in BAD_CALL_SHAPE_RE.finditer(text))

    return {
        "missing_item_rows": missing_item_rows,
        "missing_item_scripts": missing_item_scripts,
        "missing_keyitems": missing_keyitems,
        "dangling_requires": dangling_requires,
        "bad_call_shapes": bad_call_shapes,
    }


def _fmt_files(files: list[Path], base: Path) -> str:
    names = [f.relative_to(base).as_posix() for f in files[:3]]
    more = f" (+{len(files) - 3} more)" if len(files) > 3 else ""
    return ", ".join(names) + more


def _default_paths() -> tuple[Path, Path | None]:
    import settings
    return settings.get_backport_root() / "mission-packages", settings.get_dsp_root()


def main() -> None:
    packages_root, dsp_default = _default_paths()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("path", nargs="?", help="A lua-dsp/ directory to audit")
    ap.add_argument("--all-packages", action="store_true")
    ap.add_argument("--dsp-root", default=str(dsp_default) if dsp_default else None)
    ap.add_argument("--packages-root", default=str(packages_root))
    args = ap.parse_args()
    if not args.dsp_root:
        ap.error("No DSP checkout configured -- set Settings' dsp_server_path or pass --dsp-root.")
    dsp_root = Path(args.dsp_root)
    if not (dsp_root / "sql" / "item_basic.sql").is_file():
        print(f"error: {dsp_root} has no sql/item_basic.sql -- not a real DSP checkout?", file=sys.stderr)
        raise SystemExit(2)
    if args.all_packages:
        targets = sorted(Path(args.packages_root).glob("*/lua-dsp"))
    elif args.path:
        targets = [Path(args.path)]
    else:
        ap.error("Provide a path or --all-packages")

    any_errors = False
    for target in targets:
        if not target.exists():
            continue
        result = audit_package(target, dsp_root)
        n_errors = sum(len(result[k]) for k in ("missing_item_rows", "missing_keyitems", "dangling_requires", "bad_call_shapes"))
        any_errors |= bool(n_errors)
        print(f"=== {target.parent.name} === ({n_errors} error(s), {len(result['missing_item_scripts'])} item-script warning(s))")
        for item_id, files in result["missing_item_rows"]:
            print(f"  MISSING DB ROW item id {item_id} [{_fmt_files(files, target)}]")
        for name, files in result["missing_keyitems"]:
            print(f"  MISSING KEYITEM {name} [{_fmt_files(files, target)}]")
        for req_path, reason, files in result["dangling_requires"]:
            print(f"  DANGLING REQUIRE {req_path} -- {reason} [{_fmt_files(files, target)}]")
        for call, f in result["bad_call_shapes"]:
            print(f"  BAD CALL SHAPE {call} [{f.relative_to(target).as_posix()}]")
    if any_errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
