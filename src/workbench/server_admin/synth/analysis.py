"""Cross-environment recipe compare, craft-cost/loop analysis and structural health checks. Read only."""
from __future__ import annotations

import csv
import io
import re
from pathlib import Path
from collections import Counter, defaultdict
from typing import Any

from . import recipes as R


def load_all(conn) -> list[dict[str, Any]]:
    cols = R.table_columns(conn)
    return [R._canon(R._row_dict(cols, r)) for r in R._rows(conn, "SELECT * FROM `synth_recipes` ORDER BY `ID`")]


def _key(rc: dict[str, Any]) -> tuple:
    first = rc["results"][0]["item_id"] if rc["results"] else 0
    return (rc["desynth"], rc["crystal"], tuple(sorted(rc["ingredients"])), first)


def _fields(rc: dict[str, Any]) -> dict[str, Any]:
    return {"skills": {k: v for k, v in rc["skills"].items() if v}, "hq_crystal": rc["hq_crystal"], "key_item": rc["key_item"],
            "results": [(x["item_id"], x["qty"]) for x in rc["results"] if x["item_id"]]}


def compare(conn_a, conn_b, label_a: str = "A", label_b: str = "B", limit: int = 500) -> dict[str, Any]:
    """Match recipes by (desynth, crystal, ingredient set, main result), not by recipe id."""
    a_all, b_all = load_all(conn_a), load_all(conn_b)
    am, bm = defaultdict(list), defaultdict(list)
    for rc in a_all:
        am[_key(rc)].append(rc)
    for rc in b_all:
        bm[_key(rc)].append(rc)
    only_a, only_b, changed, same = [], [], [], 0
    for k, lst in am.items():
        other = bm.get(k)
        if not other:
            only_a += lst
            continue
        for rc in lst:
            if any(_fields(rc) == _fields(o) for o in other):
                same += 1
            else:
                o = other[0]
                fa, fb = _fields(rc), _fields(o)
                changed.append({"key_a": rc["id"], "key_b": o["id"], "result": k[3],
                                "diff": {f: [fa[f], fb[f]] for f in fa if fa[f] != fb[f]}})
    for k, lst in bm.items():
        if k not in am:
            only_b += lst
    ids = {i for rc in (*only_a, *only_b) for i in (rc["crystal"], *rc["ingredients"], *[x["item_id"] for x in rc["results"]]) if i}
    ids |= {c["result"] for c in changed}
    na, nb = R.item_names(conn_a, ids), R.item_names(conn_b, ids)
    mismatch = sorted(i for i in ids if i in na and i in nb and na[i].lower() != nb[i].lower())
    absent_a, absent_b = sorted(i for i in ids if i not in na), sorted(i for i in ids if i not in nb)

    def brief(rc):
        r0 = rc["results"][0]["item_id"] if rc["results"] else 0
        return {"id": rc["id"], "result": r0, "name": na.get(r0) or nb.get(r0) or "", "desynth": rc["desynth"],
                "skills": {k: v for k, v in rc["skills"].items() if v}, "ingredients": rc["ingredients"], "crystal": rc["crystal"]}
    for c in changed:
        c["name"] = na.get(c["result"]) or nb.get(c["result"]) or ""
    return {"a": {"label": label_a, "count": len(a_all)}, "b": {"label": label_b, "count": len(b_all)}, "same": same,
            "only_a_count": len(only_a), "only_b_count": len(only_b), "changed_count": len(changed),
            "only_a": [brief(r) for r in only_a[:limit]], "only_b": [brief(r) for r in only_b[:limit]], "changed": changed[:limit],
            "item_name_mismatch": [{"item_id": i, "a": na[i], "b": nb[i]} for i in mismatch[:200]],
            "items_absent_in_a": absent_a[:200], "items_absent_in_b": absent_b[:200]}


def sync_sql(conn_src, ids: list[int], target_flavor: str) -> str:
    """INSERT … ON DUPLICATE-style: plain INSERTs for recipes that exist in the source."""
    out = []
    for rid in ids[:1000]:
        rc = R.get_recipe(conn_src, rid)
        if rc:
            out.append(R.build_sql(rc, target_flavor, "create"))
    return "\n".join(out)


