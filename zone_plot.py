"""Generic zone plot backend: every mob/NPC spawn row of a zone from the live server DB, plus
navmesh reachability. Reuses nyzul_plot's pure-Python .nav parser (cached per file).

Server-agnostic: the live DB target (Topaz or DSP) is picked via the `zoneplot_server` setting
(settings.py), defaulting to "topaz". Topaz's conf file is conf/map.conf; DSP's is
conf/map_darkstar.conf (confirmed against a real D:\\Claude\\old-dsp-reference checkout,
2026-09-21) -- both use the same `key:  value` mysql_* line format, so one parser covers both.
"""
import re
import sqlite3
from pathlib import Path

import nyzul_plot as nav
import settings

# Conf filenames to try, in order, under whichever server root is active.
CONF_NAMES = ["conf/map.conf", "conf/map_darkstar.conf"]

def get_server() -> str:
    """Which server Zone Plot is currently pointed at: "topaz" or "dsp"."""
    con = sqlite3.connect(str(settings.DB_PATH))
    try:
        v = settings.get(con, "zoneplot_server")
    finally:
        con.close()
    return v if v in ("topaz", "dsp") else "topaz"


def set_server(server: str):
    if server not in ("topaz", "dsp"):
        raise ValueError('server must be "topaz" or "dsp"')
    if server == "dsp" and settings.get_dsp_root() is None:
        raise ValueError("DSP server path isn't configured yet -- set it on the Settings page first")
    con = sqlite3.connect(str(settings.DB_PATH))
    try:
        settings.set_many(con, {"zoneplot_server": server})
    finally:
        con.close()


def _server_root(server=None) -> Path:
    server = server or get_server()
    if server == "dsp":
        root = settings.get_dsp_root()
        if root is None:
            raise ValueError("DSP server path isn't configured yet -- set it on the Settings page first")
        return root
    return settings.get_topaz_root()


def _conf_path(root: Path) -> Path:
    for name in CONF_NAMES:
        p = root / name
        if p.exists():
            return p
    raise FileNotFoundError(f"no mysql conf found under {root} (tried {', '.join(CONF_NAMES)})")


def _nav_dirs(server=None):
    return [_server_root(server) / "navmeshes"]


def _db(server=None):
    try:
        import mysql.connector
    except ModuleNotFoundError:  # toolkit venv has no mysql-connector: borrow it from the user site-packages
        import glob, os, sys
        for d in glob.glob(os.path.expandvars(r"%APPDATA%\Python\Python3*\site-packages")):
            if os.path.isdir(os.path.join(d, "mysql")) and d not in sys.path:
                sys.path.append(d)
        import mysql.connector
    root = _server_root(server)
    c = _conf_path(root).read_text()
    g = lambda k: re.search(k + r":\s*(\S+)", c).group(1)
    return mysql.connector.connect(host=g("mysql_host"), port=int(g("mysql_port")), user=g("mysql_login"),
                                   password=g("mysql_password"), database=g("mysql_database"))


def _columns(cu, table):
    cu.execute(f"describe {table}")
    return {r[0] for r in cu.fetchall()}


def zone_list(server=None):
    db = _db(server); cu = db.cursor()
    cu.execute("select zoneid,name from zone_settings order by zoneid")
    out = [{"id": a, "name": b, "nav": nav_path(b, server) is not None} for a, b in cu.fetchall()]
    cols = _columns(cu, "instance_list")
    zone_col = "instance_zone" if "instance_zone" in cols else ("entrance_zone" if "entrance_zone" in cols else None)
    cu.execute(f"select instanceid,instance_name{',' + zone_col if zone_col else ''} from instance_list order by instanceid")
    rows = cu.fetchall()
    # instance_list's own "zone" column (when it exists at all) is unreliable across servers --
    # Topaz's instance_zone is the real "runs in" zone, but DSP's only column, entrance_zone, is
    # the zone you enter the instance FROM, which is a different zone for e.g. Nyzul Isle (72 vs
    # 77) -- that mismatch was silently emptying the instance dropdown for every DSP zone. The one
    # thing that's always right is the actual entity ids an instance contains, which encode their
    # zone the same way mob_spawn_points/npc_list ids do, so derive the real zone per instance from
    # one of its own instance_entities rows, falling back to the column only for an instance with
    # zero entity rows (e.g. DSP's empty "TEST" instanceid 0).
    cu.execute("select instanceid, min(id) from instance_entities group by instanceid")
    real_zone = {iid: ((sid - 16777216) >> 12) & 511 for iid, sid in cu.fetchall()}
    inst = []
    for row in rows:
        a, b = row[0], row[1]
        col_zone = row[2] if len(row) > 2 else None
        inst.append({"id": a, "name": b, "zone": real_zone.get(a, col_zone)})
    db.close()
    return {"zones": out, "instances": inst, "server": server or get_server()}


