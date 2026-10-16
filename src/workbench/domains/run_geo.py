"""Rune Fencer / Geomancer gap tracker: data/run_geo/gaps.json. Only status and note are editable from the page."""
from __future__ import annotations

import datetime
import json

from workbench.runtime.paths import REPO_ROOT

PATH = REPO_ROOT / "data" / "run_geo" / "gaps.json"
STATES = ["missing", "partial", "done", "hold"]


def load() -> list:
    return json.loads(PATH.read_text(encoding="utf-8"))


def overview() -> dict:
    rows = load()
    areas = list(dict.fromkeys(r["area"] for r in rows))
    return {"items": rows, "states": STATES, "areas": areas,
            "counts": {s: sum(1 for r in rows if r["status"] == s) for s in STATES}}


def save(item_id: str, changes: dict, who: str = "") -> dict:
    rows = load()
    e = next((r for r in rows if r["id"] == item_id), None)
    if e is None:
        raise KeyError(item_id)
    if "status" in changes:
        if changes["status"] not in STATES:
            raise ValueError("bad status")
        e["status"] = changes["status"]
    if "note" in changes:
        e["note"] = str(changes["note"])[:500]
    e["updated"] = datetime.datetime.now().isoformat(timespec="seconds")
    e["by"] = who
    tmp = PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(rows, indent=1), encoding="utf-8")
    tmp.replace(PATH)
    return e
