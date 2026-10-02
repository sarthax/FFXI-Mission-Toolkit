"""Checkout-local Assault mission catalog for Character Editor.

Assault IDs are progression data owned by the selected server checkout. Parse only a recognized
Assault enum/global file from that checkout and fall back to numeric IDs when no trustworthy
catalog is present.
"""
from __future__ import annotations

from pathlib import Path
import re
from typing import Any


_CANDIDATES = (
    ("scripts/enum/assault.lua", "assault.lua"),
    ("scripts/globals/assault.lua", "assault.lua"),
    ("scripts/globals/assaults.lua", "assaults.lua"),
)


def _label(symbol: str) -> str:
    text = str(symbol or "").strip().replace("_", " ")
    return " ".join(word.capitalize() for word in text.split())


def _find_source(root: Path | None) -> tuple[Path | None, str | None]:
    if root is None:
        return None, None
    for relative, kind in _CANDIDATES:
        path = root / relative
        if path.is_file():
            return path, kind
    return None, None


def assault_catalog(server_root: Path | str | None) -> dict[str, Any]:
    root = Path(server_root).resolve() if server_root else None
    path, kind = _find_source(root)
    source = {
        "kind": kind or "assault.lua",
        "path": str(path) if path else None,
        "available": bool(path),
    }
    if path is None:
        return {"source": source, "missions": {}}

    # Current LSB uses ``xi.assault.mission = { ... }``. Historical/fork code commonly keeps the
    # same logical table behind ``tpz`` or ``dsp`` prefixes. Do not parse unrelated instance IDs.
    start_pattern = re.compile(r"^\s*(?:xi|tpz|dsp)\.assault\.mission\s*=\s*$")
    value_pattern = re.compile(r"^\s*([A-Z][A-Z0-9_]*)\s*=\s*(\d+)\s*,?")

    missions: dict[int, dict[str, Any]] = {}
    in_table = False
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.split("--", 1)[0].rstrip()
        if not in_table:
            if start_pattern.match(line):
                in_table = True
            continue
        if line.strip().startswith("{"):
            continue
        if line.strip().startswith("}"):
            break
        match = value_pattern.match(line)
        if not match:
            continue
        symbol, raw_id = match.groups()
        assault_id = int(raw_id)
        if not 0 <= assault_id <= 127:
            continue
        missions[assault_id] = {
            "id": assault_id,
            "symbol": symbol,
            "label": _label(symbol),
        }

    return {
        "source": source,
        "missions": {str(assault_id): row for assault_id, row in sorted(missions.items())},
    }
