"""Operator-confirmed animation observations (runtime state, never auto-applied to SQL)."""
from __future__ import annotations

import json
import time
from pathlib import Path

from workbench.runtime.paths import DATA_ROOT

STORE = DATA_ROOT / "generated" / "animlab" / "observations.json"
VERDICTS = ("correct", "wrong", "unknown")


def load(path: Path = STORE) -> list[dict]:
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def record(mob: str, anim: int, skill: int, verdict: str, note: str = "", path: Path = STORE) -> dict:
    if verdict not in VERDICTS:
        raise ValueError(f"verdict must be one of {VERDICTS}")
    rows = [r for r in load(path) if not (r["mob"] == mob and r["anim"] == anim and r["skill"] == skill)]
    row = {"mob": mob, "anim": anim, "skill": skill, "verdict": verdict, "note": note,
           "when": time.strftime("%Y-%m-%dT%H:%M:%S")}
    rows.append(row)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(sorted(rows, key=lambda r: (r["mob"], r["anim"])), indent=1), encoding="utf-8")
    return row


def confirmed(mob: str | None = None, path: Path = STORE) -> list[dict]:
    return [r for r in load(path) if r["verdict"] == "correct" and (mob is None or r["mob"] == mob)]
