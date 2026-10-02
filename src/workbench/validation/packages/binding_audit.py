"""Package Lua binding-name audit for legacy DSP migration output.

This validator extracts Lua colon-method calls from generated package output and confirms that
matching registrations exist in the selected target binding surface. It reuses Development's
read-only binding scanner and Validation's cache/provenance layer; it never mutates target source.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from workbench.devtools.server import binding_index as source_index
from workbench.packages.migration import lua_convert
from workbench.runtime.legacy_settings import get_backport_root, get_dsp_root
from workbench.validation.packages import binding_index

METHOD_CALL_RE = re.compile(r":([A-Za-z_][A-Za-z0-9_]*)\s*\(")
METHOD_DEFINITION_RE = re.compile(
    r"function\s+[A-Za-z_][A-Za-z0-9_.]*:[A-Za-z_][A-Za-z0-9_]*\s*\("
)
KNOWN_NON_ENTITY_METHODS = {
    "format", "find", "gsub", "match", "sub", "upper", "lower", "insert",
    "remove", "sort", "concat", "gmatch",
}
LINE_COMMENT_RE = re.compile(r"--(?!\[\[).*$", re.MULTILINE)
BLOCK_COMMENT_RE = re.compile(r"--\[\[.*?\]\]", re.DOTALL)


def _strip_comments(text: str) -> str:
    text = BLOCK_COMMENT_RE.sub("", text)
    return LINE_COMMENT_RE.sub("", text)


def collect_method_calls(
    pkg_lua_dsp: Path,
    include_paths: set[str] | None = None,
    ignore_methods: set[str] | None = None,
) -> dict[str, list[Path]]:
    calls: dict[str, list[Path]] = {}
    for path in pkg_lua_dsp.rglob("*.lua"):
        rel = path.relative_to(pkg_lua_dsp).as_posix()
        if include_paths is not None and rel not in include_paths:
            continue
        text = _strip_comments(path.read_text(encoding="utf-8", errors="replace"))
        text = METHOD_DEFINITION_RE.sub("", text)
        for name in set(METHOD_CALL_RE.findall(text)):
            if name in KNOWN_NON_ENTITY_METHODS or (ignore_methods is not None and name in ignore_methods):
                continue
            calls.setdefault(name, []).append(path)
    return calls


def _load_cached_index(dsp_root: Path, flavor: str) -> dict[str, list[dict]] | None:
    if flavor != "old_dsp_reference":
        return None
    if not binding_index.cache_matches_root(binding_index.DSP_INDEX_META_PATH, dsp_root):
        return None
    try:
        return binding_index.load_index(binding_index.DSP_INDEX_PATH)
    except FileNotFoundError:
        return None


def check_binding(
    name: str,
    dsp_root: Path,
    flavor: str,
    cached_index: dict | None = None,
) -> tuple[bool, str]:
    if cached_index is not None:
        entries = cached_index.get(name)
        if entries:
            entry = entries[0]
            return True, f"{entry['file']}:{entry['line']} (cached index)"
        return False, (
            f"no matching registration for '{name}' found in cached index "
            f"({binding_index.DSP_INDEX_PATH.name})"
        )

    if flavor == "old_dsp_reference":
        pattern = re.compile(
            r"LUNAR_DECLARE_METHOD\(\s*\w+\s*,\s*" + re.escape(name) + r"\s*\)"
        )
    else:
        pattern = re.compile(r'SOL_REGISTER\(\s*"' + re.escape(name) + r'"\s*,')

    for src in source_index.lua_binding_files(dsp_root):
        text = src.read_text(encoding="utf-8", errors="replace")
        match = pattern.search(text)
        if match:
            line_no = text[: match.start()].count("\n") + 1
            return True, f"{src.relative_to(dsp_root).as_posix()}:{line_no}"
    return False, f"no matching registration for '{name}' found in any src/map/lua/*.cpp file"


def audit_package(
    pkg_lua_dsp: Path,
    dsp_root: Path,
    flavor: str,
    include_paths: set[str] | None = None,
    ignore_methods: set[str] | None = None,
) -> dict:
    cached_index = _load_cached_index(dsp_root, flavor)
    calls = collect_method_calls(pkg_lua_dsp, include_paths, ignore_methods)
    confirmed: list[tuple] = []
    missing: list[tuple] = []
    for name, files in sorted(calls.items()):
        found, evidence = check_binding(name, dsp_root, flavor, cached_index=cached_index)
        (confirmed if found else missing).append((name, evidence, files))
    return {"confirmed": confirmed, "missing": missing}


def _default_paths() -> tuple[Path, Path | None]:
    return get_backport_root() / "mission-packages", get_dsp_root()


def main() -> None:
    default_packages_root, default_dsp_root = _default_paths()

    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("path", nargs="?", help="A lua-dsp/ directory to audit")
    ap.add_argument("--all-packages", action="store_true", help="Audit every mission-packages/*/lua-dsp/ tree")
    ap.add_argument(
        "--dsp-root",
        default=str(default_dsp_root) if default_dsp_root else None,
        help="Real DSP checkout to check against (else Settings' dsp_server_path)",
    )
    ap.add_argument(
        "--packages-root",
        default=str(default_packages_root),
        help="mission-packages/ root for --all-packages",
    )
    ap.add_argument("--show-confirmed", action="store_true")
    args = ap.parse_args()

    if not args.dsp_root:
        ap.error("No DSP checkout configured -- set Settings' dsp_server_path or pass --dsp-root.")
    dsp_root = Path(args.dsp_root)
    flavor = lua_convert.detect_target_flavor(dsp_root)
    if flavor is None:
        print(
            f"error: {dsp_root} does not fingerprint as either known DSP flavor "
            "(old_dsp_reference/landsandboat) -- refusing to guess. Check the path.",
            file=sys.stderr,
        )
        sys.exit(2)

    if args.all_packages:
        targets = sorted(Path(args.packages_root).glob("*/lua-dsp"))
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
        print(
            f"=== {target.parent.name} === "
            f"({len(result['confirmed'])} confirmed, {len(result['missing'])} missing)"
        )
        if args.show_confirmed:
            for name, evidence, _ in result["confirmed"]:
                print(f"  CONFIRMED  :{name}(  ->  {evidence}")
        for name, reason, files in result["missing"]:
            any_missing = True
            file_list = ", ".join(path.name for path in files[:3])
            more = f" (+{len(files) - 3} more)" if len(files) > 3 else ""
            print(f"  MISSING    :{name}(  ->  {reason}  [used in: {file_list}{more}]")

    if any_missing:
        print("\n*** unconfirmed bindings found -- verify each by hand before trusting it compiles ***")
        sys.exit(1)


if __name__ == "__main__":
    main()
