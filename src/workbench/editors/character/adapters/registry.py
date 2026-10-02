"""Detect DSP, Topaz, or LandSandBoat from checkout and live-schema evidence."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class AdapterFingerprint:
    family: str
    confidence: str
    evidence: tuple[str, ...] = field(default_factory=tuple)


def _exists(root: Path, rel: str) -> bool:
    return (root / rel).exists()


def detect_adapter(server_root: Path | str, schema=None) -> AdapterFingerprint:
    root = Path(server_root).expanduser().resolve()
    evidence: list[str] = []
    scores = {"lsb": 0, "topaz": 0, "dsp": 0}

    # Filesystem/config lineage markers.
    if _exists(root, "settings/network.lua"):
        scores["lsb"] += 6; evidence.append("settings/network.lua")
    if _exists(root, "tools/dbtool.py"):
        scores["lsb"] += 3; evidence.append("tools/dbtool.py")
    if _exists(root, "conf/map_darkstar.conf"):
        scores["dsp"] += 6; evidence.append("conf/map_darkstar.conf")
    if _exists(root, "conf/map.conf"):
        scores["topaz"] += 3; scores["dsp"] += 1; evidence.append("conf/map.conf")
    if _exists(root, "src/map/lua/lua_baseentity.cpp"):
        scores["topaz"] += 1; scores["dsp"] += 1; evidence.append("src/map/lua/lua_baseentity.cpp")
    if _exists(root, "scripts/globals/keyitems.lua"):
        scores["topaz"] += 2; scores["dsp"] += 2; evidence.append("scripts/globals/keyitems.lua")
    if _exists(root, "scripts/enum/key_item.lua"):
        scores["lsb"] += 2; evidence.append("scripts/enum/key_item.lua")

    # Live schema markers supplement checkout detection. Never override stronger config evidence
    # with a single table because custom forks may backport newer tables.
    tables = set(getattr(schema, "tables", {}) or {})
    if "char_style" in tables:
        scores["lsb"] += 1; evidence.append("table:char_style")
    if "char_unlocks" in tables:
        scores["lsb"] += 1; scores["topaz"] += 1; evidence.append("table:char_unlocks")

    family, score = max(scores.items(), key=lambda item: item[1])
    ordered = sorted(scores.values(), reverse=True)
    margin = score - (ordered[1] if len(ordered) > 1 else 0)
    if score == 0:
        return AdapterFingerprint("unknown", "unknown", tuple(evidence))
    confidence = "high" if score >= 6 and margin >= 3 else ("medium" if margin >= 2 else "low")
    return AdapterFingerprint(family, confidence, tuple(evidence))
