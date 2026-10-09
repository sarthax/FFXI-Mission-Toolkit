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