def nav_path(zone_name, server=None):
    for d in _nav_dirs(server):
        p = d / f"{zone_name}.nav"
        if p.exists():
            return p
    return None


RADIUS_MOB_MODS = {
    31: ("roam_radius", "ROAM_DISTANCE"),
    47: ("leash_radius", "SPAWN_LEASH"),
    4: ("sight_range", "SIGHT_RANGE"),
    5: ("sound_range", "SOUND_RANGE"),
}
MOBMOD_IDS = {name: mid for mid, (_k, name) in RADIUS_MOB_MODS.items()}


def _mob_detect_values(cu, pool_ids):
    """Per-pool detection setup straight from SQL: mob_pools.aggro / true_detection and the
    family's mob_family_system.detects bitmask (engine DETECT_* flags). {} on schema mismatch."""
    out = {}
    ids = sorted({int(x) for x in pool_ids if x is not None})
    if not ids:
        return out
    try:
        ph = ",".join(["%s"] * len(ids))
        cu.execute(
            f"select p.poolid,p.aggro,p.true_detection,f.detects from mob_pools p "
            f"left join mob_family_system f on f.familyid=p.familyid where p.poolid in ({ph})", tuple(ids))
        for poolid, aggro, true_det, detects in cu.fetchall():
            out[int(poolid)] = {"aggro": int(aggro or 0), "true_detection": int(true_det or 0), "detects": int(detects or 0)}
    except Exception:
        return {}
    return out


def _mob_radius_pool_values(cu, pool_ids):
    """Explicit pool-level roam/leash mob mods only; no engine defaults are invented."""
    out = {}
    if not pool_ids:
        return out
    try:
        cu.execute("describe mob_pool_mods")
        cols = {r[0] for r in cu.fetchall()}
        required = {"poolid", "modid", "value"}
        if not required.issubset(cols):
            return out
        has_kind = "is_mob_mod" in cols
        ids = sorted({int(x) for x in pool_ids if x is not None})
        if not ids:
            return out
        ph = ",".join(["%s"] * len(ids))
        sql = f"select poolid,modid,value{',is_mob_mod' if has_kind else ''} from mob_pool_mods where poolid in ({ph}) and modid in (31,47,4,5)"
        cu.execute(sql, tuple(ids))
        for row in cu.fetchall():
            poolid, modid, value = int(row[0]), int(row[1]), int(row[2])
            if has_kind and not bool(row[3]):
                continue
            if modid not in RADIUS_MOB_MODS:
                continue
            key, enum_name = RADIUS_MOB_MODS[modid]
            out.setdefault(poolid, {})[key] = {
                "value": value,
                "source": "mob_pool_mods",
                "detail": f"poolid {poolid} · mob mod {enum_name} ({modid})",
            }
    except Exception:
        return {}
    return out


