"""Conservative DSP key-item identity lookup from a configured DSP checkout.

A client numeric ID is not used to establish DSP identity. Only unique,
name-normalized constants from DSP's actual enum file are eligible.
"""
from __future__ import annotations

from pathlib import Path
import re
from functools import lru_cache

from workbench.client.dat.global_tables import normalize_name

_ENUM_LINE = re.compile(r"^\s*([A-Z][A-Z0-9_]*)\s*=\s*(\d+)\s*[;,]?\s*(?:--.*)?$")


@lru_cache(maxsize=8)
def _enum_records(path: str, mtime_ns: int, size: int) -> dict[str, tuple[tuple[str, int], ...]]:
    catalog: dict[str, list[tuple[str, int]]] = {}
    with open(path, encoding="utf-8", errors="replace") as stream:
        for line in stream:
            match = _ENUM_LINE.fullmatch(line.rstrip("\r\n"))
            if match:
                key = normalize_name(match.group(1).replace("_", " "))
                catalog.setdefault(key, []).append((match.group(1), int(match.group(2))))
    return {key: tuple(values) for key, values in catalog.items()}


def inspect_dsp_key_item_catalog(root: str | Path) -> dict:
    """Report read-only source health; never assume a client/server ID match."""
    if not root:
        return {"status": "unconfigured", "entries": 0, "ambiguous_names": 0,
                "message": "No DSP source checkout configured."}
    root = Path(root).resolve()
    candidates = (root / "scripts/globals/keyitems.lua",
                  root / "scripts/globals/key_items.lua")
    existing = [path for path in candidates if path.is_file() and
                path.resolve().is_relative_to(root)]
    if len(existing) != 1:
        return {"status": "unavailable", "entries": 0, "ambiguous_names": 0,
                "message": "Expected exactly one DSP scripts/globals/keyitems.lua source."}
    source = existing[0]
    try:
        st = source.stat()
        records = _enum_records(str(source), st.st_mtime_ns, st.st_size)
    except OSError:
        return {"status": "unavailable", "entries": 0, "ambiguous_names": 0,
                "message": "DSP key-item source could not be read."}
    by_id: dict[int, set[str]] = {}
    for values in records.values():
        for symbol, server_id in values:
            by_id.setdefault(server_id, set()).add(symbol)
    duplicate_ids = {number: sorted(names) for number, names in by_id.items() if len(names) > 1}
    ambiguous = sorted(name for name, values in records.items() if len(values) > 1)
    return {"status": "ready", "source_path": source.relative_to(root).as_posix(),
            "entries": sum(len(v) for v in records.values()),
            "unique_names": sum(len(v) == 1 for v in records.values()),
            "ambiguous_names": len(ambiguous),
            "ambiguous_samples": ambiguous[:10],
            "duplicate_numeric_ids": len(duplicate_ids),
            "duplicate_id_samples": sorted(duplicate_ids)[:10],
            "message": "DSP enum catalog loaded from selected checkout."}


def resolve_dsp_key_item(root: str | Path, client_name: str) -> dict:
    root = Path(root).resolve()
    candidates = (
        root / "scripts" / "globals" / "keyitems.lua",
        root / "scripts" / "globals" / "key_items.lua",
    )
    existing = [p for p in candidates if p.is_file() and p.resolve().is_relative_to(root)]
    if len(existing) != 1:
        return {"status": "unavailable", "symbol": None,
                "message": "Expected exactly one DSP key-item enum source file."}
    source = existing[0]
    expected = normalize_name(str(client_name or ""))
    try:
        info = source.stat()
        matches = _enum_records(str(source), info.st_mtime_ns, info.st_size).get(expected, ())
    except OSError:
        return {"status": "unavailable", "symbol": None,
                "message": "DSP enum file could not be read."}
    if len(matches) != 1:
        return {"status": "ambiguous" if matches else "missing", "symbol": None,
                "message": "DSP identity requires exactly one name-matched enum constant."}
    symbol, server_id = matches[0]
    return {"status": "name_verified", "symbol": symbol, "server_id": server_id,
            "source_path": source.relative_to(root).as_posix()}
