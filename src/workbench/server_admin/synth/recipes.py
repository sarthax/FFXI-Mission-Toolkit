"""Synth/crafting recipe module: read, validate, availability-check and SQL-generate over `synth_recipes`.

The table differs per server family, so everything is driven by SHOW COLUMNS:
  DSP    : `Type` (1 = synth, 0 = desynth, inferred from the data), KeyItem, no ResultName
  Topaz  : `Desynth` (1 = desynth), KeyItem, ResultName
  LSB    : `Desynth`, KeyItem, ResultName, content_tag
Nothing here writes; `build_sql` only produces statements and `apply_sql` is called by the API behind the write gate.
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import Any

CRAFTS = ("Wood", "Smith", "Gold", "Cloth", "Leather", "Bone", "Alchemy", "Cook")
INGREDIENTS = tuple(f"Ingredient{n}" for n in range(1, 9))
RESULTS = ("Result", "ResultHQ1", "ResultHQ2", "ResultHQ3")
QTYS = ("ResultQty", "ResultHQ1Qty", "ResultHQ2Qty", "ResultHQ3Qty")
FLAVORS = ("dsp", "topaz", "lsb")

_AVAIL_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}


def _rows(conn, sql: str, params: tuple = ()) -> list[tuple]:
    cur = conn.cursor()
    try:
        cur.execute(sql, params)
        return list(cur.fetchall() or [])
    finally:
        cur.close()


def table_columns(conn) -> list[str]:
    return [str(r[0]) for r in _rows(conn, "SHOW COLUMNS FROM `synth_recipes`")]


def detect_flavor(cols: list[str]) -> str:
    s = set(cols)
    if "Type" in s and "Desynth" not in s:
        return "dsp"
    return "lsb" if "content_tag" in s else "topaz"


def _is_desynth(row: dict[str, Any]) -> bool:
    if "Desynth" in row:
        return int(row["Desynth"] or 0) == 1
    return int(row.get("Type") or 0) == 0


def _row_dict(cols: list[str], r: tuple) -> dict[str, Any]:
    return {c: r[i] for i, c in enumerate(cols)}


def _canon(row: dict[str, Any]) -> dict[str, Any]:
    """Flavor-neutral recipe view used by the UI."""
    skills = {c: int(row.get(c) or 0) for c in CRAFTS}
    return {
        "id": int(row["ID"]), "desynth": _is_desynth(row), "key_item": int(row.get("KeyItem") or 0),
        "skills": skills, "crystal": int(row.get("Crystal") or 0), "hq_crystal": int(row.get("HQCrystal") or 0),
        "ingredients": [int(row.get(c) or 0) for c in INGREDIENTS if int(row.get(c) or 0)],
        "results": [{"item_id": int(row.get(r) or 0), "qty": int(row.get(q) or 0)} for r, q in zip(RESULTS, QTYS)],
        "result_name": row.get("ResultName"), "content_tag": row.get("content_tag"),
    }


def item_names(conn, ids: set[int]) -> dict[int, str]:
    out: dict[int, str] = {}
    ids = sorted(i for i in ids if i)
    for n in range(0, len(ids), 400):
        part = ids[n:n + 400]
        for r in _rows(conn, f"SELECT itemid,name FROM item_basic WHERE itemid IN ({','.join(['%s'] * len(part))})", tuple(part)):
            out[int(r[0])] = str(r[1] or "")
    return out


def _decorate(conn, recipes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ids: set[int] = set()
    for r in recipes:
        ids.update(r["ingredients"]); ids.update((r["crystal"], r["hq_crystal"]))
        ids.update(x["item_id"] for x in r["results"])
    names = item_names(conn, ids)
    for r in recipes:
        r["crystal_name"] = names.get(r["crystal"], ""); r["hq_crystal_name"] = names.get(r["hq_crystal"], "")
        r["ingredient_names"] = [names.get(i, f"#{i} (not in item_basic)") for i in r["ingredients"]]
        for x in r["results"]:
            x["name"] = names.get(x["item_id"], "") if x["item_id"] else ""
        r["name"] = r["results"][0]["name"] or (r.get("result_name") or "")
        r["craft"] = max(CRAFTS, key=lambda c: r["skills"][c]) if any(r["skills"].values()) else ""
        r["level"] = r["skills"].get(r["craft"], 0) if r["craft"] else 0
    return recipes


def list_recipes(conn, *, craft: str = "", min_skill: int = 0, max_skill: int = 200, q: str = "", mode: str = "synth",
                 item_id: int = 0, role: str = "any", limit: int = 100, offset: int = 0, with_status: bool = False, root=None) -> dict[str, Any]:
    cols = table_columns(conn)
    flavor = detect_flavor(cols)
    where, params = ["1=1"], []
    if mode in ("synth", "desynth"):
        want = 1 if mode == "desynth" else 0
        where.append(f"s.`Desynth`={want}" if "Desynth" in cols else f"s.`Type`={0 if mode == 'desynth' else 1}")
    if craft in CRAFTS:
        where.append(f"s.`{craft}`>=%s AND s.`{craft}`<=%s AND s.`{craft}`>0"); params += [max(0, int(min_skill)), max(0, int(max_skill))]
    ing = " OR ".join(f"s.`{c}`=%s" for c in INGREDIENTS)
    res = " OR ".join(f"s.`{c}`=%s" for c in RESULTS)
    if item_id:
        item_id = int(item_id)
        if role == "result":
            where.append(f"({res})"); params += [item_id] * 4
        elif role == "ingredient":
            where.append(f"({ing} OR s.`Crystal`=%s)"); params += [item_id] * 9
        else:
            where.append(f"({ing} OR {res} OR s.`Crystal`=%s)"); params += [item_id] * 13
    if q.strip():
        like = "%" + q.strip().replace(" ", "_").replace("%", "") + "%"
        ids = [int(r[0]) for r in _rows(conn, "SELECT itemid FROM item_basic WHERE name LIKE %s OR sortname LIKE %s LIMIT 400", (like, like))]
        if not ids:
            return {"flavor": flavor, "columns": cols, "total": 0, "recipes": []}
        ph = ",".join(["%s"] * len(ids))
        where.append("(" + " OR ".join(f"s.`{c}` IN ({ph})" for c in (*RESULTS, *INGREDIENTS)) + ")"); params += ids * 12
    w = " AND ".join(where)
    total = int(_rows(conn, f"SELECT COUNT(*) FROM `synth_recipes` s WHERE {w}", tuple(params))[0][0])
    rows = _rows(conn, f"SELECT s.* FROM `synth_recipes` s WHERE {w} ORDER BY s.`ID` LIMIT %s OFFSET %s",
                 (*params, max(1, min(int(limit), 500)), max(0, int(offset))))
    recipes = _decorate(conn, [_canon(_row_dict(cols, r)) for r in rows])
    if with_status:
        av = Availability(conn, root)
        for r in recipes:
            sts = [av.status(i) for i in (r["crystal"], *r["ingredients"]) if i]
            r["status"] = next((s for s in ("missing", "ah_only", "script") if s in sts), "ok")
    return {"flavor": flavor, "columns": cols, "total": total, "recipes": recipes}


def get_recipe(conn, recipe_id: int) -> dict[str, Any] | None:
    cols = table_columns(conn)
    rows = _rows(conn, "SELECT * FROM `synth_recipes` WHERE `ID`=%s", (int(recipe_id),))
    if not rows:
        return None
    r = _decorate(conn, [_canon(_row_dict(cols, rows[0]))])[0]
    r["flavor"] = detect_flavor(cols)
    return r


# ---------------------------------------------------------------- availability
def _sources(conn, root: Path | str | None) -> dict[str, Any]:
    key = f"{root}"
    hit = _AVAIL_CACHE.get(key)
    if hit and time.time() - hit[0] < 120:
        return hit[1]
    from workbench.server_admin.auction_house.arbitrage import scan_vendor_prices

    vendors: dict[int, dict[str, Any]] = dict(scan_vendor_prices(root)["items"]) if root else {}
    try:
        for r in _rows(conn, "SELECT guildid,itemid,min_price FROM guild_shops"):
            iid = int(r[1])
            if iid not in vendors or int(r[2]) < vendors[iid]["price"]:
                vendors[iid] = {"price": int(r[2]), "vendor": f"Guild #{int(r[0])}", "zone": "", "kind": "GUILD"}
    except Exception:
        pass
    # A drop only counts when the chain droplist -> mob group -> spawn point exists (zone is encoded in mobid bits 12-23).
    drops: dict[int, dict[str, Any]] = {}
    any_drop: set[int] = set()
    try:
        any_drop = {int(r[0]) for r in _rows(conn, "SELECT DISTINCT itemId FROM mob_droplist")}
        for r in _rows(conn, "SELECT d.itemId, p.name, g.zoneid, COUNT(*) FROM mob_droplist d JOIN mob_groups g ON g.dropid=d.dropId "
                             "JOIN mob_pools p ON p.poolid=g.poolid JOIN mob_spawn_points sp ON sp.groupid=g.groupid AND ((sp.mobid>>12)&4095)=g.zoneid "
                             "GROUP BY d.itemId, p.name, g.zoneid ORDER BY d.itemId, COUNT(*) DESC"):
            e = drops.setdefault(int(r[0]), {"mobs": 0, "sample": []})
            e["mobs"] += 1
            if len(e["sample"]) < 3:
                e["sample"].append({"mob": str(r[1] or ""), "zone_id": int(r[2])})
    except Exception:
        pass
    bcnm: set[int] = set()
    try:
        bcnm = {int(r[0]) for r in _rows(conn, "SELECT DISTINCT l.itemId FROM bcnm_loot l JOIN bcnm_info i ON i.lootDropId=l.LootDropId")}
    except Exception:
        pass
    ah: dict[int, dict[str, int]] = {}
    try:
        for r in _rows(conn, "SELECT itemid,COUNT(*),MIN(price) FROM auction_house WHERE sell_date=0 AND stack=0 GROUP BY itemid"):
            ah[int(r[0])] = {"count": int(r[1]), "min": int(r[2])}
    except Exception:
        pass
    cols = table_columns(conn)
    where = "`Desynth`=0" if "Desynth" in cols else "`Type`=1"
    crafted: dict[int, list[int]] = {}
    for r in _rows(conn, f"SELECT `ID`,`Result`,`ResultHQ1`,`ResultHQ2`,`ResultHQ3` FROM `synth_recipes` WHERE {where}"):
        for iid in {int(x) for x in r[1:] if x}:
            crafted.setdefault(iid, []).append(int(r[0]))
    out = {"vendors": vendors, "drops": drops, "orphan_drops": any_drop - set(drops), "bcnm": bcnm, "ah": ah, "crafted": crafted, "cols": cols, "scripts": {}, "scripts_root": root}
    _AVAIL_CACHE[key] = (time.time(), out)
    return out


_SCRIPT_SKIP = ("globals/items/", "globals/spells/", "globals/abilities/", "globals/effects/", "globals/mixins/", "mixins/", "commands/")
_GATHER = ("mining", "harvesting", "logging", "excavation", "chocobo_digging", "fishing", "digging")


def _script_kind(rel: str) -> str:
    low = rel.lower()
    for key, label in (("campaign", "campaign reward"), ("besieged", "besieged reward"), ("abyssea", "Abyssea"), ("moghouse", "mog house / garden"), ("garden", "mog house / garden")):
        if key in low:
            return label
    if "/npcs/" in low:
        return "NPC / quest script"
    if "/mobs/" in low:
        return "mob / NM script"
    if any(g in low for g in _GATHER):
        return "gathering script"
    if "quest" in low or "mission" in low:
        return "quest / mission script"
    return "other script"


def script_references(root, wanted: set[int]) -> dict[int, list[dict[str, str]]]:
    """Lua files that mention an item id as a number. LOW confidence: it proves a script knows the id, not that it grants it."""
    import re
    out: dict[int, list[dict[str, str]]] = {}
    if not root:
        return out
    base = Path(root) / "scripts"
    num = re.compile(r"(?<![\w.])(\d{2,5})(?![\w.])")
    grant_line = re.compile(r"addItem|giveItem|addTempItem|dropItem|reward|treasure|\bitem\w*\s*=", re.I)
    pair = re.compile(r"\{\s*\d+\s*,\s*(\d{2,5})\s*\}")
    for path in base.rglob("*.lua"):
        rel = str(path.relative_to(base)).replace("\\", "/")
        if any(s in rel for s in _SCRIPT_SKIP) or rel.endswith(("IDs.lua", "keyitems.lua", "log_ids.lua", "settings.lua")):
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        found: set[int] = set()
        for line in text.splitlines():
            code = line.split("--", 1)[0]
            if grant_line.search(code):
                found.update(int(m) for m in num.findall(code))
        if any(g in rel.lower() for g in _GATHER) or "treasure" in rel.lower() or "strangeapparatus" in rel.lower():
            found.update(int(m) for m in pair.findall(text))
        for n in found & wanted:
            lst = out.setdefault(n, [])
            if len(lst) < 4:
                lst.append({"file": rel, "kind": _script_kind(rel)})
    return out


class Availability:
    """Per-item acquisition lookup with a recursive 'can it be crafted' check (cycle safe, memoized)."""

    def __init__(self, conn, root, recipes_by_id: dict[int, dict[str, Any]] | None = None):
        self.src = _sources(conn, root)
        self.conn = conn
        self.recipes: dict[int, dict[str, Any]] = recipes_by_id if recipes_by_id is not None else self._load_recipes()
        self._memo: dict[int, bool] = {}
        self._soft: dict[int, bool] = {}
        if self.src.get("scripts_root") is not None and not self.src["scripts"]:
            wanted = {i for rc in self._all_recipes() for i in (rc["crystal"], *rc["ingredients"]) if i}
            self.src["scripts"] = script_references(self.src["scripts_root"], wanted) or {-1: []}

    def _all_recipes(self):
        cols = self.src["cols"]
        return [_canon(_row_dict(cols, r)) for r in _rows(self.conn, "SELECT * FROM `synth_recipes`")]

    def _load_recipes(self) -> dict[int, dict[str, Any]]:
        cols = self.src["cols"]
        where = "`Desynth`=0" if "Desynth" in cols else "`Type`=1"
        return {int(r[0]): _canon(_row_dict(cols, r)) for r in _rows(self.conn, f"SELECT * FROM `synth_recipes` WHERE {where}")}

    def direct(self, item_id: int) -> dict[str, Any]:
        v = self.src["vendors"].get(item_id)
        ah = self.src["ah"].get(item_id)
        return {
            "vendor": ({"price": v["price"], "vendor": v["vendor"], "zone": v["zone"]} if v else None),
            "drops": self.src["drops"].get(item_id),
            "orphan_drop": item_id in self.src["orphan_drops"],
            "bcnm": item_id in self.src["bcnm"],
            "scripts": self.src["scripts"].get(item_id, []),
            "ah": ah, "recipes": self.src["crafted"].get(item_id, []),
            "engine": 4096 <= item_id <= 4111,
        }

    def obtainable(self, item_id: int, _stack: tuple[int, ...] = ()) -> bool:
        """True when there is a durable route: vendor, mob drop, or a recipe whose inputs are all obtainable."""
        if item_id in self._memo:
            return self._memo[item_id]
        d = self.direct(item_id)
        ok = bool(d["vendor"] or d["drops"] or d["bcnm"] or d["engine"])
        if not ok and item_id not in _stack:
            for rid in d["recipes"][:6]:
                rc = self.recipes.get(rid)
                if rc and all(self.obtainable(i, (*_stack, item_id)) for i in [rc["crystal"], *rc["ingredients"]] if i):
                    ok = True
                    break
        if not _stack:
            self._memo[item_id] = ok
        return ok

    def soft(self, item_id: int, _stack: tuple[int, ...] = ()) -> bool:
        """Like obtainable(), but a script reference (quest/NM/gathering) also counts."""
        if item_id in self._soft:
            return self._soft[item_id]
        d = self.direct(item_id)
        ok = self.obtainable(item_id) or bool(d["scripts"])
        if not ok and item_id not in _stack:
            for rid in d["recipes"][:6]:
                rc = self.recipes.get(rid)
                if rc and all(self.soft(i, (*_stack, item_id)) for i in [rc["crystal"], *rc["ingredients"]] if i):
                    ok = True
                    break
        if not _stack:
            self._soft[item_id] = ok
        return ok

    def status(self, item_id: int) -> str:
        d = self.direct(item_id)
        if self.obtainable(item_id):
            return "ok"
        if self.soft(item_id):
            return "script"
        return "ah_only" if d["ah"] else "missing"


def check_recipe(conn, root, recipe_id: int) -> dict[str, Any] | None:
    rc = get_recipe(conn, recipe_id)
    if rc is None:
        return None
    av = Availability(conn, root)
    needs: dict[int, int] = {}
    for iid in [rc["crystal"], *rc["ingredients"]]:
        if iid:
            needs[iid] = needs.get(iid, 0) + 1
    names = item_names(conn, set(needs))
    lines, cost, cost_known, missing = [], 0, True, []
    for iid, qty in needs.items():
        d = av.direct(iid)
        st = av.status(iid)
        unit = d["vendor"]["price"] if d["vendor"] else (d["ah"]["min"] if d["ah"] else None)
        line = {"item_id": iid, "name": names.get(iid, f"#{iid} (not in item_basic)"), "qty": qty, "status": st,
                "vendor": d["vendor"], "drops": d["drops"], "orphan_drop": d["orphan_drop"], "engine": d["engine"], "bcnm": d["bcnm"], "scripts": d["scripts"], "ah": d["ah"], "recipes": d["recipes"][:5], "unit_cost": unit,
                "in_item_basic": iid in names}
        if unit is None:
            cost_known = False
        else:
            cost += unit * qty
        if st == "missing" or iid not in names:
            missing.append(line["name"])
        lines.append(line)
    craftable = all(l["status"] != "missing" and l["in_item_basic"] for l in lines)
    return {"recipe": rc, "lines": lines, "craftable": craftable, "missing": missing,
            "estimated_cost": cost, "cost_complete": cost_known,
            "note": "Hard sources: shop scripts, guild shops, drops wired to a spawning mob, BCNM loot, other recipes. Script references (quests, NMs, gathering) are low confidence: a Lua file mentions the id. AH listings never count as a source."}


def audit(conn, root, *, limit: int = 300, mode: str = "synth") -> dict[str, Any]:
    cols = table_columns(conn)
    where = "1=1" if mode == "all" else (("`Desynth`=" + ("1" if mode == "desynth" else "0")) if "Desynth" in cols else ("`Type`=" + ("0" if mode == "desynth" else "1")))
    rows = [_canon(_row_dict(cols, r)) for r in _rows(conn, f"SELECT * FROM `synth_recipes` WHERE {where} ORDER BY `ID`")]
    av = Availability(conn, root)
    known = set(item_names(conn, {i for r in rows for i in (*r["ingredients"], r["crystal"], *[x["item_id"] for x in r["results"]]) if i}))
    bad, counts = [], {"ok": 0, "script": 0, "ah_only": 0, "missing": 0, "bad_item": 0}
    for r in rows:
        inputs = [i for i in (r["crystal"], *r["ingredients"]) if i]
        invalid = [i for i in inputs + [x["item_id"] for x in r["results"] if x["item_id"]] if i not in known]
        gaps = [i for i in inputs if i in known and av.status(i) != "ok"]
        if invalid:
            counts["bad_item"] += 1
        elif any(av.status(i) == "missing" for i in gaps):
            counts["missing"] += 1
        elif any(av.status(i) == "ah_only" for i in gaps):
            counts["ah_only"] += 1
        elif gaps:
            counts["script"] += 1
        else:
            counts["ok"] += 1
            continue
        bad.append({"id": r["id"], "result": r["results"][0]["item_id"], "invalid": invalid,
                    "gaps": [{"item_id": i, "status": av.status(i)} for i in gaps]})
    names = item_names(conn, {x["result"] for x in bad} | {g["item_id"] for x in bad for g in x["gaps"]} | {i for x in bad for i in x["invalid"]})
    for x in bad:
        x["name"] = names.get(x["result"], ""); x["gaps"] = [{**g, "name": names.get(g["item_id"], "")} for g in x["gaps"]]
    bad.sort(key=lambda x: (0 if x["invalid"] else 1, -sum(g["status"] == "missing" for g in x["gaps"])))
    return {"total": len(rows), "counts": counts, "problems": bad[:max(1, min(limit, 2000))], "problem_count": len(bad),
            "note": "‘missing’ = no vendor, guild shop, wired mob drop, BCNM loot, craft route or script reference. ‘script’ = only a Lua file mentions it (quest/NM/gathering) — verify by hand."}


# ---------------------------------------------------------------- edit / SQL
def _int(v: Any, lo: int, hi: int, label: str, errors: list[str]) -> int:
    try:
        n = int(v or 0)
    except (TypeError, ValueError):
        errors.append(f"{label} must be a whole number"); return 0
    if not lo <= n <= hi:
        errors.append(f"{label} must be {lo}–{hi}")
    return n


def validate(conn, payload: dict[str, Any], *, creating: bool) -> tuple[dict[str, Any], list[str], list[str]]:
    """Return (clean canonical recipe, errors, warnings). Every item id must exist in item_basic."""
    errors: list[str] = []; warnings: list[str] = []
    cols = table_columns(conn)
    desynth = bool(payload.get("desynth"))
    sk_in = payload.get("skills") or {}
    skills = {c: _int(sk_in.get(c), 0, 255, f"{c} skill", errors) for c in CRAFTS}
    if not any(skills.values()):
        errors.append("At least one craft skill level is required")
    ings = [_int(x, 0, 65535, "Ingredient", errors) for x in (payload.get("ingredients") or [])][:8]
    ings = [i for i in ings if i]
    if not ings:
        errors.append("At least one ingredient is required")
    if len(payload.get("ingredients") or []) > 8:
        errors.append("A recipe holds at most 8 ingredients")
    crystal = _int(payload.get("crystal"), 0, 65535, "Crystal", errors)
    hqc = _int(payload.get("hq_crystal"), 0, 65535, "HQ crystal", errors)
    if crystal not in range(4096, 4104):
        errors.append("Crystal must be one of the 8 elemental crystals (Fire, Ice, Wind, Earth, Lightning, Water, Light, Dark; item ids 4096-4103)")
    if hqc not in range(4238, 4246):
        errors.append("HQ crystal is required and must be one of Inferno, Terra, Torrent, Cyclone, Glacier, Plasma, Aurora, Twilight (item ids 4238-4245)")
    res_in = (payload.get("results") or [])[:4]
    results = []
    for n in range(4):
        x = res_in[n] if n < len(res_in) else {}
        results.append({"item_id": _int(x.get("item_id"), 0, 65535, f"Result tier {n}", errors), "qty": _int(x.get("qty"), 0, 99, f"Result tier {n} quantity", errors)})
    if not results[0]["item_id"] or not results[0]["qty"]:
        errors.append("Result (NQ) item and quantity are required")
    for n in (1, 2, 3):
        if not results[n]["item_id"]:
            results[n] = dict(results[0]); warnings.append(f"HQ tier {n} was empty; copied the NQ result (the client convention)")
        elif not results[n]["qty"]:
            results[n]["qty"] = 1
    key_item = _int(payload.get("key_item"), 0, 4294967295, "Key item", errors) if "KeyItem" in cols else 0
    rec = {"id": int(payload.get("id") or 0), "desynth": desynth, "key_item": key_item, "skills": skills, "crystal": crystal, "hq_crystal": hqc or crystal,
           "ingredients": ings, "results": results, "result_name": str(payload.get("result_name") or "")[:255], "comment": clean_comment(payload.get("comment")), "content_tag": (str(payload.get("content_tag") or "")[:14] or None)}
    check = {i for i in [crystal, hqc, *ings, *[x["item_id"] for x in results]] if i}
    names = item_names(conn, check)
    for i in sorted(check - set(names)):
        errors.append(f"Item id {i} does not exist in item_basic")
    if not rec["result_name"] and results[0]["item_id"] in names:
        rec["result_name"] = names[results[0]["item_id"]]
    if creating:
        if rec["id"]:
            if _rows(conn, "SELECT 1 FROM `synth_recipes` WHERE `ID`=%s", (rec["id"],)):
                errors.append(f"Recipe ID {rec['id']} already exists")
        else:
            rec["id"] = int(_rows(conn, "SELECT COALESCE(MAX(`ID`),0)+1 FROM `synth_recipes`")[0][0])
        dup = _rows(conn, "SELECT `ID` FROM `synth_recipes` WHERE `Crystal`=%s AND " + " AND ".join(f"`{c}`=%s" for c in INGREDIENTS) + " LIMIT 3",
                    (crystal, *(sorted(ings) + [0] * (8 - len(ings)))))
        if dup:
            warnings.append("Same crystal + ingredients already used by recipe(s) " + ", ".join(str(r[0]) for r in dup) + " — the game would pick one of them")
    elif not _rows(conn, "SELECT 1 FROM `synth_recipes` WHERE `ID`=%s", (rec["id"],)):
        errors.append(f"Recipe ID {rec['id']} does not exist")
    rec["ingredients"] = sorted(ings)  # stored ascending with trailing zeros, as in every shipped recipe
    return rec, errors, warnings


def clean_comment(text: Any) -> str:
    """Free-text note emitted as `-- ` lines above the generated SQL. Control characters are dropped; length is capped."""
    raw = "".join(ch for ch in str(text or "") if ch in "\n" or ch >= " ")
    return "\n".join(line.strip() for line in raw.splitlines() if line.strip())[:500]


def _with_comment(rec: dict[str, Any], sql: str) -> str:
    note = clean_comment(rec.get("comment"))
    return ("\n".join("-- " + ln for ln in note.splitlines()) + "\n" + sql) if note else sql


def _record_values(rec: dict[str, Any], flavor: str) -> dict[str, Any]:
    v: dict[str, Any] = {"ID": rec["id"]}
    if flavor == "dsp":
        v["Type"] = 0 if rec["desynth"] else 1
    else:
        v["Desynth"] = 1 if rec["desynth"] else 0
    v["KeyItem"] = rec["key_item"]
    for c in CRAFTS:
        v[c] = rec["skills"][c]
    v["Crystal"], v["HQCrystal"] = rec["crystal"], rec["hq_crystal"]
    ings = list(rec["ingredients"]) + [0] * (8 - len(rec["ingredients"]))
    for c, x in zip(INGREDIENTS, ings):
        v[c] = x
    for r, q, x in zip(RESULTS, QTYS, rec["results"]):
        v[r], v[q] = x["item_id"], x["qty"]
    if flavor in ("topaz", "lsb"):
        v["ResultName"] = rec.get("result_name") or ""
    if flavor == "lsb":
        v["content_tag"] = rec.get("content_tag")
    return v


def _lit(x: Any) -> str:
    if x is None:
        return "NULL"
    if isinstance(x, str):
        return "'" + x.replace("\\", "\\\\").replace("'", "''") + "'"
    return str(int(x))


def build_sql(rec: dict[str, Any], flavor: str, mode: str = "create") -> str:
    """Exact statement for one recipe in the given server flavor (create/update/delete)."""
    if flavor not in FLAVORS:
        raise ValueError(f"flavor must be one of {', '.join(FLAVORS)}")
    if mode == "delete":
        return _with_comment(rec, f"DELETE FROM `synth_recipes` WHERE `ID`={int(rec['id'])};")
    v = _record_values(rec, flavor)
    if mode == "update":
        sets = ", ".join(f"`{k}`={_lit(x)}" for k, x in v.items() if k != "ID")
        return _with_comment(rec, f"UPDATE `synth_recipes` SET {sets} WHERE `ID`={int(rec['id'])};")
    cols = ",".join(f"`{k}`" for k in v)
    return _with_comment(rec, f"INSERT INTO `synth_recipes` ({cols}) VALUES ({','.join(_lit(x) for x in v.values())});")


def apply_recipe(conn, rec: dict[str, Any], mode: str) -> int:
    """Parameterized write for the ACTIVE table layout. Caller must have passed the write gate."""
    cols = table_columns(conn)
    flavor = detect_flavor(cols)
    cur = conn.cursor()
    try:
        if mode == "delete":
            cur.execute("DELETE FROM `synth_recipes` WHERE `ID`=%s", (rec["id"],))
        else:
            v = {k: x for k, x in _record_values(rec, flavor).items() if k in cols}
            if mode == "update":
                cur.execute("UPDATE `synth_recipes` SET " + ",".join(f"`{k}`=%s" for k in v if k != "ID") + " WHERE `ID`=%s",
                            (*[x for k, x in v.items() if k != "ID"], rec["id"]))
            else:
                cur.execute(f"INSERT INTO `synth_recipes` ({','.join('`' + k + '`' for k in v)}) VALUES ({','.join(['%s'] * len(v))})", tuple(v.values()))
        n = cur.rowcount
        conn.commit()
        _AVAIL_CACHE.clear()
        return int(n)
    finally:
        cur.close()
