"""Zone Plot editing layer: every write to the live DB goes through here so it is
  1. backed up first (data/zoneplot_backups/*.json: full previous rows, restorable),
  2. journalled as annotated SQL (data/zoneplot_edit_log.sql: `-- comment` + the exact statement).
Tables touched: mob_spawn_points, npc_list, and (when cloning a mob from another zone) mob_groups."""
import json
import re
import time
from decimal import Decimal
from pathlib import Path

import zone_plot

DATA = Path(__file__).parent / "data"
BACKUPS = DATA / "zoneplot_backups"
LOG = DATA / "zoneplot_edit_log.sql"
TABLES = {  # table -> primary key columns
    "mob_spawn_points": ["mobid"],
    "npc_list": ["npcid"],
    "mob_groups": ["groupid", "zoneid"],
}
KIND_TABLE = {"m": "mob_spawn_points", "n": "npc_list", "d": "npc_list"}


# ---- value <-> json / sql -------------------------------------------------------------------
def _enc(v):
    if isinstance(v, (bytes, bytearray)):
        return {"__hex__": bytes(v).hex()}
    if isinstance(v, Decimal):
        return float(v)
    return v


def _dec(v):
    if isinstance(v, dict) and "__hex__" in v:
        return bytes.fromhex(v["__hex__"])
    return v


def lit(v):
    v = _dec(v)
    if v is None:
        return "NULL"
    if isinstance(v, (bytes, bytearray)):
        return "0x" + bytes(v).hex()
    if isinstance(v, (int, float)):
        return repr(v)
    return "'" + str(v).replace("\\", "\\\\").replace("'", "\\'") + "'"


def _cols(cu, table):
    cu.execute(f"describe {table}")
    return [r[0] for r in cu.fetchall()]


def _fetch(cu, table, keyvals):
    cols = _cols(cu, table)
    where = " and ".join(f"{k}=%s" for k in TABLES[table])
    cu.execute(f"select * from {table} where {where}", tuple(keyvals))
    r = cu.fetchall()
    return dict(zip(cols, [_enc(x) for x in r[0]])) if r else None


