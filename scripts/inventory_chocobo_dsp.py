#!/usr/bin/env python3
"""Read-only Chocobo Raising source inventory for a local DSP/Valhalla checkout.

Produces a *candidate* audit report. No subsystem status is promoted by glob hits:
file existence cannot prove client packet behavior or runtime readiness.
"""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

PATTERNS = {
    "Eggs and inventory exdata": ["src/map/items/exdata/*chocobo*", "scripts/items/*chocobo*egg*"],
    "Stable NPCs and event dialogue": ["scripts/zones/*/npcs/Hantileon.lua", "scripts/zones/*/npcs/Zopago.lua", "scripts/zones/*/npcs/Pulonono.lua"],
    "NPC packet sequences": ["src/map/packets/*event*", "src/map/packets/*event*/*"],
    "Persistent character state": ["sql/*chocobo*", "src/map/lua/lua_base_entity.*"],
    "Daily care and progression": ["scripts/globals/*chocobo*raising*", "scripts/globals/hobbies/chocobo_raising/*"],
    "Personal whistle and mount": ["scripts/items/chocobo_whistle.lua", "src/map/utils/mountutils.*"],
    "Breeding, cards and retirement": ["scripts/globals/hobbies/chocobo_raising/breeding.lua", "scripts/items/chococard*"],
    "Walks, stories and digging": ["scripts/globals/hobbies/chocobo_raising/walks.lua", "scripts/globals/chocobo*"],
    "Chocobo racing": ["src/map/packets/*chocobo*racing*", "scripts/globals/hobbies/chocobo_racing/*"],
    "Headless regression coverage": ["scripts/tests/systems/chocobo_raising/*"],
}


def git_value(root: Path, *args: str) -> str:
    result = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, check=True)
    return result.stdout.strip()


def inventory(root: Path) -> dict:
    if not root.is_dir():
        raise ValueError("DSP checkout directory does not exist")
    commit = git_value(root, "rev-parse", "HEAD")
    git_root = Path(git_value(root, "rev-parse", "--show-toplevel")).resolve()
    if git_root != root.resolve():
        raise ValueError("provide the repository root, not a subdirectory")
    dirty = bool(git_value(root, "status", "--porcelain"))
    origin = git_value(root, "remote", "get-url", "origin") if "origin" in git_value(root, "remote").splitlines() else None
    results = []
    for name, patterns in PATTERNS.items():
        matches = sorted({
            file.relative_to(root).as_posix()
            for pattern in patterns for file in root.glob(pattern)
            if file.is_file() and not file.is_symlink()
        })
        results.append({
            "name": name,
            "dsp": "unknown",
            "evidence": [f"inventory:{p}" for p in matches] or ["inventory:no-pattern-matches"],
            "note": f"Read-only source inventory: {len(matches)} matching files. This is not runtime validation.",
        })
    return {"target_commit": commit, "source": {"origin": origin, "dirty": dirty},
            "findings": results}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dsp_checkout", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = inventory(args.dsp_checkout.resolve())
    if args.output.resolve().is_relative_to(args.dsp_checkout.resolve()):
        raise ValueError("output must be outside the DSP checkout to maintain a read-only audit")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"Inventory written: {args.output} ({len(report['findings'])} unknown-status subsystems)")


if __name__ == "__main__":
    main()