# ---------------------------------------------------------------- economy
def _sell_values(conn, ids: set[int]) -> dict[int, int]:
    out: dict[int, int] = {}
    ids = sorted(ids)
    for n in range(0, len(ids), 400):
        part = ids[n:n + 400]
        for r in R._rows(conn, f"SELECT itemid,BaseSell FROM item_basic WHERE itemid IN ({','.join(['%s'] * len(part))})", tuple(part)):
            out[int(r[0])] = int(r[1] or 0)
    return out


def economy(conn, root, limit: int = 300) -> dict[str, Any]:
    """Craft cost per recipe from vendor prices (recursing through craftable inputs) vs NPC sell value of the output.

    Inputs with no vendor price and no craft route have unknown cost; the recipe is reported but not priced.
    """
    src = R._sources(conn, root)
    vendors = src["vendors"]
    recs = [r for r in load_all(conn) if not r["desynth"]]
    by_result: dict[int, list[dict]] = defaultdict(list)
    for r in recs:
        for x in r["results"][:1]:
            if x["item_id"]:
                by_result[x["item_id"]].append(r)
    memo: dict[int, int | None] = {}

    def unit_cost(item: int, stack: tuple = ()) -> int | None:
        if item in memo:
            return memo[item]
        v = vendors.get(item)
        best = v["price"] if v else None
        if item not in stack and len(stack) < 4:
            for rc in by_result.get(item, [])[:5]:
                c = recipe_cost(rc, (*stack, item))
                q = max(1, rc["results"][0]["qty"] or 1)
                if c is not None and (best is None or c / q < best):
                    best = c // q
        if not stack:
            memo[item] = best
        return best

    def recipe_cost(rc, stack=()) -> int | None:
        total = 0
        for i in rc["ingredients"]:
            c = unit_cost(i, stack)
            if c is None:
                return None
            total += c
        return total

    sells = _sell_values(conn, {x["item_id"] for r in recs for x in r["results"]} | {i for r in recs for i in r["ingredients"]})
    rows, loops = [], []
    for rc in recs:
        out = rc["results"][0] if rc["results"] else {"item_id": 0, "qty": 0}
        cost = recipe_cost(rc)
        value = sells.get(out["item_id"], 0) * max(1, out["qty"] or 1)
        if cost is None or not value:
            continue
        rows.append({"id": rc["id"], "result": out["item_id"], "qty": out["qty"], "cost": cost, "npc_value": value, "profit": value - cost})
    exploit = [r for r in rows if r["profit"] > 0]
    exploit.sort(key=lambda r: -r["profit"])

    # item cycles: A is made from B which is (transitively) made from A
    graph: dict[int, set[int]] = defaultdict(set)
    for rc in recs:
        for x in rc["results"][:1]:
            graph[x["item_id"]] |= set(rc["ingredients"])
    seen_cycles = set()
    for start in list(graph):
        stack = [(start, (start,))]
        while stack and len(loops) < 50:
            node, path = stack.pop()
            for nxt in graph.get(node, ()):
                if nxt == start and len(path) > 1:
                    cyc = tuple(sorted(path))
                    if cyc not in seen_cycles:
                        seen_cycles.add(cyc)
                        loops.append(list(path))
                elif nxt not in path and len(path) < 4:
                    stack.append((nxt, (*path, nxt)))
    ids = {r["result"] for r in exploit[:limit]} | {i for l in loops for i in l}
    names = R.item_names(conn, ids)
    for r in exploit:
        r["name"] = names.get(r["result"], "")
    return {"priced": len(rows), "profitable": len(exploit), "exploits": exploit[:limit],
            "loops": [{"items": l, "names": [names.get(i, str(i)) for i in l]} for l in loops],
            "note": "Cost uses cheapest vendor/guild price per input (recursing through craftable inputs, depth 4). Recipes with an input that has no priced route are skipped. Profit = NPC sell value of the result minus cost; a positive value means crafting then selling to an NPC creates gil."}