def _journal(comment, lines):
    LOG.parent.mkdir(exist_ok=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(f"\n-- [{time.strftime('%Y-%m-%d %H:%M:%S')}] {re.sub(chr(10), ' ', comment or '(no comment)')}\n")
        for l in lines:
            f.write(l + "\n")


# ---- backups --------------------------------------------------------------------------------
def _save_backup(label, zone, ops, kind="auto"):
    BACKUPS.mkdir(parents=True, exist_ok=True)
    bid = time.strftime("%Y%m%d-%H%M%S") + f"-{len([1 for _ in BACKUPS.glob('*.json')]) % 1000:03d}"
    b = {"id": bid, "ts": time.strftime("%Y-%m-%d %H:%M:%S"), "label": label, "zone": zone, "kind": kind, "ops": ops}
    (BACKUPS / f"{bid}.json").write_text(json.dumps(b, default=lambda o: float(o) if isinstance(o, Decimal) else str(o)))
    return bid


def _capture(cu, table, keyvals):
    return {"table": table, "key": list(keyvals), "row": _fetch(cu, table, keyvals)}


def snapshot_zone(zid, label=""):
    """Full snapshot of a zone's mob spawns, npcs and mob groups (restorable in 'exact' mode)."""
    db = zone_plot._db(); cu = db.cursor()
    lo = ((zid) << 12) + 16777216
    hi = lo + 4095
    ops = []
    for table, keycol in (("mob_spawn_points", "mobid"), ("npc_list", "npcid")):
        cu.execute(f"select {keycol} from {table} where {keycol} between %s and %s", (lo, hi))
        ops += [_capture(cu, table, [r[0]]) for r in cu.fetchall()]
    cu.execute("select groupid from mob_groups where zoneid=%s", (zid,))
    ops += [_capture(cu, "mob_groups", [r[0], zid]) for r in cu.fetchall()]
    db.close()
    return _save_backup(label or "manual zone snapshot", zid, ops, kind="zone")


def list_backups():
    out = []
    for f in sorted(BACKUPS.glob("*.json"), reverse=True) if BACKUPS.exists() else []:
        b = json.loads(f.read_text())
        out.append({"id": b["id"], "ts": b["ts"], "label": b["label"], "zone": b["zone"], "kind": b["kind"], "rows": len(b["ops"])})
    return out


def restore(bid, exact=False):
    """Put every row in the backup back (REPLACE / delete-if-it-did-not-exist). exact=True on a zone
    snapshot also deletes rows that exist now but are not in the snapshot. Backs up current state first."""
    b = json.loads((BACKUPS / f"{bid}.json").read_text())
    db = zone_plot._db(); cu = db.cursor()
    pre, lines, snap_keys = [], [], {t: set() for t in TABLES}
    for op in b["ops"]:
        t, kv = op["table"], op["key"]
        snap_keys[t].add(tuple(kv))
        pre.append(_capture(cu, t, kv))
    extra = []
    if exact and b["kind"] == "zone":
        zid = b["zone"]; lo = (zid << 12) + 16777216; hi = lo + 4095
        for table, keycol in (("mob_spawn_points", "mobid"), ("npc_list", "npcid")):
            cu.execute(f"select {keycol} from {table} where {keycol} between %s and %s", (lo, hi))
            extra += [(table, [r[0]]) for r in cu.fetchall() if (r[0],) not in snap_keys[table]]
        cu.execute("select groupid from mob_groups where zoneid=%s", (zid,))
        extra += [("mob_groups", [r[0], zid]) for r in cu.fetchall() if (r[0], zid) not in snap_keys["mob_groups"]]
        pre += [_capture(cu, t, kv) for t, kv in extra]
    pre_id = _save_backup(f"auto: before restore of {bid}", b["zone"], pre)
    for op in b["ops"]:
        t, kv, row = op["table"], op["key"], op["row"]
        where = " and ".join(f"{k}={lit(v)}" for k, v in zip(TABLES[t], kv))
        if row is None:
            cu.execute(f"delete from {t} where " + " and ".join(f"{k}=%s" for k in TABLES[t]), tuple(kv))
            lines.append(f"DELETE FROM {t} WHERE {where};")
        else:
            cols = list(row)
            cu.execute(f"replace into {t} ({','.join(cols)}) values ({','.join(['%s'] * len(cols))})", tuple(_dec(row[c]) for c in cols))
            lines.append(f"REPLACE INTO {t} ({','.join(cols)}) VALUES ({','.join(lit(row[c]) for c in cols)});")
    for t, kv in extra:
        cu.execute(f"delete from {t} where " + " and ".join(f"{k}=%s" for k in TABLES[t]), tuple(kv))
        lines.append(f"DELETE FROM {t} WHERE " + " AND ".join(f"{k}={lit(v)}" for k, v in zip(TABLES[t], kv)) + ";")
    db.commit(); db.close()
    _journal(f"RESTORE from backup {bid} ({b['label']}){' [exact]' if exact else ''}; pre-restore state saved as {pre_id}", lines)
    return {"restored": len(b["ops"]), "deleted_extra": len(extra), "pre_restore_backup": pre_id}


# ---- edits ----------------------------------------------------------------------------------
def _zone_of(i):
    return ((int(i) - 16777216) >> 12) & 511


def update_position(kind, eid, x, y, z, rot, comment=""):
    table = KIND_TABLE[kind]; key = TABLES[table][0]
    x, y, z, rot, eid = round(float(x), 3), round(float(y), 3), round(float(z), 3), int(rot) & 0xFF, int(eid)
    if x == y == z == 0:
        raise ValueError("(0,0,0) is excluded from instance loading; use a real position")
    db = zone_plot._db(); cu = db.cursor()
    op = _capture(cu, table, [eid])
    if op["row"] is None:
        db.close(); raise ValueError(f"{table}.{key}={eid} not found")
    bid = _save_backup(f"edit {table} {eid} position", _zone_of(eid), [op])
    cu.execute(f"update {table} set pos_x=%s,pos_y=%s,pos_z=%s,pos_rot=%s where {key}=%s", (x, y, z, rot, eid))
    db.commit(); db.close()
    o = op["row"]
    sql = f"UPDATE {table} SET pos_x={x}, pos_y={y}, pos_z={z}, pos_rot={rot} WHERE {key}={eid};"
    _journal(comment, [f"-- was ({o['pos_x']}, {o['pos_y']}, {o['pos_z']}, rot {o['pos_rot']})  backup {bid}", sql])
    return {"sql": sql, "backup": bid}


def _next_id(cu, zid):
    lo = (zid << 12) + 16777216
    hi = lo + 4095
    cu.execute("select max(m) from (select max(mobid) m from mob_spawn_points where mobid between %s and %s "
               "union all select max(npcid) from npc_list where npcid between %s and %s) t", (lo, hi, lo, hi))
    m = cu.fetchone()[0]
    n = (int(m) + 1) if m else lo + 1
    if n > hi:
        raise ValueError("zone id space (4096 slots) is full")
    return n


def delete_entity(kind, eid, comment=""):
    table = KIND_TABLE[kind]; key = TABLES[table][0]; eid = int(eid)
    db = zone_plot._db(); cu = db.cursor()
    op = _capture(cu, table, [eid])
    if op["row"] is None:
        db.close(); raise ValueError(f"{table}.{key}={eid} not found")
    cu.execute("select count(*) from instance_entities where id=%s", (eid,))
    in_inst = cu.fetchone()[0]
    bid = _save_backup(f"delete {table} {eid} ({op['row'].get('mobname') or op['row'].get('name')})", _zone_of(eid), [op])
    cu.execute(f"delete from {table} where {key}=%s", (eid,))
    sqls = [f"DELETE FROM {table} WHERE {key}={eid};"]
    # NOTE: we deliberately do NOT auto-delete a now-zero-spawn mob_groups row here. A group having zero
    # mob_spawn_points rows is a normal, common state (e.g. Nyzul Isle groups referenced dynamically by the
    # instance generator, not via static spawn rows) -- auto-cleaning it destroyed a real live group once.
    # Just surface it so a human can judge whether it's really dead.
    group_note = ""
    if table == "mob_spawn_points":
        gid, gzone = op["row"].get("groupid"), _zone_of(eid)
        if gid is not None:
            cu.execute("select count(*) from mob_spawn_points where groupid=%s", (gid,))
            if cu.fetchone()[0] == 0:
                group_note = (f" (mob_groups {gid}/{gzone} now has zero mob_spawn_points rows -- "
                               f"NOT auto-deleted; remove it yourself only if you're sure it's unused)")
    db.commit(); db.close()
    _journal(comment, [f"-- backup {bid}"] + sqls)
    return {"sql": "\n".join(sqls), "backup": bid,
            "warning": (f"still listed in instance_entities ({in_inst} instance rows)" if in_inst else "") + group_note}


def catalogue(kind, q, limit=60):
    """Search everything that can be cloned into a zone. kind m: mob_groups (any zone); n: npc_list (any zone)."""
    db = zone_plot._db(); cu = db.cursor()
    like = f"%{q}%"
    if kind == "m":
        # mob_groups has a "name" column on Topaz; this DSP checkout's mob_groups has none at all
        # (group identity there is poolid-only) -- fall back to the spawn rows' own mobname.
        if "name" in zone_plot._columns(cu, "mob_groups"):
            cu.execute("""select g.groupid,g.zoneid,z.name,g.name,g.minLevel,g.maxLevel,g.poolid from mob_groups g
                          left join zone_settings z on z.zoneid=g.zoneid where g.name like %s order by g.name,g.zoneid limit %s""", (like, limit))
        else:
            cu.execute("""select g.groupid,g.zoneid,z.name,min(s.mobname),g.minLevel,g.maxLevel,g.poolid
                          from mob_groups g join mob_spawn_points s on s.groupid=g.groupid
                          left join zone_settings z on z.zoneid=g.zoneid
                          where s.mobname like %s group by g.groupid,g.zoneid,z.name,g.minLevel,g.maxLevel,g.poolid
                          order by min(s.mobname) limit %s""", (like, limit))
        out = [{"groupid": a, "zone": b, "zname": c, "name": d, "lv": f"{e}-{f}", "poolid": g} for a, b, c, d, e, f, g in cu.fetchall()]
    else:
        cu.execute("""select n.npcid,z.name,n.name,n.polutils_name from npc_list n
                      left join zone_settings z on z.zoneid=((n.npcid-16777216)>>12)&511
                      where n.name like %s or n.polutils_name like %s order by n.name limit %s""", (like, like, limit))
        out = [{"npcid": a, "zname": b, "name": c, "pname": d} for a, b, c, d in cu.fetchall()]
    db.close()
    return out


def add_entity(kind, zid, src, x, y, z, rot, name="", comment=""):
    """Add a mob spawn (src = {groupid, zone}) or npc (src = {npcid}) at (x,y,z) in zone `zid`.
    A mob group from another zone is cloned into this zone as a new mob_groups row."""
    zid = int(zid)
    x, y, z, rot = round(float(x), 3), round(float(y), 3), round(float(z), 3), int(rot) & 0xFF
    if x == y == z == 0:
        raise ValueError("(0,0,0) is excluded from instance loading; use a real position")
    db = zone_plot._db(); cu = db.cursor()
    nid = _next_id(cu, zid)
    lines, ops = [], []
    if kind == "m":
        g = _fetch(cu, "mob_groups", [int(src["groupid"]), int(src["zone"])])
        if not g:
            db.close(); raise ValueError("source mob group not found")
        gid = g["groupid"]
        if "name" not in g:  # DSP's mob_groups has no name column -- borrow one from an existing spawn in the group
            cu.execute("select mobname from mob_spawn_points where groupid=%s limit 1", (gid,))
            r = cu.fetchone()
            if r and r[0]:
                g["name"] = r[0]
        if int(src["zone"]) != zid:  # clone the group into this zone under a fresh groupid
            cu.execute("select max(groupid) from mob_groups where zoneid=%s", (zid,))
            gid = int(cu.fetchone()[0] or 0) + 1
            ng = dict(g, groupid=gid, zoneid=zid)
            cols = list(ng)
            ops.append({"table": "mob_groups", "key": [gid, zid], "row": None})
            cu.execute(f"insert into mob_groups ({','.join(cols)}) values ({','.join(['%s'] * len(cols))})", tuple(_dec(ng[c]) for c in cols))
            lines.append(f"INSERT INTO mob_groups ({','.join(cols)}) VALUES ({','.join(lit(ng[c]) for c in cols)});")
        gname = name or g.get("name") or "mob"
        row = {"mobid": nid, "mobname": gname[:24], "polutils_name": gname[:50], "groupid": gid,
               "pos_x": x, "pos_y": y, "pos_z": z, "pos_rot": rot}
        table = "mob_spawn_points"
    else:
        s = _fetch(cu, "npc_list", [int(src["npcid"])])
        if not s:
            db.close(); raise ValueError("source npc not found")
        row = dict(s, npcid=nid, pos_x=x, pos_y=y, pos_z=z, pos_rot=rot)
        if name:
            row["name"] = name[:24]; row["polutils_name"] = name[:50]
        table = "npc_list"
    cols = list(row)
    ops.append({"table": table, "key": [nid], "row": None})
    bid = _save_backup(f"add {table} {nid} ({row.get('mobname') or row.get('name')})", zid, ops)
    cu.execute(f"insert into {table} ({','.join(cols)}) values ({','.join(['%s'] * len(cols))})", tuple(_dec(row[c]) for c in cols))
    db.commit(); db.close()
    lines.append(f"INSERT INTO {table} ({','.join(cols)}) VALUES ({','.join(lit(row[c]) for c in cols)});")
    _journal(comment, [f"-- backup {bid}"] + lines)
    return {"id": nid, "backup": bid, "sql": "\n".join(lines)}
