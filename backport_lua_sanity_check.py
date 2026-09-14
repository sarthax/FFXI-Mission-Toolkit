#!/usr/bin/env python3
"""
backport_lua_sanity_check.py -- catches the exact class of bug that shipped once already this
project (2026-09-13): a zone's id-constants file declaring `zones[PERIQIA] = {...}` while every
real consumer file referenced bare `Periqia` -- syntactically valid Lua in isolation, but the
referenced global was never actually assigned anywhere, so it would be `nil` at runtime. That bug
was only caught by a human spot-checking the output by hand; nothing in the toolkit checked for it
mechanically. This does, for two things:

1. **Syntax validity** -- every `.lua` file in a lua-dsp/ tree actually parses (via `luaparser`,
   already a real dependency of this toolkit). A conversion regex gone wrong can produce text that
   LOOKS like Lua but doesn't parse -- this catches that outright, immediately, no server needed.
2. **Declared-vs-referenced bare globals** -- for the "one file declares `X = {...}`, other files
   do `local ID = X`" pattern this project's zone id-files use (old-dsp-reference's real
   convention, see per_zone_id_file_conventions in data/dsp_namespace_map.json), cross-references
   every `local ID = <Global>` / `local ID = zones[<Global>]`-style reference in a package against
   every top-level `<Global> = {`/`<Global> = ...` assignment actually present somewhere in that
   same package. A referenced-but-never-declared global is flagged -- exactly what would have
   caught the real shipped bug immediately instead of by luck.

This is deliberately narrow and heuristic, not a full Lua static analyzer -- it targets the ONE
failure mode that's actually bitten this project, not a general-purpose linter. Extend it if a new
failure mode of the same shape (a real bug that shipped and was only caught by hand) shows up.

Usage:
    py -3 backport_lua_sanity_check.py mission-packages/periqia_missions_1-4/lua-dsp
    py -3 backport_lua_sanity_check.py --all-packages
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

try:
    from luaparser import ast as lua_ast
except ImportError:
    lua_ast = None

import settings

DEFAULT_PACKAGES_ROOT = settings.get_backport_root() / "mission-packages"

# `local ID = Periqia` or `local ID = zones[Periqia]`/`zones[xi.zone.PERIQIA]` (the shape this
# project has shipped both wrong and right this session -- catch references to a bare capitalized
# global either way, ignore the zones[]/xi.zone. wrapping itself, only care about the tail name).
BARE_GLOBAL_REF_RE = re.compile(
    r"^\s*local\s+ID\s*=\s*(?:zones\[(?:xi\.zone\.|tpz\.zone\.)?)?([A-Z][A-Za-z0-9_]*)\]?\s*$",
    re.MULTILINE,
)
# `Periqia =` / `Periqia=` at column 0 -- a real top-level declaration of that global.
BARE_GLOBAL_DECL_RE = re.compile(r"^([A-Z][A-Za-z0-9_]*)\s*=", re.MULTILINE)


def check_syntax(path: Path) -> str | None:
    """Returns an error string if the file fails to parse, None if it's valid (or if luaparser
    isn't installed -- that's a real environment gap, reported once by the caller, not silently
    treated as "all files pass")."""
    if lua_ast is None:
        return None
    text = path.read_text(encoding="utf-8", errors="replace")
    try:
        lua_ast.parse(text)
        return None
    except Exception as e:  # luaparser raises its own exception types; catch broadly, report exactly
        return f"{type(e).__name__}: {e}"


def check_package(pkg_lua_dsp: Path) -> dict:
    """Returns {"syntax_errors": [(path, error)], "undeclared_globals": [(path, global_name)]}."""
    syntax_errors: list[tuple[Path, str]] = []
    declared: set[str] = set()
    references: list[tuple[Path, str]] = []

    lua_files = list(pkg_lua_dsp.rglob("*.lua"))
    for f in lua_files:
        err = check_syntax(f)
        if err:
            syntax_errors.append((f, err))

        text = f.read_text(encoding="utf-8", errors="replace")
        declared.update(BARE_GLOBAL_DECL_RE.findall(text))
        for m in BARE_GLOBAL_REF_RE.finditer(text):
            references.append((f, m.group(1)))

    undeclared = [(f, name) for f, name in references if name not in declared]
    return {"syntax_errors": syntax_errors, "undeclared_globals": undeclared, "file_count": len(lua_files)}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("path", nargs="?", help="A lua-dsp/ directory to check")
    ap.add_argument("--all-packages", action="store_true", help="Check every mission-packages/*/lua-dsp/ tree")
    ap.add_argument("--packages-root", default=str(DEFAULT_PACKAGES_ROOT),
                     help="mission-packages/ root for --all-packages (else Settings' backport_root, "
                          "else the bundled backport-workspace/ scaffold)")
    args = ap.parse_args()

    if lua_ast is None:
        print("warning: luaparser not importable -- syntax checks skipped, only the declared-vs-"
              "referenced global check will run. `pip install luaparser` to enable full checking.",
              file=sys.stderr)

    if args.all_packages:
        targets = sorted(Path(args.packages_root).glob("*/lua-dsp"))
    elif args.path:
        targets = [Path(args.path)]
    else:
        ap.error("Provide a path or --all-packages")
        return

    any_problems = False
    for target in targets:
        if not target.exists():
            print(f"=== {target} === NOT FOUND, skipping")
            continue
        result = check_package(target)
        pkg_name = target.parent.name
        print(f"=== {pkg_name} === ({result['file_count']} files)")
        if result["syntax_errors"]:
            any_problems = True
            for f, err in result["syntax_errors"]:
                print(f"  SYNTAX ERROR  {f.relative_to(target)}: {err}")
        if result["undeclared_globals"]:
            any_problems = True
            for f, name in result["undeclared_globals"]:
                print(f"  UNDECLARED GLOBAL  {f.relative_to(target)} references `{name}`, "
                      f"but no `{name} = ...` declaration found anywhere in this package")
        if not result["syntax_errors"] and not result["undeclared_globals"]:
            print("  clean")

    if any_problems:
        print("\n*** real problems found -- see above ***")
        sys.exit(1)


if __name__ == "__main__":
    main()