def _mob_radius_script_values(root: Path, zone_name: str, mob_name: str):
    """Direct literal per-mob Lua overrides only.

    To stay conservative, only assignments at one indentation level inside the callback are
    accepted. Nested conditional assignments are deliberately not promoted because they may apply
    only to one spawn/id/state rather than every row sharing this mob script.
    """
    candidates = [
        root / "scripts" / "zones" / zone_name / "mobs" / f"{mob_name}.lua",
        root / "scripts" / "zones" / zone_name.replace(" ", "_") / "mobs" / f"{mob_name}.lua",
    ]
    path = next((p for p in candidates if p.is_file()), None)
    if path is None:
        return {}
    try:
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except Exception:
        return {}
    found = {}
    rx = re.compile(r"^(?: {4}|\t)mob:setMobMod\(xi\.mobMod\.(ROAM_DISTANCE|SPAWN_LEASH|SIGHT_RANGE|SOUND_RANGE),\s*(-?\d+(?:\.\d+)?)\s*\)")
    for lineno, line in enumerate(lines, 1):
        m = rx.match(line)
        if not m:
            continue
        enum_name, raw = m.groups()
        modid = {"ROAM_DISTANCE": 31, "SPAWN_LEASH": 47}.get(enum_name) or MOBMOD_IDS[enum_name]
        key, _ = RADIUS_MOB_MODS[modid]
        value = float(raw)
        if value.is_integer():
            value = int(value)
        found[key] = {
            "value": value,
            "source": "mob_script_literal",
            "detail": f"{path.relative_to(root).as_posix()}:{lineno} · {enum_name}",
        }
    return found


def zone_data(zid, instance=0, server=None):
    db = _db(server); cu = db.cursor()
    cu.execute("select name from zone_settings where zoneid=%s", (zid,))
    row = cu.fetchone()
    name = row[0] if row else str(zid)
    ents, inst_ids = [], None
    if instance:
        cu.execute("select id from instance_entities where instanceid=%s", (instance,))
        inst_ids = {r[0] for r in cu.fetchall()}
    # mob_groups has a "name" column on Topaz; this DSP checkout's mob_groups has no name column at
    # all (group identity there is poolid-only), so fall back to the spawn row's own mobname for "g".
    group_cols = _columns(cu, "mob_groups")
    group_name_col = "g.name" if "name" in group_cols else "s.mobname"
    pool_col = "g.poolid" if "poolid" in group_cols else "NULL"
    cu.execute(f"""select s.mobid,s.mobname,s.pos_x,s.pos_y,s.pos_z,{group_name_col},g.minLevel,g.maxLevel,s.pos_rot,s.groupid,{pool_col}
                  from mob_spawn_points s join mob_groups g on g.groupid=s.groupid and g.zoneid=%s
                  where ((s.mobid-16777216)>>12)&511=%s""", (zid, zid))
    mob_rows = cu.fetchall()
    pool_radii = _mob_radius_pool_values(cu, [r[10] for r in mob_rows])
    pool_detect = _mob_detect_values(cu, [r[10] for r in mob_rows])
    root = _server_root(server)
    script_cache = {}
    for i, n, x, y, z, gn, lo, hi, rot, gid, poolid in mob_rows:
        explicit = dict(pool_radii.get(int(poolid), {})) if poolid is not None else {}
        cache_key = str(n or "")
        if cache_key not in script_cache:
            script_cache[cache_key] = _mob_radius_script_values(root, name, cache_key)
        explicit.update(script_cache[cache_key])
        ent = {"k": "m", "id": i, "n": n, "x": float(x), "y": float(y), "z": float(z), "r": int(rot or 0), "g": gn, "gid": int(gid), "lv": f"{lo}-{hi}"}
        if poolid is not None:
            ent["poolid"] = int(poolid)
        if poolid is not None and int(poolid) in pool_detect:
            ent.update(pool_detect[int(poolid)])
        for radius_key in ("roam_radius", "leash_radius", "sight_range", "sound_range"):
            if radius_key in explicit:
                ent[radius_key] = explicit[radius_key]["value"]
                ent[radius_key + "_source"] = explicit[radius_key]["source"]
                ent[radius_key + "_detail"] = explicit[radius_key]["detail"]
        ents.append(ent)
    cu.execute("""select npcid,name,polutils_name,pos_x,pos_y,pos_z,status,entityFlags,pos_rot,animation,animationsub from npc_list
                  where ((npcid-16777216)>>12)&511=%s""", (zid,))
    for i, n, pn, x, y, z, st, fl, rot, an, asub in cu.fetchall():
        ents.append({"k": "d" if (n or "").strip().startswith("_") else "n", "r": int(rot or 0), "id": i, "n": pn or n, "x": float(x), "y": float(y), "z": float(z), "g": n, "lv": "",
                     "fl": int(fl or 0), "st": int(st or 0), "an": int(an or 0), "asub": int(asub or 0)})
    db.close()
    if inst_ids is not None:
        ents = [e for e in ents if e["id"] in inst_ids]
    for e in ents:
        e["zero"] = e["x"] == 0 and e["y"] == 0 and e["z"] == 0
    return {"zone": name, "zid": zid, "entities": ents, "has_nav": nav_path(name, server) is not None}