# ---------------------------------------------------------------- health
def health(conn, root) -> dict[str, Any]:
    recs = load_all(conn)
    known = set(R.item_names(conn, {i for r in recs for i in (r["crystal"], *r["ingredients"], *[x["item_id"] for x in r["results"]]) if i}))
    issues: dict[str, list[int]] = defaultdict(list)
    seen: dict[tuple, int] = {}
    for r in recs:
        out = [x for x in r["results"] if x["item_id"]]
        if not r["desynth"]:
            if not r["ingredients"]:
                issues["no_ingredients"].append(r["id"])
            if not r["crystal"]:
                issues["no_crystal"].append(r["id"])
            if not any(r["skills"].values()):
                issues["no_skill_level"].append(r["id"])
        if not out:
            issues["no_result"].append(r["id"])
        elif any(x["qty"] <= 0 for x in out):
            issues["zero_result_qty"].append(r["id"])
        if any(i not in known for i in (r["crystal"], *r["ingredients"], *[x["item_id"] for x in out]) if i):
            issues["unknown_item_id"].append(r["id"])
        k = (r["desynth"], r["crystal"], tuple(sorted(r["ingredients"])), tuple(x["item_id"] for x in out[:1]))
        if k in seen:
            issues["duplicate"].append(r["id"])
        else:
            seen[k] = r["id"]
        if any(r["skills"].values()) and max(r["skills"].values()) > 120:
            issues["skill_over_120"].append(r["id"])
    labels = {"no_ingredients": "Synth with no ingredients", "no_crystal": "Synth with no crystal", "no_skill_level": "Synth with no skill level",
              "no_result": "No result item", "zero_result_qty": "Result quantity is 0", "unknown_item_id": "References an item id not in item_basic",
              "duplicate": "Duplicate of an earlier recipe", "skill_over_120": "Skill requirement above 120 (check)"}
    checks = [{"code": c, "label": labels[c], "count": len(v), "ids": v[:100]} for c, v in issues.items()]
    checks.sort(key=lambda c: -c["count"])
    aud = R.audit(conn, root, limit=2000, mode="all")
    blockers: Counter = Counter()
    for p in aud["problems"]:
        for g in p["gaps"]:
            if g["status"] == "missing":
                blockers[(g["item_id"], g.get("name") or "")] += 1
    return {"total": len(recs), "structural": checks, "sources": aud["counts"],
            "blockers": [{"item_id": i, "name": n, "recipes": c} for (i, n), c in blockers.most_common(40)]}


def audit_csv(conn, root, mode: str = "synth") -> str:
    aud = R.audit(conn, root, limit=2000, mode=mode)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["recipe_id", "result_id", "result", "problem", "gap_item_id", "gap_item", "status"])
    for p in aud["problems"]:
        for i in p["invalid"]:
            w.writerow([p["id"], p["result"], p["name"], "unknown item id", i, "", "bad_item"])
        for g in p["gaps"]:
            w.writerow([p["id"], p["result"], p["name"], "no hard source", g["item_id"], g.get("name", ""), g["status"]])
    return buf.getvalue()


# ---------------------------------------------------------------- research: naming, guild coverage
_CONTAINER = re.compile(r"^(?:[a-z]+_)+?of_")


def _norm_name(name: str) -> str:
    """Strip a leading container phrase ('sprig_of_', 'piece_of_', 'pinch_of_') so 'sprig_of_fresh_marjoram' == 'fresh_marjoram'."""
    n = str(name or "").lower().strip()
    return _CONTAINER.sub("", n, count=1)


_GUILD_CRAFT = {"blacksmithing": "Smith", "smithing": "Smith", "woodworking": "Wood", "goldsmithing": "Gold", "clothcraft": "Cloth", "leathercraft": "Leather",
                "bonecraft": "Bone", "alchemy": "Alchemy", "culinary": "Cook", "cooking": "Cook", "fishing": "Fish", "tenshodo": ""}


