#!/usr/bin/env python3
"""Focused Lua package sanity validation for generated/backport package trees."""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

try:
    from luaparser import ast as lua_ast
except ImportError:
    lua_ast = None

BARE_GLOBAL_REF_RE = re.compile(
    r"^\s*local\s+ID\s*=\s*(?:zones\[(?:xi\.zone\.|tpz\.zone\.)?)?([A-Z][A-Za-z0-9_]*)\]?\s*$",
    re.MULTILINE,
)
BARE_GLOBAL_DECL_RE = re.compile(r"^([A-Z][A-Za-z0-9_]*)\s*=", re.MULTILINE)


def check_syntax(path: Path) -> str | None:
    if lua_ast is None:
        return None
    text = path.read_text(encoding="utf-8", errors="replace")
    try:
        lua_ast.parse(text)
        return None
    except Exception as e:
        return f"{type(e).__name__}: {e}"


def check_package(pkg_lua_dsp: Path, include_paths: set[str] | None = None) -> dict:
    syntax_errors: list[tuple[Path, str]] = []
    declared: set[str] = set()
    references: list[tuple[Path, str]] = []

    lua_files = [
        f for f in pkg_lua_dsp.rglob("*.lua")
        if include_paths is None or f.relative_to(pkg_lua_dsp).as_posix() in include_paths
    ]
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


def _default_packages_root() -> Path:
    # Keep root settings/bootstrap concerns at the CLI boundary so the validator is importable
    # from an editable/package install without repository-root participation.
    import settings
    return settings.get_backport_root() / "mission-packages"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("path", nargs="?", help="A lua-dsp/ directory to check")
    ap.add_argument("--all-packages", action="store_true", help="Check every mission-packages/*/lua-dsp/ tree")
    ap.add_argument("--packages-root", default=None, help="mission-packages/ root for --all-packages")
    args = ap.parse_args()

    if lua_ast is None:
        print(
            "warning: luaparser not importable -- syntax checks skipped, only the declared-vs-"
            "referenced global check will run. `pip install luaparser` to enable full checking.",
            file=sys.stderr,
        )

    if args.all_packages:
        packages_root = Path(args.packages_root) if args.packages_root else _default_packages_root()
        targets = sorted(packages_root.glob("*/lua-dsp"))
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
                print(
                    f"  UNDECLARED GLOBAL  {f.relative_to(target)} references `{name}`, "
                    f"but no `{name} = ...` declaration found anywhere in this package"
                )
        if not result["syntax_errors"] and not result["undeclared_globals"]:
            print("  clean")

    if any_problems:
        print("\n*** real problems found -- see above ***")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
