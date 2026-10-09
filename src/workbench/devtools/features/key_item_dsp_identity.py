"""Conservative DSP key-item identity lookup from a configured DSP checkout.

A client numeric ID is not used to establish DSP identity. Only unique,
name-normalized constants from DSP's actual enum file are eligible.
"""
from __future__ import annotations

from pathlib import Path
import re

from workbench.client.dat.global_tables import normalize_name

_ENUM_LINE = re.compile(r"^\s*([A-Z][A-Z0-9_]*)\s*=\s*(\d+)\s*,?\s*(?:--.*)?$")


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
    matches: list[tuple[str, int]] = []
    try:
        with source.open(encoding="utf-8", errors="replace") as stream:
            for line in stream:
                match = _ENUM_LINE.fullmatch(line.rstrip("\r\n"))
                if match and normalize_name(match.group(1).replace("_", " ")) == expected:
                    matches.append((match.group(1), int(match.group(2))))
    except OSError:
        return {"status": "unavailable", "symbol": None,
                "message": "DSP enum file could not be read."}
    if len(matches) != 1:
        return {"status": "ambiguous" if matches else "missing", "symbol": None,
                "message": "DSP identity requires exactly one name-matched enum constant."}
    symbol, server_id = matches[0]
    return {"status": "name_verified", "symbol": symbol, "server_id": server_id,
            "source_path": source.relative_to(root).as_posix()}
