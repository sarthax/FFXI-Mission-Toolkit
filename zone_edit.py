"""Zone Plot editing layer: every write to the live DB goes through here so it is
  1. backed up first (data/zoneplot_backups/*.json: full previous rows, restorable),
  2. journalled as annotated SQL (data/zoneplot_edit_log.sql: `-- comment` + the exact statement).
Tables touched: mob_spawn_points, npc_list, and (when cloning a mob from another zone) mob_groups."""
import json
import re
import time
from decimal import Decimal
from pathlib import Path

import settings
import zone_plot

DATA = Path(__file__).parent / "data"
BACKUPS = DATA / "zoneplot_backups"
LOG = DATA / "zoneplot_edit_log.sql"
                                  # Checked-in source files a `dbtool.py`-style reimport reads from --
                                  # completely separate from the live DB writes above, and NOT kept
                                  # in sync automatically (a reimport after a live-only edit would
                                  # silently revert it). sync_sql_file() is the opt-in bridge.
                                  # MUST resolve per the *same* server the live-DB row came from
                                  # (zone_plot.get_server(), same as zone_plot._db()'s default) --
                                  # a fixed Topaz-only path here previously wrote DSP-sourced rows
                                  # into C:\topaz\sql\*.sql (caught 2026-09-22 by the user).


def _sql_dir(server=None) -> Path:
    server = server or zone_plot.get_server()
    root = settings.get_dsp_root() if server == "dsp" else settings.get_topaz_root()
    if root is None:
        raise ValueError(f"{server} server path isn't configured yet -- set it on the Settings page first")
    return root / "sql"
