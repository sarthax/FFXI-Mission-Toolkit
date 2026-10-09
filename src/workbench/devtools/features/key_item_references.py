"""Conservative checkout-local key-item Lua reference discovery.

Only explicit enum-symbol calls are reported. This is static evidence, not proof
that a script branch executes. No numeric IDs are compared across lineages.
"""
from __future__ import annotations

from pathlib import Path
import re

from workbench.devtools.features.state_surface import _line_refs


def discover_key_item_references(
    server_root: str | Path,
    symbol: str,
    *,
    max_matches: int = 250,
    max_files: int = 50000,
    lineage: str | None = None,
) -> dict:
    """Return explicit grant / require / remove references with source locations.

    Source root must be the selected checkout for one lineage. Call separately
    for DSP, Topaz, and LSB after resolving each lineage's enum symbol.
    """
    symbol = str(symbol or "").strip()
    if not re.fullmatch(r"[A-Z][A-Z0-9_]*", symbol):
        raise ValueError("key-item symbol must be an uppercase enum name")
    namespaces = {"lsb": "xi.keyItem.", "topaz": "tpz.ki.", "dsp": "tpz.ki."}
    if lineage is not None and lineage not in namespaces:
        raise ValueError("lineage must be lsb, topaz, or dsp")
    if max_matches < 1 or max_files < 1:
        raise ValueError("limits must be positive")
    root = Path(server_root).resolve()
    scripts = root / "scripts"
    if not scripts.is_dir():
        return {"symbol": symbol, "lineage": lineage, "source_root": str(root), "references": [],
                "scanned_files": 0, "truncated": False,
                "limitations": ["No scripts directory at the selected source root."]}
    references: list[dict] = []
    scanned = 0
    truncated = False
    for path in sorted(scripts.rglob("*.lua")):
        if scanned >= max_files:
            truncated = True
            break
        scanned += 1
        try:
            source = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if symbol not in source:
            continue
        rel = path.relative_to(root).as_posix()
        for ref in _line_refs(source, rel):
            if ref.state_type != "key_item" or ref.key != symbol:
                continue
            if lineage is not None and namespaces[lineage] + symbol not in ref.source_text:
                continue
            if len(references) >= max_matches:
                truncated = True
                break
            references.append({
                "operation": ref.operation,
                "source_path": ref.source_path,
                "source_line": ref.source_line,
                "source_text": ref.source_text,
                "symbol": symbol,
            })
        if truncated:
            break
    return {
        "symbol": symbol, "lineage": lineage, "source_root": str(root),
        "references": references, "scanned_files": scanned,
        "truncated": truncated,
        "limitations": [
            "Static textual references do not prove runtime reachability.",
            "Dynamic/helper-generated and numeric key-item references are not resolved.",
            "Use the enum symbol from the selected server lineage; numeric client IDs can drift.",
        ],
    }
