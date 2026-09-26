"""Service layer for the Client > Binary Inspector page (read-only PE evidence).

Thin wrapper over workbench.client.binary_index / binary_deep / binary_diff: it adds an in-process
index cache (indexing a 2.8 MB DLL is fast, but strings + imports are re-served on every filter
change) and discovery of candidate binaries in the FFXI install. Nothing here writes to a binary.
Only exact byte matches and PE-header facts are treated as evidence in the UI; the xref/function
candidate passes are deliberately not exposed (see docs/workbench/CLIENT_BINARY_RESEARCH.md --
they are heuristic and produce mostly false positives on the packed FFXiMain image).
"""
from __future__ import annotations

from pathlib import Path

from workbench.client.binary_deep import byte_search
from workbench.client.binary_diff import diff_binary_indexes
from workbench.client.binary_index import index_binary

_CACHE: dict[tuple[str, float, int], dict] = {}


def list_candidates(install_dir: str) -> list[dict]:
    root = Path(install_dir)
    out = []
    if root.is_dir():
        for p in sorted(list(root.glob("*.dll")) + list(root.glob("*.exe")), key=lambda x: x.name.lower()):
            out.append({"name": p.name, "path": str(p), "size": p.stat().st_size})
    return out


def get_index(path: str, max_strings: int = 25000) -> dict:
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"No such file: {path}")
    key = (str(p.resolve()), p.stat().st_mtime, max_strings)
    if key not in _CACHE:
        if len(_CACHE) > 6:
            _CACHE.clear()
        _CACHE[key] = index_binary(p, max_strings=max_strings)
    return _CACHE[key]


def imports_by_dll(idx: dict, q: str = "") -> list[dict]:
    q = q.lower()
    groups: dict[str, list[str]] = {}
    for row in idx["imports"]:
        name = row.get("name") or f"#{row.get('ordinal')}"
        if q and q not in name.lower() and q not in row["dll"].lower():
            continue
        groups.setdefault(row["dll"], []).append(name)
    return [{"dll": d, "names": sorted(n)} for d, n in sorted(groups.items(), key=lambda x: x[0].lower())]


def search_strings(idx: dict, q: str, limit: int = 300) -> dict:
    q_l = q.lower()
    hits = [s for s in idx["strings"] if q_l in s["text"].lower()]
    return {"total": len(hits), "rows": hits[:limit], "corpus": len(idx["strings"])}


def pattern_search(path: str, pattern: str, executable_only: bool, limit: int = 200) -> dict:
    return byte_search(Path(path), pattern, executable_only=executable_only, max_matches=limit)


def diff(left_path: str, right_path: str) -> dict:
    return diff_binary_indexes(get_index(left_path), get_index(right_path))
