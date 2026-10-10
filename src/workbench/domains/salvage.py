"""Salvage domain data: loads data/salvage/salvage.json (built by scripts/build_salvage_domain.py) and merges the
user's per-item validation marks (data/salvage/validation.json). The only write is a validation mark."""
from __future__ import annotations

import datetime
import json
import runpy

from workbench.runtime.paths import REPO_ROOT

DATA = REPO_ROOT / "data" / "salvage" / "salvage.json"
VALID = REPO_ROOT / "data" / "salvage" / "validation.json"
BUILDER = REPO_ROOT / "scripts" / "build_salvage_domain.py"
STATES = ("ok", "warn", "bad", "idle")
KINDS = ("system", "track", "zone", "npc")
SECTIONS = (("system", "systems"), ("track", "tracks"), ("zone", "zones"), ("npc", "npcs"))


def _marks() -> dict:
    try:
        return json.loads(VALID.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def rebuild() -> None:
    runpy.run_path(str(BUILDER), run_name="__main__")


def overview() -> dict:
    if not DATA.exists():
        rebuild()
    d = json.loads(DATA.read_text(encoding="utf-8"))
    marks = _marks()
    summ = {}
    for kind, sect in SECTIONS:
        s = {"total": len(d[sect]), "status": {}, "validation": {}}
        for r in d[sect]:
            mk = marks.get("%s:%s" % (kind, r["id"]), {})
            r["validation"] = mk.get("state", "idle")
            r["vnote"] = mk.get("note", "")
            s["status"][r["status"]] = s["status"].get(r["status"], 0) + 1
            s["validation"][r["validation"]] = s["validation"].get(r["validation"], 0) + 1
        summ[kind] = s
    d["summary"] = summ
    return d


def mark(kind: str, ident: str, state: str, note: str = "", who: str = "") -> dict:
    if kind not in KINDS:
        raise ValueError("unknown kind %r" % kind)
    if state not in STATES:
        raise ValueError("state must be one of %s" % ", ".join(STATES))
    d = overview()
    sect = dict(SECTIONS)[kind]
    if not any(str(r["id"]) == str(ident) for r in d[sect]):
        raise KeyError("no %s with id %r" % (kind, ident))
    marks = _marks()
    k = "%s:%s" % (kind, ident)
    marks[k] = {"state": state, "note": note.strip()[:500], "by": who,
                "updated": datetime.datetime.now().isoformat(timespec="seconds")}
    VALID.parent.mkdir(parents=True, exist_ok=True)
    VALID.write_text(json.dumps(marks, indent=1, ensure_ascii=False), encoding="utf-8")
    return marks[k]
