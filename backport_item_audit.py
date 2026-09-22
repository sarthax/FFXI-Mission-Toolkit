#!/usr/bin/env python3
r"""
backport_item_audit.py -- mechanizes the manual sweep done by hand this session (2026-09-14) that
found: 20 of 25 real Nyzul Isle vending-box items had no usable-item script in old-dsp-reference,
5 of 5 Assault zones needed their own "give up" Fireflies item (3 were missing), and one package's
Mining_Point.lua required() a shared helper module that was never actually shipped with it (a
live-crashing dangling require, only caught by tracing a `require()` chain by hand). This turns
that three-part manual sweep into one repeatable command instead of a fresh by-hand pass for every
new package.

Checks three real gap classes a package's own `lua-dsp/` tree can hide, none of which
backport_binding_audit.py or backport_lua_sanity_check.py catch (those check *bindings* and
*declared-vs-referenced bare globals* -- this checks *data/content* a real binding/global still
needs to actually work):

1. **Item ids with no DB row** -- every numeric item id referenced (local `*_ITEM = NNN`
   constants, and literal-id calls to addItem/addTempItem/giveItem/hasItem/hasItemQty/tradeHas/
   addTreasure/delItem) is checked against the real target's `sql/item_basic.sql`. A referenced id
   with no row is a hard error -- the item doesn't exist at all server-side.
2. **Item ids with no usable-item script** -- same id set, checked against
   `scripts/globals/items/<name>.lua` (name resolved via the DB row found in check 1). Reported as
   a warning, not an error: plenty of real item ids (turn-in materials, trade fodder) are never
   `onItemUse`'d and genuinely don't need a script -- a human has to judge each one, same as this
   session's own manual pass did.
3. **Key items with no keyitems.lua entry** -- every bare name passed to
   hasKeyItem/addKeyItem/delKeyItem/giveKeyItem is checked against the real target's
   `scripts/globals/keyitems.lua`.
4. **Dangling require()s** -- every `require("scripts/...")` path in the package is checked to
   resolve to a real .lua file either inside the package's own lua-dsp/ tree OR in the real DSP
   checkout -- catches the exact Mining_Point.lua/counting_sheep_common class of bug (a shared
   module referenced but never shipped with the package, live-crashing on first use).

Usage:
    py -3 backport_item_audit.py mission-packages/nyzul_isle_investigation/lua-dsp
    py -3 backport_item_audit.py --all-packages
    py -3 backport_item_audit.py --all-packages --dsp-root D:\Claude\old-dsp-reference
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import settings

DEFAULT_PACKAGES_ROOT = settings.get_backport_root() / "mission-packages"
DEFAULT_DSP_ROOT = settings.get_dsp_root()

LINE_COMMENT_RE = re.compile(r"--(?!\[\[).*$", re.MULTILINE)
BLOCK_COMMENT_RE = re.compile(r"--\[\[.*?\]\]", re.DOTALL)


def _strip_comments(text: str) -> str:
    text = BLOCK_COMMENT_RE.sub("", text)
    text = LINE_COMMENT_RE.sub("", text)
    return text


# `local FOO_ITEM = 1234` / `local FOO_ITEM      = 1234` -- this project's own established naming
# convention for a literal item id (see vending_box.lua, Mining_Point.lua, etc.), plus direct
# literal-id calls into the small set of real item-taking bindings this project's packages
# actually use. Deliberately NOT matching every numeric literal in a file -- that would flag CSIDs,
# durations, percentages, etc. as false "item ids".
ITEM_CONST_RE = re.compile(r"local\s+[A-Z][A-Z0-9_]*_ITEM\w*\s*=\s*(\d+)")
ITEM_CALL_RE = re.compile(
    r"\b(?:addItem|addTempItem|giveItem|hasItem|hasItemQty|tradeHas|addTreasure|delItem)"
    r"\(\s*(?:player,\s*)?(\d+)"
)

KEYITEM_CALL_RE = re.compile(
    r"\b(?:hasKeyItem|addKeyItem|delKeyItem)\(\s*([A-Z][A-Z0-9_]*)\s*\)"
    r"|\bgiveKeyItem\(\s*player,\s*([A-Z][A-Z0-9_]*)\s*\)"
)

REQUIRE_RE = re.compile(r'require\(\s*"([^"]+)"\s*\)')

# Known real API-shape landmines: a function that exists with the SAME NAME on both Topaz and
# old-dsp-reference, but takes genuinely different real argument types -- backport_binding_audit.py
# cannot catch this class of bug at all (it only checks the binding NAME exists, never the argument
# shape). GetNPCByID(id, instance) is the first confirmed case (2026-09-14, found via a live
# map-server crash across 37 files/193 call sites before this check existed) -- see
# data/dsp_namespace_map.json's call_reshapes entry for the full real evidence. Add future
# confirmed shape-mismatch cases here the same way.
BAD_CALL_SHAPE_RE = re.compile(r"GetNPCByID\([^,()]+,\s*instance\)")


def collect_item_ids(pkg_lua_dsp: Path) -> dict[int, list[Path]]:
    """Real item id -> files that reference it."""
    ids: dict[int, list[Path]] = {}
    for f in pkg_lua_dsp.rglob("*.lua"):
        text = _strip_comments(f.read_text(encoding="utf-8", errors="replace"))
        found = set(int(m) for m in ITEM_CONST_RE.findall(text))
        found |= set(int(m) for m in ITEM_CALL_RE.findall(text))
        for i in found:
            ids.setdefault(i, []).append(f)
    return ids


def collect_keyitem_names(pkg_lua_dsp: Path) -> dict[str, list[Path]]:
    names: dict[str, list[Path]] = {}
    for f in pkg_lua_dsp.rglob("*.lua"):
        text = _strip_comments(f.read_text(encoding="utf-8", errors="replace"))
        for a, b in KEYITEM_CALL_RE.findall(text):
            name = a or b
            names.setdefault(name, []).append(f)
    return names


def collect_requires(pkg_lua_dsp: Path) -> dict[str, list[Path]]:
    paths: dict[str, list[Path]] = {}
    for f in pkg_lua_dsp.rglob("*.lua"):
        text = _strip_comments(f.read_text(encoding="utf-8", errors="replace"))
        for req in REQUIRE_RE.findall(text):
            paths.setdefault(req, []).append(f)
    return paths


_ITEM_BASIC_ROW_RE = re.compile(r"INSERT INTO `item_basic` VALUES \((\d+),\d+,'([^']*)'")


def load_item_basic(dsp_root: Path) -> dict[int, str]:
    """Real item id -> real DB `name` column (the exact string scripts/globals/items/<name>.lua
    must match), parsed fresh from the target's own sql/item_basic.sql every run -- never cached,
    since this file is exactly the kind of thing that changes as gaps get closed."""
    sql_path = dsp_root / "sql" / "item_basic.sql"
    if not sql_path.is_file():
        return {}
    text = sql_path.read_text(encoding="utf-8", errors="replace")
    return {int(i): name for i, name in _ITEM_BASIC_ROW_RE.findall(text)}


_KEYITEM_DECL_RE = re.compile(r"^\s*([A-Z][A-Z0-9_]*)\s*=", re.MULTILINE)


def load_keyitem_names(dsp_root: Path) -> set[str]:
    path = dsp_root / "scripts" / "globals" / "keyitems.lua"
    if not path.is_file():
        return set()
    text = path.read_text(encoding="utf-8", errors="replace")
    return set(_KEYITEM_DECL_RE.findall(text))


def resolve_require(req_path: str, pkg_lua_dsp: Path, dsp_root: Path) -> str | None:
    """Returns None if `req_path` (a `require("scripts/...")` argument) resolves to a real .lua
    file either inside the package's own lua-dsp/ tree or in the real DSP checkout -- otherwise
    returns a short reason string. Skips non-scripts/ requires (e.g. a bare module name) since
    those aren't this project's own path convention and would just be noise."""
    if not req_path.startswith("scripts/"):
        return None
    rel = Path(req_path + ".lua")
    if (pkg_lua_dsp / rel).is_file():
        return None
    if (dsp_root / rel).is_file():
        return None
    return f"not found in package lua-dsp/ or in {dsp_root.name}"


def audit_package(pkg_lua_dsp: Path, dsp_root: Path) -> dict:
    item_basic = load_item_basic(dsp_root)
    keyitem_names = load_keyitem_names(dsp_root)
    items_dir = dsp_root / "scripts" / "globals" / "items"

    item_ids = collect_item_ids(pkg_lua_dsp)
    missing_item_rows, missing_item_scripts = [], []
    for item_id, files in sorted(item_ids.items()):
        real_name = item_basic.get(item_id)
        if real_name is None:
            missing_item_rows.append((item_id, files))
            continue
        if not (items_dir / f"{real_name}.lua").is_file():
            missing_item_scripts.append((item_id, real_name, files))

    keyitem_refs = collect_keyitem_names(pkg_lua_dsp)
    missing_keyitems = [(name, files) for name, files in sorted(keyitem_refs.items())
                         if name not in keyitem_names]

    requires = collect_requires(pkg_lua_dsp)
    dangling_requires = []
    for req_path, files in sorted(requires.items()):
        reason = resolve_require(req_path, pkg_lua_dsp, dsp_root)
        if reason:
            dangling_requires.append((req_path, reason, files))

    bad_call_shapes = []
    for f in pkg_lua_dsp.rglob("*.lua"):
        text = _strip_comments(f.read_text(encoding="utf-8", errors="replace"))
        for m in BAD_CALL_SHAPE_RE.finditer(text):
            bad_call_shapes.append((m.group(0), f))

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


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("path", nargs="?", help="A lua-dsp/ directory to audit")
    ap.add_argument("--all-packages", action="store_true", help="Audit every mission-packages/*/lua-dsp/ tree")
    ap.add_argument("--dsp-root", default=str(DEFAULT_DSP_ROOT) if DEFAULT_DSP_ROOT else None,
                     help="Real DSP checkout to check against (else Settings' dsp_server_path)")
    ap.add_argument("--packages-root", default=str(DEFAULT_PACKAGES_ROOT),
                     help="mission-packages/ root for --all-packages")
    args = ap.parse_args()

    if not args.dsp_root:
        ap.error("No DSP checkout configured -- set Settings' dsp_server_path or pass --dsp-root.")
    dsp_root = Path(args.dsp_root)
    if not (dsp_root / "sql" / "item_basic.sql").is_file():
        print(f"error: {dsp_root} has no sql/item_basic.sql -- not a real DSP checkout?", file=sys.stderr)
        sys.exit(2)
    print(f"Target: {dsp_root}\n")

    if args.all_packages:
        targets = sorted(Path(args.packages_root).glob("*/lua-dsp"))
    elif args.path:
        targets = [Path(args.path)]
    else:
        ap.error("Provide a path or --all-packages")
        return

    any_errors = False
    for target in targets:
        if not target.exists():
            print(f"=== {target} === NOT FOUND, skipping")
            continue
        result = audit_package(target, dsp_root)
        pkg_name = target.parent.name
        n_problems = (len(result["missing_item_rows"]) + len(result["missing_keyitems"])
                      + len(result["dangling_requires"]) + len(result["bad_call_shapes"]))
        print(f"=== {pkg_name} === ({n_problems} error(s), "
              f"{len(result['missing_item_scripts'])} item-script warning(s))")

        for item_id, files in result["missing_item_rows"]:
            any_errors = True
            print(f"  MISSING DB ROW    item id {item_id} has no sql/item_basic.sql row at all "
                  f"[referenced in: {_fmt_files(files, target)}]")
        for name, files in result["missing_keyitems"]:
            any_errors = True
            print(f"  MISSING KEYITEM   `{name}` has no scripts/globals/keyitems.lua entry "
                  f"[referenced in: {_fmt_files(files, target)}]")
        for req_path, reason, files in result["dangling_requires"]:
            any_errors = True
            print(f"  DANGLING REQUIRE  require(\"{req_path}\") -- {reason} "
                  f"[referenced in: {_fmt_files(files, target)}]")
        for call, f in result["bad_call_shapes"]:
            any_errors = True
            print(f"  BAD CALL SHAPE    `{call}` -- known Topaz/DSP API shape mismatch, will crash "
                  f"live (see data/dsp_namespace_map.json call_reshapes) [in: {f.relative_to(target).as_posix()}]")
        for item_id, real_name, files in result["missing_item_scripts"]:
            print(f"  no item script    item id {item_id} ({real_name}) has a DB row but no "
                  f"scripts/globals/items/{real_name}.lua -- verify by hand whether it needs one "
                  f"(a plain trade/turn-in material usually doesn't) "
                  f"[referenced in: {_fmt_files(files, target)}]")

        if n_problems == 0 and not result["missing_item_scripts"]:
            print("  clean")

    if any_errors:
        print("\n*** real gaps found (missing DB rows / keyitems / dangling requires) -- these "
              "will crash or silently no-op at runtime, fix before a live test ***")
        sys.exit(1)


if __name__ == "__main__":
    main()