def nav_diagnostics(zid, x, y, z, server=None):
    d = zone_data(zid, server=server)
    p = nav_path(d["zone"], server)
    if not p:
        return {"error": "no navmesh for this zone"}
    diag = nav.point_diagnostics(float(x), float(y), float(z), p)
    return diag or {"error": "navmesh contains no polygons"}


def reach(zid, anchor=None, instance=0, server=None):
    """Per-entity state: ok (same component as anchor), blocked (other component), off (no polygon).
    Anchor defaults to the component holding the most entities."""
    d = zone_data(zid, instance, server)
    p = nav_path(d["zone"], server)
    if not p:
        return {"error": "no navmesh for this zone"}
    comps = [None if e["zero"] else nav.locate(e["x"], e["y"], e["z"], p) for e in d["entities"]]
    if anchor:
        ac = nav.locate(*anchor, path=p)
    else:
        cnt = {}
        for c in comps:
            if c is not None:
                cnt[c] = cnt.get(c, 0) + 1
        ac = max(cnt, key=cnt.get) if cnt else None
    st = ["zero" if e["zero"] else "off" if c is None else "ok" if c == ac else "blocked"
          for e, c in zip(d["entities"], comps)]
    return {"state": st, "comp": comps, "anchor_comp": ac}


EDIT_LOG = Path(__file__).parent / "data" / "zoneplot_edit_log.sql"


def update_position(kind, eid, x, y, z, rot, server=None):
    """Write a new position/rotation for one mob spawn row or npc_list row to the LIVE DB.
    Returns the exact SQL that ran (also appended to data/zoneplot_edit_log.sql for the .sql files)."""
    if kind == "m":
        tbl, key = "mob_spawn_points", "mobid"
    elif kind in ("n", "d"):
        tbl, key = "npc_list", "npcid"
    else:
        raise ValueError("kind must be m/n/d")
    x, y, z, rot, eid = round(float(x), 3), round(float(y), 3), round(float(z), 3), int(rot) & 0xFF, int(eid)
    if x == y == z == 0:
        raise ValueError("(0,0,0) is excluded from instance loading; use a real position")
    sql = f"UPDATE {tbl} SET pos_x={x}, pos_y={y}, pos_z={z}, pos_rot={rot} WHERE {key}={eid};"
    db = _db(server); cu = db.cursor()
    cu.execute(f"select pos_x,pos_y,pos_z,pos_rot from {tbl} where {key}=%s", (eid,))
    old = cu.fetchall()
    if len(old) != 1:
        db.close(); raise ValueError(f"{tbl}.{key}={eid} matched {len(old)} rows")
    cu.execute(f"update {tbl} set pos_x=%s,pos_y=%s,pos_z=%s,pos_rot=%s where {key}=%s", (x, y, z, rot, eid))
    db.commit(); db.close()
    EDIT_LOG.parent.mkdir(exist_ok=True)
    with EDIT_LOG.open("a", encoding="utf-8") as f:
        f.write(f"-- [{server or get_server()}] was ({old[0][0]}, {old[0][1]}, {old[0][2]}, rot {old[0][3]})\n{sql}\n")
    return {"sql": sql, "old": [float(old[0][0]), float(old[0][1]), float(old[0][2]), int(old[0][3])]}
