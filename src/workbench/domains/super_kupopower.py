"""Super Kupopower domain: loads data/super_kupopower/model.json (built by scripts/build_super_kupopower_domain.py) and merges the
user's entries: per-spot coordinates (entered.json) and per-item validation marks (validation.json). Writes are limited to those two files."""
from __future__ import annotations

import datetime
import json
import runpy

from workbench.runtime.paths import REPO_ROOT

DIR = REPO_ROOT / "data" / "super_kupopower"
DATA = DIR / "model.json"
ENTERED = DIR / "entered.json"
VALID = DIR / "validation.json"
BUILDER = REPO_ROOT / "scripts" / "build_super_kupopower_domain.py"
STATES = ("ok", "warn", "bad", "idle")
KINDS = ("power", "tablet", "npc", "global", "spot")
SPOT_STATUS = ("wiki", "visited", "verified", "bad")


def _load(p) -> dict:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _save(p, d) -> None:
    DIR.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(d, indent=1, ensure_ascii=False), encoding="utf-8")


def rebuild() -> None:
    runpy.run_path(str(BUILDER), run_name="__main__")


def overview() -> dict:
    if not DATA.exists():
        rebuild()
    d = json.loads(DATA.read_text(encoding="utf-8"))
    marks, ent = _load(VALID), _load(ENTERED)
    for kind, rows in (("power", d["powers"]), ("tablet", d["tablets"]), ("npc", d["npcs"]), ("global", d["globals"])):
        for r in rows:
            mk = marks.get("%s:%s" % (kind, r["id"]), {})
            r["validation"] = mk.get("state", "idle")
            r["vnote"] = mk.get("note", "")
    for z in d["zones"]:
        z["custom"] = [dict(v, id=k) for k, v in ent.items() if v.get("custom") and v.get("zoneid") == z["zoneid"]]
        for s in z["wiki_spots"]:
            e = ent.get(s["id"], {})
            s.update({k: e.get(k) for k in ("x", "y", "z", "tablet", "status", "note")})
            s["status"] = s["status"] or "wiki"
    d["summary"] = {
        "zones": len(d["zones"]),
        "spots": sum(len(z["wiki_spots"]) + len(z["custom"]) for z in d["zones"]),
        "with_coords": sum(1 for z in d["zones"] for s in z["wiki_spots"] + z["custom"] if s.get("x") is not None),
        "verified": sum(1 for z in d["zones"] for s in z["wiki_spots"] + z["custom"] if s.get("status") == "verified"),
    }
    return d


def _num(v, name):
    if v in (None, ""):
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        raise ValueError("%s: %r is not a number" % (name, v))
    if not -9999 <= f <= 9999:
        raise ValueError("%s outside -9999..9999" % name)
    return f


def save_spot(spot_id: str, b: dict) -> dict:
    """Store x/y/z (Y is the DB value, inverted axis), the tablet type, a status and a note for one spot, or create a custom spot."""
    d = overview()
    ent = _load(ENTERED)
    status = str(b.get("status") or "wiki")
    if status not in SPOT_STATUS:
        raise ValueError("status must be one of %s" % ", ".join(SPOT_STATUS))
    tablet = str(b.get("tablet") or "")
    if tablet and tablet not in {t["id"] for t in d["tablets"]}:
        raise ValueError("unknown tablet %r" % tablet)
    rec = {"x": _num(b.get("x"), "x"), "y": _num(b.get("y"), "y"), "z": _num(b.get("z"), "z"), "tablet": tablet, "status": status,
           "note": str(b.get("note") or "").strip()[:300], "updated": datetime.datetime.now().isoformat(timespec="seconds")}
    if status == "verified" and rec["x"] is None:
        raise ValueError("a verified spot needs coordinates")
    if spot_id == "new":
        zid = int(b.get("zoneid"))
        if zid not in {z["zoneid"] for z in d["zones"]}:
            raise ValueError("zone %r is not a tablet zone" % zid)
        n = 1 + max([int(k.split("-")[1][1:]) for k, v in ent.items() if v.get("custom") and v.get("zoneid") == zid] or [0])
        spot_id = "%d-c%d" % (zid, n)
        rec.update({"custom": True, "zoneid": zid, "grid": str(b.get("grid") or "").strip()[:12]})
    elif spot_id not in {s["id"] for z in d["zones"] for s in z["wiki_spots"]} and not ent.get(spot_id, {}).get("custom"):
        raise KeyError("no spot %r" % spot_id)
    else:
        rec = dict(ent.get(spot_id, {}), **rec)
    ent[spot_id] = rec
    _save(ENTERED, ent)
    return dict(rec, id=spot_id)


def delete_spot(spot_id: str) -> None:
    ent = _load(ENTERED)
    if not ent.get(spot_id, {}).get("custom"):
        raise KeyError("only custom spots can be deleted")
    del ent[spot_id]
    _save(ENTERED, ent)


def mark(kind: str, ident: str, state: str, note: str = "", who: str = "") -> dict:
    if kind not in KINDS:
        raise ValueError("unknown kind %r" % kind)
    if state not in STATES:
        raise ValueError("state must be one of %s" % ", ".join(STATES))
    d = overview()
    rows = {"power": d["powers"], "tablet": d["tablets"], "npc": d["npcs"], "global": d["globals"]}.get(kind)
    if rows is not None and not any(str(r["id"]) == str(ident) for r in rows):
        raise KeyError("no %s with id %r" % (kind, ident))
    marks = _load(VALID)
    k = "%s:%s" % (kind, ident)
    marks[k] = {"state": state, "note": note.strip()[:500], "by": who, "updated": datetime.datetime.now().isoformat(timespec="seconds")}
    _save(VALID, marks)
    return marks[k]
