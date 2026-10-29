"""Voidwalker domain: parses the generated DSP data file + NM scripts, cross-checks the live DB."""
from __future__ import annotations
import datetime, json, re, sqlite3
from pathlib import Path

from workbench.runtime.local_roots import dsp_root

DATA = Path(__file__).resolve().parents[3] / "data" / "voidwalker"
VALID = DATA / "validation.json"
BACKLOG = DATA / "backlog.json"
KI = {"CLEAR_ABYSSITE": 1253, "COLORFUL_ABYSSITE": 1254, "BLUE_ABYSSITE": 1255, "ORANGE_ABYSSITE": 1256, "BROWN_ABYSSITE": 1257,
      "YELLOW_ABYSSITE": 1258, "PURPLE_ABYSSITE": 1259, "BLACK_ABYSSITE": 1260, "GREY_ABYSSITE": 1590}
TIERS = [["CLEAR_ABYSSITE"], ["COLORFUL_ABYSSITE"],
         ["BLUE_ABYSSITE", "ORANGE_ABYSSITE", "BROWN_ABYSSITE", "YELLOW_ABYSSITE", "PURPLE_ABYSSITE", "GREY_ABYSSITE"], ["BLACK_ABYSSITE"]]
AREAS = [["pop", "Pop with abyssite"], ["hint", "Hint message"], ["fight", "Targetable and fights"],
         ["model", "Model, name, skills"], ["drops", "Drops"], ["upgrade", "Abyssite upgrade"]]
STATES = ["untested", "ok", "issue", "n/a"]
_ZONE = re.compile(r"^VOIDWALKER_DATA\[(\d+)\] = \{ -- (\S+)", re.M)
_TXT = re.compile(r"(\w+) = (\d+),")
_MOB = re.compile(r"^\s*(\d{8}), -- (.+)$")


def _root(r=None):
    return Path(r) if r else (dsp_root() or Path("<dsp-root-not-configured>"))


def parse_data(root: Path) -> list[dict]:
    f = root / "scripts/globals/voidwalker_data.lua"
    if not f.exists():
        return []
    parts = _ZONE.split(f.read_text(encoding="utf-8", errors="ignore"))
    zones = []
    for i in range(1, len(parts), 3):
        zid, folder, body = int(parts[i]), parts[i + 1], parts[i + 2]
        tm = re.search(r"text = \{(.*?)\}", body, re.S)
        text = {k: int(v) for k, v in _TXT.findall(tm.group(1))} if tm else {}
        mobs, cur = [], None
        mb = re.search(r"mobs = \{(.*?)\n    \},", body, re.S)
        for line in (mb.group(1) if mb else "").splitlines():
            m = re.match(r"\s*\[(\w+)\] = \{", line)
            if m:
                cur = m.group(1)
                continue
            m = _MOB.match(line)
            if m and cur:
                mobs.append({"id": int(m.group(1)), "name": m.group(2).strip(), "abyssite": cur})
        pm = re.search(r"pos = \{(.*?)\n    \},", body, re.S)
        npos = len(re.findall(r"\{\s*-?\d+", pm.group(1))) if pm else 0
        plist = [[int(a), int(b), int(c)] for a, b, c in re.findall(r"\{\s*(-?\d+)\s*,\s*(-?\d+)\s*,\s*(-?\d+)\s*\}", pm.group(1))] if pm else []
        zones.append({"zone_id": zid, "folder": folder, "text": text, "mobs": mobs, "positions": npos, "pos_list": plist})
    return zones


def script_info(root: Path, folder: str, name: str) -> dict:
    p = root / "scripts/zones" / folder / "mobs" / (name.replace(" ", "_").replace("'", "") + ".lua")
    if not p.exists():
        return {"exists": False, "upgrade": None}
    t = p.read_text(encoding="utf-8", errors="ignore")
    m = re.search(r"voidwalker\.onMobDeath\([^)]*?,\s*(\w+)\s*\)", t)
    return {"exists": True, "upgrade": (m.group(1) if m and m.group(1) != "nil" else None)}


def _validation():
    try:
        return json.loads(VALID.read_text(encoding="utf-8")) if VALID.exists() else {}
    except ValueError:
        return {}


def vstatus(rec):
    a = (rec or {}).get("areas", {})
    v = [a.get(k, "untested") for k, _ in AREAS]
    if "issue" in v:
        return "issue"
    if all(x in ("ok", "n/a") for x in v):
        return "validated"
    return "partial" if "ok" in v else "unvalidated"