def _abbrev(sort: str, name: str) -> bool:
    toks = [x for x in re.split(r"[_.\s]+", sort.lower()) if x]
    full = [x for x in re.split(r"[_.\s]+", name.lower()) if x]
    return bool(toks) and all(any(f.startswith(x) for f in full) for x in toks)


def guild_npcs(root) -> list[dict[str, Any]]:
    """Guild merchant NPCs found as player:sendGuild(<guild id>, ...) in the zone scripts."""
    out = []
    base = Path(root) / "scripts" / "zones"
    pat = re.compile(r"sendGuild\(\s*(\d+)\s*,")
    if not base.exists():
        return out
    for path in base.rglob("*.lua"):
        if "npcs" not in path.parts:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        m = pat.search(text)
        if m:
            h = re.search(r"Guild Merchant NPC:\s*([A-Za-z ]+?)\s*Guild", text[:600])
            out.append({"guild": int(m.group(1)), "npc": path.stem, "zone": path.parts[path.parts.index("zones") + 1],
                        "craft": _GUILD_CRAFT.get(h.group(1).strip().lower(), "") if h else ""})
    return sorted(out, key=lambda x: (x["guild"], x["zone"]))


def research(conn, root, other=None) -> dict[str, Any]:
    """Tighter source/naming research. `other` = (label, connection) of a second environment for cross-checks."""
    cols = R.table_columns(conn)
    rows = [R._canon(R._row_dict(cols, r)) for r in R._rows(conn, "SELECT * FROM `synth_recipes`")]
    ids = {i for r in rows for i in (*r["ingredients"], r["crystal"], r["hq_crystal"], *[x["item_id"] for x in r["results"]]) if i}
    marks = ",".join(["%s"] * len(ids)) or "NULL"
    items = {int(r[0]): (str(r[1] or ""), str(r[2] or "")) for r in R._rows(conn, f"SELECT itemid,name,sortname FROM item_basic WHERE itemid IN ({marks})", tuple(ids))}
    alias, mismatch = [], []
    for iid, (name, sort) in sorted(items.items()):
        if name == sort or not sort:
            continue
        if _norm_name(name) != _norm_name(sort) and _abbrev(sort, name):
            continue                                   # ‘f._aquarium’ for ‘freshwater_aquarium’: an abbreviation, not a naming conflict
        (alias if _norm_name(name) == _norm_name(sort) else mismatch).append({"item_id": iid, "name": name, "sortname": sort})
    groups: dict[str, list[int]] = {}
    for r in R._rows(conn, "SELECT itemid,name FROM item_basic"):
        groups.setdefault(_norm_name(str(r[1])), []).append(int(r[0]))
    clash = [{"norm": k, "ids": v, "names": [str(x[0]) for x in R._rows(conn, f"SELECT name FROM item_basic WHERE itemid IN ({','.join(['%s'] * len(v))})", tuple(v))]}
             for k, v in groups.items() if len(v) > 1 and any(i in ids for i in v) and k]
    cross = []
    other_guilds: dict[int, int] = {}
    if other:
        oc = other[1]
        om = {int(r[0]): str(r[1] or "") for r in R._rows(oc, f"SELECT itemid,name FROM item_basic WHERE itemid IN ({marks})", tuple(ids))}
        cross = [{"item_id": i, "name": items[i][0], "other": om[i]} for i in sorted(items) if i in om and om[i] != items[i][0]]
        other_guilds = {int(r[0]): int(r[1]) for r in R._rows(oc, "SELECT guildid,COUNT(*) FROM guild_shops GROUP BY guildid")}
    counts = {int(r[0]): int(r[1]) for r in R._rows(conn, "SELECT guildid,COUNT(*) FROM guild_shops GROUP BY guildid")}
    guilds = []
    for g in guild_npcs(root):
        guilds.append({**g, "rows": counts.get(g["guild"], 0), "other_rows": other_guilds.get(g["guild"]) if other else None})
    guilds.sort(key=lambda x: (x["rows"], x["guild"]))
    return {"alias": alias, "mismatch": mismatch, "clash": clash[:200], "cross": cross, "other_label": other[0] if other else None,
            "guilds": guilds, "thin_guilds": sum(1 for g in guilds if g["rows"] < 12),
            "note": "Prefix-only aliases (‘sprig_of_fresh_marjoram’ vs ‘fresh_marjoram’) are expected but break any name-based matching. A guild NPC with few guild_shops rows is a vendor gap: the shop script calls sendGuild but the table holds almost no stock for it."}