TABLES = {  # table -> primary key columns
    "mob_spawn_points": ["mobid"],
    "npc_list": ["npcid"],
    "mob_groups": ["groupid", "zoneid"],
    "mob_droplist": ["dropid", "dropType", "groupId", "itemId"],
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
            if t == "mob_droplist":
                # mob_droplist has NO primary/unique key at all (confirmed via `show index`) -- REPLACE INTO
                # can't detect a conflict here and silently behaves as a bare INSERT, creating duplicates.
                # Explicit delete-then-insert instead.
                cu.execute("delete from mob_droplist where dropid=%s and dropType=%s and groupId=%s and itemId=%s limit 1", tuple(kv))
                lines.append("DELETE FROM mob_droplist WHERE " + " AND ".join(f"{k}={lit(v)}" for k, v in zip(TABLES[t], kv)) + " LIMIT 1;")
            cu.execute(f"insert into {t} ({','.join(cols)}) values ({','.join(['%s'] * len(cols))})" if t == "mob_droplist"
                       else f"replace into {t} ({','.join(cols)}) values ({','.join(['%s'] * len(cols))})", tuple(_dec(row[c]) for c in cols))
            lines.append((f"INSERT INTO {t} " if t == "mob_droplist" else f"REPLACE INTO {t} ") +
                          f"({','.join(cols)}) VALUES ({','.join(lit(row[c]) for c in cols)});")
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


def update_animation(kind, eid, animation, animationsub, comment=""):
    """npc_list only (doors/props/npcs) -- mob_spawn_points has no animation columns."""
    if kind not in ("n", "d"):
        raise ValueError("animation is only editable on npc_list rows (kind n/d)")
    table = KIND_TABLE[kind]; key = TABLES[table][0]
    animation, animationsub, eid = int(animation) & 0xFF, int(animationsub) & 0xFF, int(eid)
    db = zone_plot._db(); cu = db.cursor()
    op = _capture(cu, table, [eid])
    if op["row"] is None:
        db.close(); raise ValueError(f"{table}.{key}={eid} not found")
    bid = _save_backup(f"edit {table} {eid} animation", _zone_of(eid), [op])
    cu.execute(f"update {table} set animation=%s,animationsub=%s where {key}=%s", (animation, animationsub, eid))
    db.commit(); db.close()
    o = op["row"]
    sql = f"UPDATE {table} SET animation={animation}, animationsub={animationsub} WHERE {key}={eid};"
    _journal(comment, [f"-- was (animation {o.get('animation')}, animationsub {o.get('animationsub')})  backup {bid}", sql])
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


# ---- drops ------------------------------------------------------------------------------------
# mob_groups.dropid is the real FK into mob_droplist (NOT mob_pools.poolid -- confirmed against
# Topaz's own C++, see entity_profile.py's build_profile() drops section). dropid=0/NULL is a
# real, valid "no drop table configured" state. A dropid is shared by every mob_spawn_points row
# in the same mob_groups group, so changing it (or editing a row under it) affects every spawn of
# that group, not just the one mob clicked in the plot -- the UI surfaces this explicitly.
def get_drops(mobid):
    """Trace mob_spawn_points -> mob_groups.dropid -> mob_droplist, joined with item_basic names."""
    mobid = int(mobid)
    db = zone_plot._db(); cu = db.cursor()
    sp = _fetch(cu, "mob_spawn_points", [mobid])
    if sp is None:
        db.close(); raise ValueError(f"mob_spawn_points.mobid={mobid} not found")
    gid, zid = sp.get("groupid"), _zone_of(mobid)
    group = _fetch(cu, "mob_groups", [gid, zid]) if gid is not None else None
    dropid = group.get("dropid") if group else None
    rows = []
    if dropid:
        # (dropId, groupId, itemId) is NOT unique on its own -- dropType is part of the real key
        # (confirmed live: dropid 2018 has two itemId=936 rows differing only by dropType). Any
        # write path must key on all four columns or it can silently clobber/delete the wrong row.
        cu.execute("""select d.dropid,d.dropType,d.groupId,d.groupRate,d.itemId,d.itemRate,i.name
                      from mob_droplist d left join item_basic i on i.itemid=d.itemId
                      where d.dropid=%s order by d.groupId,d.itemRate desc""", (dropid,))
        rows = [{"dropid": a, "drop_type": b, "group_id": c, "group_rate": d, "item_id": e, "item_rate": f,
                  "item_name": g, "effective_pct": round(d / 1000 * f / 1000 * 100, 2)}
                for a, b, c, d, e, f, g in cu.fetchall()]
    cu.execute("select count(*) from mob_spawn_points where groupid=%s", (gid,))
    n_sharing = cu.fetchone()[0] if gid is not None else 0
    db.close()
    return {"mobid": mobid, "mobname": sp.get("mobname"), "groupid": gid, "dropid": dropid,
            "n_sharing_group": n_sharing, "drops": rows}


def set_group_dropid(mobid, dropid, comment=""):
    """Point mobid's mob_groups row at a different (or brand-new, dropid='new') mob_droplist id.
    Affects every mob_spawn_points row sharing that groupid, not just mobid."""
    mobid = int(mobid)
    db = zone_plot._db(); cu = db.cursor()
    sp = _fetch(cu, "mob_spawn_points", [mobid])
    if sp is None:
        db.close(); raise ValueError(f"mob_spawn_points.mobid={mobid} not found")
    gid, zid = sp.get("groupid"), _zone_of(mobid)
    if gid is None:
        db.close(); raise ValueError("this mob has no groupid")
    op = _capture(cu, "mob_groups", [gid, zid])
    if op["row"] is None:
        db.close(); raise ValueError(f"mob_groups {gid}/{zid} not found")
    if dropid == "new":
        cu.execute("select coalesce(max(dropid),0)+1 from mob_droplist")
        new_dropid = int(cu.fetchone()[0])
    else:
        new_dropid = int(dropid)
    bid = _save_backup(f"set dropid on mob_groups {gid}/{zid}", zid, [op])
    cu.execute("update mob_groups set dropid=%s where groupid=%s and zoneid=%s", (new_dropid, gid, zid))
    db.commit(); db.close()
    sql = f"UPDATE mob_groups SET dropid={new_dropid} WHERE groupid={gid} AND zoneid={zid};"
    _journal(comment, [f"-- was dropid {op['row'].get('dropid')}  backup {bid}", sql])
    return {"sql": sql, "backup": bid, "dropid": new_dropid}


def save_drop_row(dropid, drop_type, group_id, item_id, group_rate, item_rate,
                   orig_drop_type=None, orig_group_id=None, orig_item_id=None, comment=""):
    """Insert a new mob_droplist row, or update one identified by (dropid, orig_drop_type,
    orig_group_id, orig_item_id) when those are given (lets drop_type/group_id/item_id themselves
    be edited on an existing row). The real primary key is all four columns -- (dropid, groupId,
    itemId) alone is NOT unique (confirmed live: some dropids carry two rows for the same item
    differing only by dropType)."""
    dropid, drop_type, group_id, item_id = int(dropid), int(drop_type), int(group_id), int(item_id)
    group_rate, item_rate = int(group_rate), int(item_rate)
    if not (0 <= group_rate <= 1000) or not (0 <= item_rate <= 1000):
        raise ValueError("group_rate/item_rate are thousandths (0-1000)")
    db = zone_plot._db(); cu = db.cursor()
    cu.execute("select 1 from item_basic where itemid=%s", (item_id,))
    if not cu.fetchone():
        db.close(); raise ValueError(f"item_basic.itemid={item_id} not found -- refusing to write a fabricated item id")
    is_edit = orig_drop_type is not None and orig_group_id is not None and orig_item_id is not None
    orig_key = [dropid, int(orig_drop_type), int(orig_group_id), int(orig_item_id)] if is_edit else None
    key = orig_key or [dropid, drop_type, group_id, item_id]
    op = _capture(cu, "mob_droplist", key)
    if is_edit and op["row"] is None:
        db.close(); raise ValueError("original drop row not found (it changed underneath you -- reload)")
    bid = _save_backup(f"{'edit' if is_edit else 'add'} mob_droplist dropid={dropid}", None, [op], kind="mob_droplist")
    # mob_droplist has NO primary/unique key (confirmed via `show index from mob_droplist`), so REPLACE INTO
    # cannot detect a conflict and silently behaves as a bare INSERT -- always explicitly delete the original
    # row (by its ORIGINAL key, LIMIT 1 so a duplicate sibling row is untouched) before inserting the new one.
    del_sql = ""
    if is_edit:
        cu.execute("delete from mob_droplist where dropid=%s and dropType=%s and groupId=%s and itemId=%s limit 1", tuple(orig_key))
        del_sql = (f"DELETE FROM mob_droplist WHERE dropid={orig_key[0]} AND dropType={orig_key[1]} "
                   f"AND groupId={orig_key[2]} AND itemId={orig_key[3]} LIMIT 1;\n")
    cols = ["dropid", "dropType", "groupId", "groupRate", "itemId", "itemRate"]
    vals = [dropid, drop_type, group_id, group_rate, item_id, item_rate]
    cu.execute(f"insert into mob_droplist ({','.join(cols)}) values ({','.join(['%s'] * len(cols))})", vals)
    db.commit(); db.close()
    sql = del_sql + f"INSERT INTO mob_droplist ({','.join(cols)}) VALUES ({','.join(lit(v) for v in vals)});"
    _journal(comment, [f"-- backup {bid}", sql])
    return {"sql": sql, "backup": bid}


def delete_drop_row(dropid, drop_type, group_id, item_id, comment=""):
    dropid, drop_type, group_id, item_id = int(dropid), int(drop_type), int(group_id), int(item_id)
    db = zone_plot._db(); cu = db.cursor()
    op = _capture(cu, "mob_droplist", [dropid, drop_type, group_id, item_id])
    if op["row"] is None:
        db.close(); raise ValueError("drop row not found")
    bid = _save_backup(f"delete mob_droplist dropid={dropid} item={item_id}", None, [op], kind="mob_droplist")
    cu.execute("delete from mob_droplist where dropid=%s and dropType=%s and groupId=%s and itemId=%s limit 1",
                (dropid, drop_type, group_id, item_id))
    db.commit(); db.close()
    sql = f"DELETE FROM mob_droplist WHERE dropid={dropid} AND dropType={drop_type} AND groupId={group_id} AND itemId={item_id} LIMIT 1;"
    _journal(comment, [f"-- backup {bid}", sql])
    return {"sql": sql, "backup": bid}


def item_catalogue(q, limit=40):
    if not q or len(q) < 2:
        return []
    db = zone_plot._db(); cu = db.cursor()
    cu.execute("select itemid, name from item_basic where name like %s order by name limit %s", (f"%{q}%", limit))
    out = [{"itemid": a, "name": b} for a, b in cu.fetchall()]
    db.close()
    return out


# ---- sync to sql/*.sql source files ----------------------------------------------------------
# Everything above writes only to the live DB. `dbtool.py` (per CLAUDE.md) reimports sql/*.sql over
# the live DB, so any live-only edit here is silently reverted the next time someone runs it. This
# is an explicit, opt-in bridge -- a separate button in the UI, never called automatically by the
# edit/add/delete/drop functions above -- that mirrors ONE row's current live-DB state into the
# matching checked-in sql/<table>.sql file (replace its INSERT line, append one, or remove it).
def _split_row_values(s):
    """Split the inside of an `INSERT ... VALUES (...)` tuple on top-level commas, respecting
    quoted strings (with backslash escapes) so commas/parens inside a string don't split it."""
    tokens, cur, in_str, i, n = [], "", False, 0, len(s)
    while i < n:
        c = s[i]
        if in_str:
            if c == "\\" and i + 1 < n:
                cur += s[i:i + 2]; i += 2; continue
            if c == "'":
                cur += c; in_str = False; i += 1; continue
            cur += c; i += 1; continue
        if c == "'":
            in_str = True; cur += c; i += 1; continue
        if c == ",":
            tokens.append(cur); cur = ""; i += 1; continue
        cur += c; i += 1
    tokens.append(cur)
    return [t.strip() for t in tokens]


_INSERT_RE = {}


def _insert_re(table):
    if table not in _INSERT_RE:
        _INSERT_RE[table] = re.compile(r"^INSERT INTO `%s` VALUES \((.*)\);\s*(--.*)?$" % re.escape(table))
    return _INSERT_RE[table]


def sql_file_path(table, server=None):
    return _sql_dir(server) / f"{table}.sql"


def sync_sql_file(table, keyvals, server=None):
    """Mirror table's current live-DB row for `keyvals` (the TABLES[table] key) into sql/<table>.sql:
    replace its INSERT line if one matches that key, append a new INSERT line if the row is new,
    or remove the line if the row no longer exists live (was deleted). keyvals must all be ints --
    every TABLES[] key column on these 4 tables is an int, so exact string comparison is safe.
    `server` pins both the live-DB row lookup AND which server's sql/ tree gets written -- defaults
    to Zone Plot's current dropdown selection (zone_plot.get_server()) so a sync always writes back
    to the same server the row was read from."""
    if table not in TABLES:
        raise ValueError(f"no sync support for table {table}")
    server = server or zone_plot.get_server()
    path = sql_file_path(table, server)
    if not path.exists():
        raise ValueError(f"source file not found: {path}")
    keyvals = [int(v) for v in keyvals]
    db = zone_plot._db(server); cu = db.cursor()
    cols = _cols(cu, table)
    row = _fetch(cu, table, keyvals)
    db.close()
    key_idx = [cols.index(k) for k in TABLES[table]]
    pat = _insert_re(table)
    text = path.read_text(encoding="utf-8", errors="replace")
    had_crlf = "\r\n" in text
    lines = text.replace("\r\n", "\n").split("\n")
    match_i = last_insert_i = None
    for i, line in enumerate(lines):
        m = pat.match(line)
        if not m:
            continue
        last_insert_i = i
        vals = _split_row_values(m.group(1))
        try:
            if all(vals[idx].strip("'") == str(k) for idx, k in zip(key_idx, keyvals)):
                match_i = i
                break
        except IndexError:
            continue
    if row is None:
        if match_i is None:
            action, old_line = "already absent from file", None
        else:
            old_line = lines[match_i]
            del lines[match_i]
            action = "deleted"
    else:
        new_line = f"INSERT INTO `{table}` VALUES ({','.join(lit(row[c]) for c in cols)});"
        if match_i is not None:
            old_line = lines[match_i]
            lines[match_i] = new_line
            action = "replaced"
        elif last_insert_i is not None:
            old_line = None
            lines.insert(last_insert_i + 1, new_line)
            action = "inserted"
        else:
            raise ValueError(f"no existing INSERT INTO `{table}` found in {path.name} to anchor a new row next to")
    out = "\n".join(lines)
    path.write_text(out.replace("\n", "\r\n") if had_crlf else out, encoding="utf-8")
    return {"file": str(path), "table": table, "key": keyvals, "action": action}


def sync_entity_sql(kind, eid, server=None):
    table = KIND_TABLE[kind]
    return sync_sql_file(table, [int(eid)], server)


def sync_group_dropid_sql(mobid, server=None):
    server = server or zone_plot.get_server()
    db = zone_plot._db(server); cu = db.cursor()
    sp = _fetch(cu, "mob_spawn_points", [int(mobid)])
    db.close()
    if sp is None:
        raise ValueError(f"mob_spawn_points.mobid={mobid} not found")
    gid = sp.get("groupid")
    if gid is None:
        raise ValueError("this mob has no groupid")
    return sync_sql_file("mob_groups", [gid, _zone_of(mobid)], server)


def sync_drop_row_sql(dropid, drop_type, group_id, item_id, orig_drop_type=None, orig_group_id=None, orig_item_id=None, server=None):
    """Sync a mob_droplist row. If orig_* differ from the new key (the row was edited in place with
    its key columns changed), also removes the stale line at the OLD key first."""
    server = server or zone_plot.get_server()
    results = []
    if orig_drop_type is not None and orig_group_id is not None and orig_item_id is not None:
        orig_key = [dropid, orig_drop_type, orig_group_id, orig_item_id]
        new_key = [dropid, drop_type, group_id, item_id]
        if [int(v) for v in orig_key] != [int(v) for v in new_key]:
            results.append(sync_sql_file("mob_droplist", orig_key, server))
    results.append(sync_sql_file("mob_droplist", [dropid, drop_type, group_id, item_id], server))
    return {"results": results}