def _db(conn, ids):
    out = {}
    if conn is None or not ids:
        return out
    cur = conn.cursor()
    cur.execute("select mobid,pos_x,pos_y,pos_z,groupid from mob_spawn_points where mobid in (%s)" % ",".join(["%s"] * len(ids)), tuple(ids))
    for mid, x, y, z, g in cur.fetchall():
        out[int(mid)] = {"pos": [float(x), float(y), float(z)], "groupid": int(g)}
    gids = {v["groupid"] for v in out.values()}
    gm, pn = {}, {}
    if gids:
        cur.execute("select groupid,poolid,HP,dropid from mob_groups where groupid in (%s)" % ",".join(["%s"] * len(gids)), tuple(gids))
        gm = {int(a): (int(b), int(c), int(d)) for a, b, c, d in cur.fetchall()}
        pools = {g[0] for g in gm.values()}
        if pools:
            cur.execute("select poolid,name from mob_pools where poolid in (%s)" % ",".join(["%s"] * len(pools)), tuple(pools))
            pn = {int(a): b for a, b in cur.fetchall()}
    dids = {g[2] for g in gm.values() if g[2]}
    drops = {}
    if dids:
        cur.execute("select d.dropid,d.dropType,d.groupId,d.groupRate,d.itemId,d.itemRate,coalesce(i.sortname,i.name) from mob_droplist d left join item_basic i on i.itemid=d.itemId where d.dropid in (%s)" % ",".join(["%s"] * len(dids)), tuple(dids))
        for did, dt, gi, gr, it, ir, nm in cur.fetchall():
            drops.setdefault(int(did), []).append({"type": int(dt), "group": int(gi), "group_rate": int(gr), "item": int(it), "rate": int(ir), "name": (nm or "").replace("_", " ")})
    for v in out.values():
        g = gm.get(v["groupid"])
        v["poolid"], v["hp"] = (g[0], g[1]) if g else (None, None)
        v["dropid"] = g[2] if g else None
        v["drops"] = drops.get(g[2], []) if g else []
        v["pool_name"] = pn.get(v["poolid"]) if g else None
    return out


ZONE_DB = Path(__file__).resolve().parents[3] / "ffxi_zone_database.db"
NPC = {"name": "Assai Nybaem", "zone": "Ru'Lude Gardens", "zone_id": 243, "pos": "G-10 (!pos -34 0 -77)", "event": 10120, "price": 1000,
       "script": "scripts/zones/RuLude_Gardens/npcs/Assai_Nybaem.lua",
       "desc": "Sells the Clear Abyssite (1000 gil) that starts the system; the menu also shows which abyssites you hold. No quest log entry: buying the stone is the start."}
ABYSSEA = ("Exists, not built, not in LSB. FFXIclopedia 'Voidwalker Notorious Monsters/Abyssea' (31 pages, stored) documents a second branch: "
           "same rest-on-the-item pop, but with Demilune Abyssite key items (Clear 1564, Colorful 1565, Scarlet 1566, Azure 1567, Viridian 1568, "
           "Jade 1649, Sapphire 1650, Crimson 1651, Emerald 1652, Vermillion 1653, Indigo 1654; ids identical in LSB and DSP) inside the Abyssea zones "
           "(Attohwa, Misareaux, La Theine, Konschtat, Altepa, Uleguerand, Grauberg, Vunkerl, Tahrongi). Different NMs "
           "(At'euvhi, Es'euvhi, Lusca, Tristitia, Brulo, Ketea, Maere, Ogopogo, Ruminator, Usurper, Hadal Satiator and others), "
           "Per zone: Tier I (Clear pop) -> Tier II (Colorful pop) -> Tier III (zone colour KI pop, drops Atma); 9 zone paths, no merge NM. DSP only references the key items (abyssea.lua, keyitems.lua, Cruor_Prospector). "
           "DECISION 2026-10-16: documented only; Valhalla's customised Abyssea zones are left untouched until the overworld path is finished. Full table: docs/voidwalker/ABYSSEA-BRANCH.md.")


def wiki_coverage(names):
    """Which wiki pages exist locally per NM (BG Wiki, FFXIclopedia, WikiWikiJP) in ffxi_zone_database.db."""
    out = {}
    if not ZONE_DB.exists():
        return out
    try:
        c = sqlite3.connect(str(ZONE_DB))
        have = {}
        for sid, t in c.execute("select source_id,title from reference_wiki_pages where lower(title) in (%s)" % ",".join("?" * len(names)), [n.lower() for n in names]):
            have.setdefault(t.lower(), set()).add(sid)
        c.close()
    except sqlite3.Error:
        return out
    return {n: sorted(have.get(n.lower(), [])) for n in names}