def vendor_candidates(conn, root, others=None, limit: int = 300) -> dict[str, Any]:
    """Missing ingredients matched to the thin guild shops that probably should stock them.

    Evidence only: a guild's craft is the craft whose recipes use most of the items it already sells; an item's craft is the craft
    of the recipes that need it. `others` = [(label, connection)] — a hit there is direct proof another environment stocks it.
    """
    cols = R.table_columns(conn)
    rows = [R._canon(R._row_dict(cols, r)) for r in R._rows(conn, "SELECT * FROM `synth_recipes`")]
    synth = [r for r in rows if not r["desynth"]]
    av = R.Availability(conn, root)
    item_craft: dict[int, Counter] = defaultdict(Counter)
    item_recipes: Counter = Counter()
    for r in synth:
        crafts = [c for c, v in r["skills"].items() if v]
        for iid in set(r["ingredients"]):
            item_recipes[iid] += 1
            for c in crafts:
                item_craft[iid][c] += 1
    stock: dict[int, list[int]] = defaultdict(list)
    for g, i in R._rows(conn, "SELECT guildid,itemid FROM guild_shops"):
        stock[int(g)].append(int(i))
    guild_craft: dict[int, str] = {}
    for g, its in stock.items():
        tally: Counter = Counter()
        for i in its:
            tally.update(item_craft.get(i, {}))
        if tally:
            guild_craft[g] = tally.most_common(1)[0][0]
    npcs: dict[int, list[str]] = defaultdict(list)
    for n in guild_npcs(root):
        if n["craft"]:
            guild_craft[n["guild"]] = n["craft"]         # the NPC script header names its guild: stronger than inferring from stock
        npcs[n["guild"]].append(f"{n['npc'].replace('_', ' ')} ({n['zone'].replace('_', ' ')})")
    missing = [i for i in item_recipes if av.status(i) == "missing"]
    names = R.item_names(conn, set(missing))
    meta = {int(r[0]): (int(r[1] or 0), int(r[2] or 0)) for r in R._rows(conn, f"SELECT itemid,stackSize,BaseSell FROM item_basic WHERE itemid IN ({','.join(['%s'] * len(missing)) or 'NULL'})", tuple(missing))}
    out = []
    for iid in sorted(missing, key=lambda i: -item_recipes[i])[:max(1, min(limit, 1000))]:
        craft = item_craft[iid].most_common(1)[0][0] if item_craft[iid] else ""
        cands = sorted(({"guild": g, "rows": len(stock[g]), "npcs": npcs.get(g, [])} for g, c in guild_craft.items() if c == craft and len(stock[g]) < 40),
                       key=lambda x: x["rows"])[:4]
        proof = []
        for label, oc in others or []:
            for g, price in R._rows(oc, "SELECT guildid,min_price FROM guild_shops WHERE itemid=%s", (iid,)):
                proof.append({"env": label, "guild": int(g), "price": int(price)})
        out.append({"item_id": iid, "name": names.get(iid, ""), "recipes": item_recipes[iid], "craft": craft, "guilds": cands, "proof": proof,
                    "staple": meta.get(iid, (0, 0))[0] >= 12 and meta.get(iid, (0, 0))[1] <= 1000})
    out.sort(key=lambda x: (not x["proof"], not x["staple"], -x["recipes"]))
    return {"count": len(missing), "items": out, "guild_craft": {str(g): c for g, c in sorted(guild_craft.items())},
            "note": "Candidate guilds are an inference (same craft, thin stock), not a fact. ‘Proof’ means another environment's guild_shops stocks the item."}
