#!/usr/bin/env python3
r"""
backport_binding_audit.py -- mechanizes the manual process used repeatedly this session to find
every invented/mis-cased binding (SetAutoAttackEnabled, addCharVar, getShortID, setName,
PrintToPlayer, goToEntity, untargetable...): extract every `:method(` call in a package's lua-dsp/
output, then grep the real target checkout to confirm each one actually exists. Every one of those
bugs was found this way, one at a time, by hand -- this turns that into one command instead of a
fresh manual audit for the next zone.

Only checks method-style calls (`entity:methodName(...)`), the class every real bug this session
was. Bare global function calls (`GetMobByID(...)`, `tpz.*`/namespace-family references) are a
different check -- see backport_map_confidence_check.py for family-level decay checking, and
backport_lua_sanity_check.py for the declared-vs-referenced-global class of bug.

Target flavor is auto-detected via backport_lua_convert.detect_target_flavor() -- refuses to
guess if the checkout doesn't fingerprint as one of the two known flavors, since a binding
"confirmed" against the wrong codebase is exactly the mistake this project already made once.

Uses backport_binding_index.py's cached DSP-side index (data/old_dsp_reference_binding_index.json)
when present, instead of re-grepping every src/map/lua/*.cpp file on every single lookup --
falls back to a live grep automatically if the cache is missing (e.g. --build was never run, or
a different --dsp-root is passed than what the cache was built from) so this never silently goes
stale-but-fast; run `py -3 backport_binding_index.py --build` after any real DSP engine change
to refresh it.

Usage:
    py -3 backport_binding_audit.py mission-packages/periqia_missions_1-4/lua-dsp
    py -3 backport_binding_audit.py --all-packages
    py -3 backport_binding_audit.py --all-packages --dsp-root D:\Claude\old-dsp-reference
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import backport_binding_index as bbi

import backport_lua_convert as blc

PACKAGES_ROOT = Path(r"D:\Claude\Topaz-Assault-Backport\mission-packages")
DEFAULT_DSP_ROOT = Path(r"D:\Claude\old-dsp-reference")

METHOD_CALL_RE = re.compile(r":([A-Za-z_][A-Za-z0-9_]*)\s*\(")

# Bindings confirmed by other means (e.g. Lua-side globals like math.random, string.format) that
# would otherwise false-positive as "not found in C++ source" -- not an exhaustive stdlib list,
# just names actually seen causing noise while building this tool.
KNOWN_NON_ENTITY_METHODS = {"format", "find", "gsub", "match", "sub", "upper", "lower", "insert",
                            "remove", "sort", "concat", "gmatch"}


LINE_COMMENT_RE = re.compile(r"--(?!\[\[).*$", re.MULTILINE)
BLOCK_COMMENT_RE = re.compile(r"--\[\[.*?\]\]", re.DOTALL)


def _strip_comments(text: str) -> str:
    """Real false-positive source found while building this tool: a prose comment describing real
    C++ (`CBaseEntity::GetName()`, `STATUS_TYPE::MOB(1)`) matches the same `:name(`-shaped regex
    as an actual Lua colon-call, since C++'s `::` contains a single `:` too. Strip both comment
    styles before scanning -- never scan raw source text for a call-shaped pattern."""
    text = BLOCK_COMMENT_RE.sub("", text)
    text = LINE_COMMENT_RE.sub("", text)
    return text


def collect_method_calls(pkg_lua_dsp: Path) -> dict[str, list[Path]]:
    """method name -> list of files that call it (colon-call syntax only)."""
    calls: dict[str, list[Path]] = {}
    for f in pkg_lua_dsp.rglob("*.lua"):
        text = _strip_comments(f.read_text(encoding="utf-8", errors="replace"))
        for name in set(METHOD_CALL_RE.findall(text)):
            if name in KNOWN_NON_ENTITY_METHODS:
                continue
            calls.setdefault(name, []).append(f)
    return calls


def _lua_binding_files(dsp_root: Path) -> list[Path]:
    """Every real class-binding source file under src/map/lua/ -- bindings are split across
    several Lunar/sol2-bound classes (CLuaBaseEntity, CLuaInstance, CLuaZone, CLuaItem, ...), not
    just the entity one. A first version of this tool only checked lua_baseentity.cpp and produced
    a pile of false "missing" results for real CLuaInstance methods (getChars, setProgress, fail,
    complete...) -- checking every file in the directory is the real fix, not narrowing further."""
    d = dsp_root / "src/map/lua"
    return sorted(d.glob("*.cpp")) if d.is_dir() else []


def _load_cached_index(dsp_root: Path, flavor: str) -> dict[str, list[dict]] | None:
    """Returns the cached index if it exists AND was built from this same dsp_root (checked via
    one real file's path recorded in the index -- a cache built from a different checkout at the
    same flavor would silently give wrong answers otherwise, e.g. a differently-patched fork).
    None if unusable for any reason -- callers fall back to a live grep, never guess."""
    if flavor != "old_dsp_reference":
        return None  # only old-dsp-reference has a cache built by default; landsandboat is reference-only
    try:
        index = bbi.load_index(bbi.DSP_INDEX_PATH)
    except FileNotFoundError:
        return None
    # Sanity check: every recorded file path should actually exist under dsp_root.
    for entries in list(index.values())[:3]:
        if entries and not (dsp_root / entries[0]["file"]).exists():
            return None
    return index


def check_binding(name: str, dsp_root: Path, flavor: str, cached_index: dict | None = None) -> tuple[bool, str]:
    """Returns (found, evidence_or_reason). Uses the cached index (backport_binding_index.py) when
    available and confirmed built from this same dsp_root; otherwise searches every real
    class-binding source file directly for the detected flavor's own registration macro/call --
    LUNAR_DECLARE_METHOD(AnyClass,name) for old_dsp_reference, SOL_REGISTER("name", for
    landsandboat -- not tied to one specific class, since a real binding for an entity-shaped call
    site can legitimately live on CLuaInstance, CLuaZone, etc. instead of CLuaBaseEntity."""
    if cached_index is not None:
        entries = cached_index.get(name)
        if entries:
            e = entries[0]
            return True, f"{e['file']}:{e['line']} (cached index)"
        return False, f"no matching registration for '{name}' found in cached index ({bbi.DSP_INDEX_PATH.name})"

    if flavor == "old_dsp_reference":
        pattern = re.compile(r"LUNAR_DECLARE_METHOD\(\s*\w+\s*,\s*" + re.escape(name) + r"\s*\)")
    else:
        pattern = re.compile(r'SOL_REGISTER\(\s*"' + re.escape(name) + r'"\s*,')

    for src in _lua_binding_files(dsp_root):
        text = src.read_text(encoding="utf-8", errors="replace")
        m = pattern.search(text)
        if m:
            line_no = text[:m.start()].count("\n") + 1
            return True, f"{src.relative_to(dsp_root).as_posix()}:{line_no}"
    return False, f"no matching registration for '{name}' found in any src/map/lua/*.cpp file"


def audit_package(pkg_lua_dsp: Path, dsp_root: Path, flavor: str) -> dict:
    cached_index = _load_cached_index(dsp_root, flavor)
    calls = collect_method_calls(pkg_lua_dsp)
    confirmed, missing = [], []
    for name, files in sorted(calls.items()):
        found, evidence = check_binding(name, dsp_root, flavor, cached_index=cached_index)
        (confirmed if found else missing).append((name, evidence, files))
    return {"confirmed": confirmed, "missing": missing}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("path", nargs="?", help="A lua-dsp/ directory to audit")
    ap.add_argument("--all-packages", action="store_true", help="Audit every mission-packages/*/lua-dsp/ tree")
    ap.add_argument("--dsp-root", default=str(DEFAULT_DSP_ROOT), help="Real DSP checkout to check against")
    ap.add_argument("--show-confirmed", action="store_true", help="Also list confirmed (not just missing) bindings")
    args = ap.parse_args()

    dsp_root = Path(args.dsp_root)
    flavor = blc.detect_target_flavor(dsp_root)
    if flavor is None:
        print(f"error: {dsp_root} does not fingerprint as either known DSP flavor "
              f"(old_dsp_reference/landsandboat) -- refusing to guess. Check the path.", file=sys.stderr)
        sys.exit(2)
    print(f"Target: {dsp_root} (detected flavor: {flavor})\n")

    if args.all_packages:
        targets = sorted(PACKAGES_ROOT.glob("*/lua-dsp"))
    elif args.path:
        targets = [Path(args.path)]
    else:
        ap.error("Provide a path or --all-packages")
        return

    any_missing = False
    for target in targets:
        if not target.exists():
            continue
        result = audit_package(target, dsp_root, flavor)
        print(f"=== {target.parent.name} === "
              f"({len(result['confirmed'])} confirmed, {len(result['missing'])} missing)")
        if args.show_confirmed:
            for name, evidence, _ in result["confirmed"]:
                print(f"  CONFIRMED  :{name}(  ->  {evidence}")
        for name, reason, files in result["missing"]:
            any_missing = True
            file_list = ", ".join(f.name for f in files[:3])
            more = f" (+{len(files) - 3} more)" if len(files) > 3 else ""
            print(f"  MISSING    :{name}(  ->  {reason}  [used in: {file_list}{more}]")

    if any_missing:
        print("\n*** unconfirmed bindings found -- verify each by hand before trusting it "
              "compiles; this tool only checks the binding NAME exists, not that the signature "
              "matches how it's actually called ***")
        sys.exit(1)


if __name__ == "__main__":
    main()
