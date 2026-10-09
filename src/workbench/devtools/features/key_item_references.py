"""Read-only Lua key-item usage discovery scoped to one configured server checkout.

Only literal enum-symbol API calls are reported; no numeric cross-lineage guesses.
Source occurrences are evidence, not proof of runtime execution.
"""
from __future__ import annotations

from pathlib import Path
import re
from functools import lru_cache

_ALLOWED_NAMESPACES = {
    "lsb": ("xi.keyItem",),
    "topaz": ("tpz.ki", "tpz.keyItem"),
    "dsp": ("tpz.ki", "tpz.keyItem"),
}
_CALL = re.compile(
    r"(?P<api>\b(?:player:(?:hasKeyItem|addKeyItem|delKeyItem)|"
    r"npcUtil\.giveKeyItem))\s*\(\s*"
    r"(?:(?:player\s*,\s*)?)"
    r"(?P<namespace>xi\.keyItem|tpz\.ki|tpz\.keyItem)\."
    r"(?P<symbol>[A-Z][A-Z0-9_]*)\b"
)
_OPERATION = {
    "hasKeyItem": "require",
    "addKeyItem": "grant",
    "delKeyItem": "remove",
    "giveKeyItem": "grant",
}


@lru_cache(maxsize=16384)
def _read_lua_lines(path: str, mtime_ns: int, size: int) -> tuple[str, ...]:
    """Cache immutable file content until its metadata changes.

    Both modification time and size form the invalidation key. This is
    checkout-local and does not cache cross-lineage search results.
    """
    with open(path, encoding="utf-8", errors="replace") as stream:
        return tuple(stream)


def discover_key_item_references(
    server_root: str | Path,
    symbol: str,
    *,
    max_matches: int = 250,
    max_files: int = 50000,
    lineage: str | None = None,
) -> dict:
    """Find source lines using an exact key-item enum in one server checkout.

    The caller must resolve `symbol` against the selected server's own enum,
    rather than passing client numeric IDs directly.
    """
    symbol = str(symbol or "").strip()
    if not re.fullmatch(r"[A-Z][A-Z0-9_]*", symbol):
        raise ValueError("key-item symbol must be an uppercase enum name")
    if lineage is not None and lineage not in _ALLOWED_NAMESPACES:
        raise ValueError("lineage must be lsb, topaz, or dsp")
    if max_matches < 1 or max_files < 1:
        raise ValueError("limits must be positive")

    root = Path(server_root).resolve()
    scripts = root / "scripts"
    result = {
        "operation_counts": {"require": 0, "grant": 0, "remove": 0},
        "matched_scripts": 0,
        "symbol": symbol, "lineage": lineage, "source_root": str(root),
        "references": [], "scanned_files": 0, "truncated": False,
        "limitations": [
            "Static source occurrences do not prove runtime execution.",
            "Dynamic, numeric, multiline, and helper-generated references may be missed.",
            "Resolve symbols from the selected server lineage; client IDs may drift.",
        ],
    }
    if not scripts.is_dir():
        result["limitations"].append("The selected checkout has no scripts directory.")
        return result

    permitted = set(_ALLOWED_NAMESPACES[lineage]) if lineage else {
        value for values in _ALLOWED_NAMESPACES.values() for value in values
    }
    matched_paths: set[str] = set()
    for path in sorted(scripts.rglob("*.lua")):
        # A symlinked script must never escape the selected checkout.
        if not path.resolve().is_relative_to(root):
            result["limitations"].append("A Lua symlink outside the selected checkout was skipped.")
            continue
        if result["scanned_files"] >= max_files:
            result["truncated"] = True
            break
        result["scanned_files"] += 1
        try:
            info = path.stat()
            for line_no, raw in enumerate(
                _read_lua_lines(str(path), info.st_mtime_ns, info.st_size), 1
            ):
                # Conservative line scan; text in Lua strings may still need review.
                code = raw.split("--", 1)[0]
                if symbol not in code:
                    continue
                for match in _CALL.finditer(code):
                    if match.group("symbol") != symbol or match.group("namespace") not in permitted:
                        continue
                    if len(result["references"]) >= max_matches:
                        result["truncated"] = True
                        return result
                    api = match.group("api").split(":")[-1].split(".")[-1]
                    relative_path = path.relative_to(root).as_posix()
                    matched_paths.add(relative_path)
                    result["operation_counts"][_OPERATION[api]] += 1
                    result["matched_scripts"] = len(matched_paths)
                    result["references"].append({
                        "operation": _OPERATION[api],
                        "api": api,
                        "namespace": match.group("namespace"),
                        "source_path": path.relative_to(root).as_posix(),
                        "source_line": line_no,
                        "source_text": raw.strip(),
                        "symbol": symbol,
                    })
        except OSError:
            result["limitations"].append("One or more Lua files could not be read.")
    return result
