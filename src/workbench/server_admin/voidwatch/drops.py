"""Voidwatch drop editing.

Drops are not in mob_droplist; they come from each NM's script plus scripts/globals/voidwatch_drops.lua.
This module reads and rewrites ONLY voidwatch_drops.lua (a small generated data file): extra shared Pyxis-pool items,
shared-pool removals, and per-NM added drops (percent) / removed script drops. Item ids are verified against item_basic.
"""
from __future__ import annotations

import datetime
import difflib
import json
import re
from pathlib import Path

from workbench.runtime.paths import REPO_ROOT

from . import details as D

LOG = REPO_ROOT / "data" / "voidwatch" / "edit_log.jsonl"
HEADER = """-----------------------------------
-- Voidwatch drop overrides. Managed by the Mission Toolkit Voidwatch domain (or edit by hand).
-- pool       : item ids ADDED to the shared Pyxis filler pool
-- poolRemove : item ids removed from the shared filler pool (including the built-in placeholder list)
-- nm[name]   : keyed by the mob's script name (mob:getName()); add = {[itemid] = percent}, remove = {itemid, ...}
-----------------------------------"""


class DropError(ValueError):
    pass


def locate(active_root):
    for root in D.script_roots(active_root):
        if (root / "scripts" / "globals" / "voidwatch.lua").exists():
            return root
    return None


def overrides_path(root: Path) -> Path:
    return root / "scripts" / "globals" / "voidwatch_drops.lua"


def _ids(txt: str) -> list[int]:
    return [int(x) for x in re.findall(r"\d+", txt)]


def parse(text: str) -> dict:
    out = {"pool": [], "poolRemove": [], "nm": {}}
    for key in ("pool", "poolRemove"):
        m = re.search(r"^\s*" + key + r"\s*=\s*\{([^}]*)\}", text, re.M)
        if m:
            out[key] = _ids(m.group(1))
    pat = r'\["([^"]+)"\]\s*=\s*\{\s*add\s*=\s*\{([^}]*)\}\s*,\s*remove\s*=\s*\{([^}]*)\}\s*,?\s*\}'
    for m in re.finditer(pat, text):
        add = {int(a): float(b) for a, b in re.findall(r"\[(\d+)\]\s*=\s*([\d.]+)", m.group(2))}
        out["nm"][m.group(1)] = {"add": add, "remove": _ids(m.group(3))}
    return out


def render(o: dict) -> str:
    lines = [HEADER, "VW_DROP_OVERRIDES = {",
             "    pool = {" + ", ".join(str(i) for i in o["pool"]) + "},",
             "    poolRemove = {" + ", ".join(str(i) for i in o["poolRemove"]) + "},",
             "    nm = {"]
    for name in sorted(o["nm"]):
        e = o["nm"][name]
        if not e["add"] and not e["remove"]:
            continue
        add = ", ".join("[%d] = %g" % (i, p) for i, p in sorted(e["add"].items()))
        rem = ", ".join(str(i) for i in e["remove"])
        lines.append('        ["%s"] = { add = {%s}, remove = {%s} },' % (name, add, rem))
    lines += ["    },", "};", ""]
    return "\n".join(lines)


def current(active_root) -> dict:
    empty = {"pool": [], "poolRemove": [], "nm": {}}
    root = locate(active_root)
    if root is None:
        return {"root": None, "path": None, "exists": False, "wired": False, "overrides": empty, "placeholder_pool": []}
    path = overrides_path(root)
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    vw = (root / "scripts" / "globals" / "voidwatch.lua").read_text(encoding="utf-8", errors="replace")
    m = re.search(r"PLACEHOLDER_POOL\s*=\s*\{([^}]*)\}", vw)
    return {"root": str(root), "path": str(path), "exists": path.exists(), "wired": "voidwatch_drops" in vw,
            "overrides": parse(text) if text else empty, "placeholder_pool": _ids(m.group(1)) if m else []}


def plan(conn, active_root, payload: dict) -> dict:
    """payload: scope (NM name; ignored for pool ops), op (add|unadd|remove|restore|pool_add|pool_remove|pool_restore), item, rate."""
    cur = current(active_root)
    if cur["root"] is None:
        raise DropError("No DSP checkout with scripts/globals/voidwatch.lua was found")
    if not cur["wired"]:
        raise DropError("voidwatch.lua does not require voidwatch_drops yet, so overrides would have no effect")
    o = json.loads(json.dumps(cur["overrides"]))
    o["nm"] = {k: {"add": {int(a): b for a, b in v["add"].items()}, "remove": v["remove"]} for k, v in cur["overrides"]["nm"].items()}
    op = str(payload.get("op", ""))
    try:
        item = int(payload.get("item"))
    except (TypeError, ValueError):
        raise DropError("item must be an item id")
    names = D._item_names(conn, [item])
    if item not in names:
        raise DropError("Item id %d is not in item_basic" % item)
    scope = str(payload.get("scope", ""))
    base = cur["placeholder_pool"]
    if op.startswith("pool_"):
        if op == "pool_add":
            if item in o["pool"] or (item in base and item not in o["poolRemove"]):
                raise DropError("Item is already in the shared pool")
            o["poolRemove"] = [i for i in o["poolRemove"] if i != item]
            if item not in base:
                o["pool"].append(item)
        elif op == "pool_remove":
            if item in o["pool"]:
                o["pool"].remove(item)
            elif item in base and item not in o["poolRemove"]:
                o["poolRemove"].append(item)
            else:
                raise DropError("Item is not in the shared pool")
        elif op == "pool_restore":
            o["poolRemove"] = [i for i in o["poolRemove"] if i != item]
        else:
            raise DropError("Unknown op " + op)
    else:
        if not any(x["name"] == scope for x in D.load_tracker()):
            raise DropError("Unknown NM %r" % scope)
        key = D.script_name(scope)
        e = o["nm"].setdefault(key, {"add": {}, "remove": []})
        if op == "add":
            try:
                rate = float(payload.get("rate"))
            except (TypeError, ValueError):
                raise DropError("rate must be a percent")
            if not 0 < rate <= 100:
                raise DropError("rate must be above 0 and at most 100 (percent)")
            e["add"][item] = rate
        elif op == "unadd":
            e["add"].pop(item, None)
        elif op == "remove":
            if item not in e["remove"]:
                e["remove"].append(item)
        elif op == "restore":
            e["remove"] = [i for i in e["remove"] if i != item]
        else:
            raise DropError("Unknown op " + op)
        if not e["add"] and not e["remove"]:
            o["nm"].pop(key, None)
    old = overrides_path(Path(cur["root"])).read_text(encoding="utf-8") if cur["exists"] else ""
    new = render(o)
    diff = "".join(difflib.unified_diff(old.splitlines(True), new.splitlines(True), "voidwatch_drops.lua (before)", "voidwatch_drops.lua (after)"))
    return {"path": cur["path"], "op": op, "scope": scope, "item": item, "item_name": names[item], "new_text": new,
            "diff": diff, "unchanged": old.strip() == new.strip()}


def apply(p: dict, who: str = "") -> None:
    Path(p["path"]).write_text(p["new_text"], encoding="utf-8")
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"at": datetime.datetime.now().isoformat(timespec="seconds"), "by": who, "table": "voidwatch_drops.lua",
                             "op": p["op"], "scope": p["scope"], "item": p["item"], "diff": p["diff"]}) + "\n")
