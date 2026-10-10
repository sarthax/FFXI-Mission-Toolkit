"""Campaign domain data: loads data/campaign/campaign.json (built by scripts/build_campaign_domain.py) and merges the
user's per-item validation marks (data/campaign/validation.json). Read-mostly; the only write is a validation mark."""
from __future__ import annotations

import datetime
import json
import runpy

from workbench.runtime.paths import REPO_ROOT

DATA = REPO_ROOT / "data" / "campaign" / "campaign.json"
VALID = REPO_ROOT / "data" / "campaign" / "validation.json"
BUILDER = REPO_ROOT / "scripts" / "build_campaign_domain.py"
STATES = ("ok", "warn", "bad", "idle")
KINDS = ("system", "npc", "menu", "mission", "reward")


def _marks() -> dict:
    try:
        return json.loads(VALID.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def key(kind: str, ident) -> str:
    return "%s:%s" % (kind, ident)


def rebuild() -> None:
    runpy.run_path(str(BUILDER), run_name="__main__")


def overview() -> dict:
    if not DATA.exists():
        rebuild()
    d = json.loads(DATA.read_text(encoding="utf-8"))
    marks = _marks()
    for m in d["menus"]:
        m["id"] = str(m["event"]) + "-" + m["npc"]
        m["status"] = {"yes": "done", "partial": "partial", "no": "not built"}.get(m["decoded"], "unknown")
    for kind, rows in (("system", d["systems"]), ("npc", d["npcs"]), ("menu", d["menus"]), ("mission", d["missions"]), ("reward", d["rewards"])):
        for r in rows:
            mk = marks.get(key(kind, r["id"]), {})
            r["validation"] = mk.get("state", "idle")
            r["vnote"] = mk.get("note", "")
    summ = {}
    for kind, rows in (("system", d["systems"]), ("npc", d["npcs"]), ("menu", d["menus"]), ("mission", d["missions"]), ("reward", d["rewards"])):
        s = {"total": len(rows), "status": {}, "validation": {}}
        for r in rows:
            s["status"][r["status"]] = s["status"].get(r["status"], 0) + 1
            s["validation"][r["validation"]] = s["validation"].get(r["validation"], 0) + 1
        summ[kind] = s
    d["summary"] = summ
    d["summary"]["quest"] = {"total": len(d["quests"]), "status": {}, "validation": {}}
    return d


def mark(kind: str, ident: str, state: str, note: str = "", who: str = "") -> dict:
    if kind not in KINDS:
        raise ValueError("unknown kind %r" % kind)
    if state not in STATES:
        raise ValueError("state must be one of %s" % ", ".join(STATES))
    d = overview()
    rows = {"system": d["systems"], "npc": d["npcs"], "menu": d["menus"], "mission": d["missions"], "reward": d["rewards"]}[kind]
    if not any(str(r["id"]) == str(ident) for r in rows):
        raise KeyError("no %s with id %r" % (kind, ident))
    marks = _marks()
    marks[key(kind, ident)] = {"state": state, "note": note.strip()[:500], "by": who,
                               "updated": datetime.datetime.now().isoformat(timespec="seconds")}
    VALID.parent.mkdir(parents=True, exist_ok=True)
    VALID.write_text(json.dumps(marks, indent=1, ensure_ascii=False), encoding="utf-8")
    return marks[key(kind, ident)]