def skills_info(conn, root, names):
    """Per NM pool: skill list id and each skill with whether its Lua exists."""
    out = {}
    if conn is None:
        return out
    cur = conn.cursor(buffered=True)
    for n in names:
        cur.execute("select poolid,skill_list_id from mob_pools where replace(name,'_',' ')=%s", (n,))
        rows = cur.fetchall()
        if not rows:
            continue
        pid, sl = rows[0]
        cur.execute("select s.mob_skill_id,s.mob_skill_name from mob_skill_lists l join mob_skills s using(mob_skill_id) where l.skill_list_id=%s", (sl,))
        sk = [{"id": int(a), "name": b, "lua": (root / "scripts/globals/mobskills" / (b + ".lua")).exists()} for a, b in cur.fetchall()]
        out[n] = {"pool": int(pid), "list": int(sl), "skills": sk}
    return out


def overview(root=None, conn=None) -> dict:
    root = _root(root)
    zones = parse_data(root)
    val = _validation()
    db = _db(conn, [m["id"] for z in zones for m in z["mobs"]])
    nms, listed = [], set()
    for z in zones:
        for m in z["mobs"]:
            s = script_info(root, z["folder"], m["name"])
            listed.add((z["folder"], m["name"].replace(" ", "_").replace("'", "").lower()))
            d = db.get(m["id"])
            gaps = []
            if conn is not None:
                if not d:
                    gaps.append("No mob_spawn_points row")
                else:
                    if d["pos"] == [0.0, 0.0, 0.0]:
                        gaps.append("Spawn at (0,0,0): the loader skips it")
                    if d.get("poolid") is None:
                        gaps.append("Group has no mob_groups row")
                    elif not d.get("pool_name"):
                        gaps.append("Pool missing in mob_pools")
            if d and d.get("poolid") is not None and not d["drops"] and m["abyssite"] not in ("CLEAR_ABYSSITE", "COLORFUL_ABYSSITE"):
                gaps.append("No drop table wired (dropid %s)" % d.get("dropid"))
            if not s["exists"]:
                gaps.append("No NM script")
            elif m["abyssite"] != "BLACK_ABYSSITE" and s["upgrade"] is None:
                gaps.append("Script passes no upgrade abyssite")
            key = "%d:%d" % (z["zone_id"], m["id"])
            nms.append({"key": key, "id": m["id"], "name": m["name"], "zone_id": z["zone_id"], "zone": z["folder"], "abyssite": m["abyssite"],
                        "ki_id": KI.get(m["abyssite"]), "upgrade": s["upgrade"], "has_script": s["exists"], "db": d, "gaps": gaps,
                        "status": "built" if s["exists"] and not gaps else "partial", "validation": vstatus(val.get(key)), "validation_rec": val.get(key)})
    orphans = []
    for z in zones:
        d = root / "scripts/zones" / z["folder"] / "mobs"
        if not d.exists():
            continue
        for f in d.glob("*.lua"):
            try:
                t = f.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            if "voidwalker.onMobDeath" in t and (z["folder"], f.stem.lower()) not in listed:
                orphans.append("%s/%s" % (z["folder"], f.name))
    try:
        backlog = json.loads(BACKLOG.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        backlog = []
    tiers = [{"names": t, "count": sum(1 for n in nms if n["abyssite"] in t),
              "nm": len({n["name"] for n in nms if n["abyssite"] in t}),
              "built": sum(1 for n in nms if n["abyssite"] in t and n["status"] == "built")} for t in TIERS]
    names = sorted({n["name"] for n in nms})
    import json as _j
    try: aby=_j.load(open(Path(__file__).resolve().parents[3]/"data"/"voidwalker"/"abyssea.json",encoding="utf-8"))
    except Exception: aby=[]
    from .voidwalker_coverage import summarize as summarize_validation
    return {"validation_coverage": summarize_validation(nms), "abyssea_paths": aby, "npc": NPC, "abyssea": ABYSSEA, "wiki": wiki_coverage(names + ["Voidwalker", "Making Contact", "Assai Nybaem"]),
            "skills": skills_info(conn, root, names), "root": str(root), "areas": AREAS, "states": STATES, "tiers": tiers, "ki": KI, "nms": nms, "orphans": orphans, "backlog": backlog,
            "zones": [{"zone_id": z["zone_id"], "folder": z["folder"], "nms": len(z["mobs"]), "positions": z["positions"], "pos_list": z["pos_list"], "text": len(z["text"])} for z in zones],
            "db_checked": conn is not None,
            "note": "Abyssite ids are DSP keyitems.lua, not client-verified. Positions are LSB and not yet !checknav-verified."}


def save_validation(key: str, areas: dict, note: str) -> dict:
    clean = {k: (areas.get(k) if areas.get(k) in STATES else "untested") for k, _ in AREAS}
    data = _validation()
    data[key] = {"areas": clean, "note": note[:2000], "updated": datetime.datetime.now().isoformat(timespec="seconds")}
    DATA.mkdir(parents=True, exist_ok=True)
    tmp = VALID.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=1, sort_keys=True), encoding="utf-8")
    tmp.replace(VALID)
    return data[key]
