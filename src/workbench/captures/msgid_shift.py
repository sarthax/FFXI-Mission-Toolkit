"""Measure the server-message-id -> client-DAT-dialog-index shift per (capture, zone).

The shift is not constant (varies by zone/client generation), so it is never assumed: it is
measured once by matching 0x036 packets against the client-displayed chat (capture_caplog_chat)
in the same second, then cached in capture_msgid_shift with its evidence. No cached row (or low
confidence) => callers show the raw id and flag it unverified.
"""
import collections
import re
import struct

RANGE = range(-60, 61)
MIN_HITS = 3


def ensure_table(con):
    con.execute("""CREATE TABLE IF NOT EXISTS capture_msgid_shift (
        capture_id INTEGER, zone_db TEXT, zoneid INTEGER, shift INTEGER, hits INTEGER,
        total INTEGER, runner_up_hits INTEGER, confident INTEGER,
        PRIMARY KEY (capture_id, zone_db))""")


def _norm(s):
    return re.sub(r"[\r\n\x07\s]+", " ", re.sub(r"\u227a.*?\u227b", " ", s or "")).strip()[:25]


def _zmap(con, capture_id):
    """(entity_id, msgid) -> zone_db. capture_events for older ingests; capture_eventview
    (0x036 rows, mes_num) for newer-format EventView captures that never filled capture_events."""
    zm = {(r[0], r[1]): r[2] for r in con.execute(
        "SELECT entity_id, mes_num, zone_db FROM capture_eventview WHERE capture_id=? "
        "AND opcode='0x036' AND mes_num IS NOT NULL AND entity_id IS NOT NULL", (capture_id,))}
    zm.update({(r[0], r[1]): r[2] for r in con.execute(
        "SELECT entity_id, message_id, zone_db FROM capture_events WHERE capture_id=? "
        "AND message_id IS NOT NULL AND opcode_name LIKE '%Chat%'", (capture_id,))})
    return {k: v for k, v in zm.items() if v and v != "__UNKNOWN__"}   # sentinel zone == unknown, never a real zone


def _entmap(con, capture_id):
    """entity_id -> zone_db from capture_npc_entries, only where the entity sits in exactly one
    zone. Fallback for captures with no EventView (no (entity, msgid) zone rows)."""
    zs = {}
    for eid, z in con.execute("SELECT DISTINCT entity_id, zone_db FROM capture_npc_entries WHERE capture_id=? AND entity_id IS NOT NULL", (capture_id,)):
        zs.setdefault(eid, set()).add(z)
    return {e: next(iter(v)) for e, v in zs.items() if len(v) == 1}


def _decode_zone(con, uid, _cache={}):
    """Last-resort fallback: NPC entity id = 0x01000000 | zoneid<<12 | targid. Only for real NPC ids
    (high byte 1) whose decoded zone is a known zone. Instance zones (Assault etc.) use pseudo zone
    ids in the id, but those always resolve through the tables first."""
    if (uid >> 24) != 1:
        return None
    zid = (uid >> 12) & 0xFFF
    key = (id(con), zid)
    if key not in _cache:
        r = con.execute("SELECT name FROM zones WHERE zoneid=?", (zid,)).fetchone()
        _cache[key] = r[0] if r else None
    return _cache[key]


def build_pseudo_map(con, min_n=20, min_share=0.95):
    """Measure instance pseudo-zone ids (zone bits of the entity id) -> real zone_db from packets that
    already resolve via the tables. Only unambiguous ids are usable (share>=min_share, n>=min_n);
    ids shared by several zones (e.g. 109 = all Remnants zones) stay unresolved."""
    con.execute("""CREATE TABLE IF NOT EXISTS instance_pseudo_zone (
        pseudo INTEGER PRIMARY KEY, zone_db TEXT, n INTEGER, total INTEGER, usable INTEGER)""")
    cnt = collections.defaultdict(collections.Counter)
    ids = [r[0] for r in con.execute("SELECT DISTINCT capture_id FROM capture_raw_packets WHERE UPPER(opcode)='0X036'")]
    for cid in ids:
        zm, em = _zmap(con, cid), _entmap(con, cid)
        for (hx,) in con.execute("SELECT raw_hex FROM capture_raw_packets WHERE capture_id=? AND UPPER(opcode)='0X036'", (cid,)):
            b = bytes.fromhex(hx.replace(" ", ""))
            if len(b) < 12:
                continue
            uid = struct.unpack_from("<I", b, 4)[0]
            m = struct.unpack_from("<H", b, 10)[0] & 0x7FFF
            z = zm.get((uid, m)) or em.get(uid)
            if z:
                cnt[(uid >> 12) & 0xFFF][z] += 1
    con.execute("DELETE FROM instance_pseudo_zone")
    for ps, c in cnt.items():
        (z, n), tot = c.most_common(1)[0], sum(c.values())
        con.execute("INSERT INTO instance_pseudo_zone VALUES (?,?,?,?,?)",
                    (ps, z, n, tot, int(n >= min_n and n >= min_share * tot)))
    con.commit()


def _pseudo_zone(con, uid):
    try:
        r = con.execute("SELECT zone_db FROM instance_pseudo_zone WHERE pseudo=? AND usable=1", ((uid >> 12) & 0xFFF,)).fetchone()
    except Exception:
        return None
    return r[0] if r else None


def _src(con, capture_id):
    r = con.execute("SELECT source_path FROM captures WHERE capture_id=?", (capture_id,)).fetchone()
    return r[0] if r else None


def _pending(con, capture_id):
    """Quarantine check shared by every derived pipeline: any pending blocking exception for this capture."""
    from workbench.captures import review_queue as rq
    return rq.is_quarantined(con, capture_id)


def is_quarantined(con, capture_id):
    return bool(_pending(con, capture_id))


def _purge(con, capture_id):
    ensure_table(con)
    ensure_master_tables(con)
    con.execute("DELETE FROM capture_msgid_shift WHERE capture_id=?", (capture_id,))
    con.execute("DELETE FROM msgid_shift_obs WHERE capture_id=?", (capture_id,))
    con.commit()


def _approved(con, capture_id):
    """{pseudo-zone id: zone_db} the reviewer approved for this capture."""
    from workbench.captures import review_queue as rq
    return {int(r["key"]): r["resolution"] for r in rq.items(con, "resolved", "zone", capture_id) if r["resolution"]}


def _resolve(con, zmap, emap, appr, uid, m):
    return (zmap.get((uid, m)) or emap.get(uid) or _decode_zone(con, uid) or _pseudo_zone(con, uid)
            or appr.get((uid >> 12) & 0xFFF))


def _name_hint(con, capture_id):
    """Zone names mentioned in the capture's label/path. A HINT for the reviewer only -- many captures cover several zones."""
    r = con.execute("SELECT capture_label, source_path FROM captures WHERE capture_id=?", (capture_id,)).fetchone()
    flat = lambda t: re.sub(r"[^a-z0-9]+", "", (t or "").lower())
    h = flat(" ".join(x or "" for x in r)) if r else ""
    out = []
    for (n,) in con.execute("SELECT name FROM zones"):
        k = flat(n)
        if len(k) >= 5 and k in h and n not in out:
            out.append(n)
    return ",".join(out)


def review_candidates(con, capture_id):
    """{pseudo-zone id (str): detail} for 0x036 packets that no automatic fallback resolves (review_queue 'zone' detector)."""
    zmap, emap = _zmap(con, capture_id), _entmap(con, capture_id)
    left = collections.Counter()
    for (hx,) in con.execute("SELECT raw_hex FROM capture_raw_packets WHERE capture_id=? AND UPPER(opcode)='0X036'", (capture_id,)):
        b = bytes.fromhex(hx.replace(" ", ""))
        if len(b) < 12:
            continue
        uid = struct.unpack_from("<I", b, 4)[0]
        m = struct.unpack_from("<H", b, 10)[0] & 0x7FFF
        if not _resolve(con, zmap, emap, {}, uid, m):
            left[(uid >> 12) & 0xFFF] += 1
    zones, hint = sorted(set(emap.values())), _name_hint(con, capture_id)
    return {str(ps): {"packets": n, "capture_zones": zones, "name_hint": hint.split(",") if hint else [],
                      "reason": "%d 0x036 packet(s) with pseudo-zone id %d could not be resolved to a zone" % (n, ps)}
            for ps, n in left.items()}


def _chat_near(chat, ts, window=2):
    """Chat lines within +-window seconds of a packet timestamp (HH:MM:SS keys)."""
    try:
        h, m, s = (int(x) for x in (ts or "")[11:19].split(":"))
    except ValueError:
        return []   # packet has no usable timestamp
    base = h * 3600 + m * 60 + s
    out = []
    for d in range(-window, window + 1):
        t = (base + d) % 86400
        out += chat.get("%02d:%02d:%02d" % (t // 3600, t % 3600 // 60, t % 60), [])
    return out


def compute(con, capture_id, zoneid_for_zone_db):
    ensure_table(con)
    zmap = _zmap(con, capture_id)
    emap = _entmap(con, capture_id)
    appr = _approved(con, capture_id)
    if _pending(con, capture_id):
        _purge(con, capture_id)
        return []
    chat = collections.defaultdict(list)
    for ts, t in con.execute("SELECT ts,text FROM capture_caplog_chat WHERE capture_id=?", (capture_id,)):
        chat[ts].append(t or "")
    per = collections.defaultdict(list)
    for ts, hx in con.execute("SELECT ts, raw_hex FROM capture_raw_packets WHERE capture_id=? AND UPPER(opcode)='0X036'", (capture_id,)):
        b = bytes.fromhex(hx.replace(" ", ""))
        if len(b) < 12:
            continue
        uid = struct.unpack_from("<I", b, 4)[0]
        m = struct.unpack_from("<H", b, 10)[0] & 0x7FFF
        zone = _resolve(con, zmap, emap, appr, uid, m)
        if zone:
            per[zone].append((m, " | ".join(_chat_near(chat, ts))))
    out = []
    for zone, pk in per.items():
        zid = zoneid_for_zone_db(con, zone)
        if zid is None:
            continue
        d = dict(con.execute("SELECT idx,text FROM dialog_text WHERE zoneid=?", (zid,)))
        hits = collections.Counter()
        for m, lines in pk:
            if not lines:
                continue
            for off in RANGE:
                t = _norm(d.get(m - off))
                if len(t) >= 8 and t in lines:
                    hits[off] += 1
        top = hits.most_common(2)
        best, bh = top[0] if top else (0, 0)
        ru = top[1][1] if len(top) > 1 else 0
        conf = int(bh >= MIN_HITS and bh >= 2 * ru)
        con.execute("INSERT OR REPLACE INTO capture_msgid_shift VALUES (?,?,?,?,?,?,?,?)",
                    (capture_id, zone, zid, best if conf else None, bh, len(pk), ru, conf))
        out.append((zone, zid, best, bh, len(pk), ru, conf))
    con.commit()
    return out


def lookup(con, capture_id, zone_db):
    """-> (shift or None, info dict or None). None shift == unverified, use raw id."""
    ensure_table(con)
    r = con.execute("SELECT shift,hits,total,runner_up_hits,confident FROM capture_msgid_shift "
                    "WHERE capture_id=? AND zone_db=?", (capture_id, zone_db)).fetchone()
    if not r:
        return None, None
    return (r[0] if r[4] else None), dict(shift=r[0], hits=r[1], total=r[2], runner_up=r[3], confident=bool(r[4]))


# ---------------------------------------------------------------------------------------------
# Piecewise master list. The game developers inserted blocks mid-table more than once, so the
# shift can change inside one zone's id space. Evidence is stored per observation (one packet id
# matched to one client DAT index via CapLog) and merged into id ranges across ALL captures.
# ---------------------------------------------------------------------------------------------
def ensure_master_tables(con):
    con.execute("""CREATE TABLE IF NOT EXISTS msgid_shift_obs (
        capture_id INTEGER, zoneid INTEGER, msgid INTEGER, shift INTEGER, n INTEGER,
        PRIMARY KEY (capture_id, zoneid, msgid, shift))""")
    con.execute("""CREATE TABLE IF NOT EXISTS msgid_shift_master (
        zoneid INTEGER, id_lo INTEGER, id_hi INTEGER, shift INTEGER, obs INTEGER, captures INTEGER,
        gap_before INTEGER, conflict INTEGER, PRIMARY KEY (zoneid, id_lo, shift))""")


def observe(con, capture_id, zoneid_for_zone_db):
    """Store unambiguous (msgid -> shift) observations for one capture. Cheap; run at/after ingest."""
    ensure_master_tables(con)
    zmap = _zmap(con, capture_id)
    emap = _entmap(con, capture_id)
    appr = _approved(con, capture_id)
    if _pending(con, capture_id):
        _purge(con, capture_id)
        return 0
    chat = collections.defaultdict(list)
    for ts, t in con.execute("SELECT ts,text FROM capture_caplog_chat WHERE capture_id=?", (capture_id,)):
        chat[ts].append(t or "")
    dcache, found = {}, collections.Counter()
    for ts, hx in con.execute("SELECT ts, raw_hex FROM capture_raw_packets WHERE capture_id=? AND UPPER(opcode)='0X036'", (capture_id,)):
        b = bytes.fromhex(hx.replace(" ", ""))
        if len(b) < 12:
            continue
        m = struct.unpack_from("<H", b, 10)[0] & 0x7FFF
        uid = struct.unpack_from("<I", b, 4)[0]
        zone = _resolve(con, zmap, emap, appr, uid, m)
        lines = " | ".join(_chat_near(chat, ts))
        if not zone or not lines:
            continue
        zid = zoneid_for_zone_db(con, zone)
        if zid is None:
            continue
        if zid not in dcache:
            dcache[zid] = dict(con.execute("SELECT idx,text FROM dialog_text WHERE zoneid=?", (zid,)))
        d = dcache[zid]
        cands = [o for o in RANGE if len(_norm(d.get(m - o))) >= 8 and _norm(d.get(m - o)) in lines]
        if len(cands) == 1:               # ambiguous matches are never recorded as evidence
            found[(zid, m, cands[0])] += 1
    con.execute("DELETE FROM msgid_shift_obs WHERE capture_id=?", (capture_id,))
    con.executemany("INSERT INTO msgid_shift_obs VALUES (?,?,?,?,?)",
                    [(capture_id, z, m, o, n) for (z, m, o), n in found.items()])
    con.commit()
    return len(found)


def build_master(con):
    """Merge all observations into per-zone id ranges. conflict=1 when captures disagree on the
    same id (different client builds) -- surfaced, never silently resolved."""
    ensure_master_tables(con)
    con.execute("DELETE FROM msgid_shift_master")
    byz = collections.defaultdict(lambda: collections.defaultdict(collections.Counter))
    caps = collections.defaultdict(set)
    for cid, z, m, o, n in con.execute("SELECT capture_id,zoneid,msgid,shift,n FROM msgid_shift_obs"):
        byz[z][m][o] += n
        caps[(z, m, o)].add(cid)
    rows = 0
    for z, ids in byz.items():
        segs, prev_hi = [], None
        for m in sorted(ids):
            o, _ = ids[m].most_common(1)[0]
            conflict = int(len(ids[m]) > 1)
            if segs and segs[-1]["shift"] == o:
                s = segs[-1]; s["hi"] = m; s["obs"] += sum(ids[m].values()); s["conflict"] |= conflict
                s["caps"] |= caps[(z, m, o)]
            else:
                segs.append(dict(lo=m, hi=m, shift=o, obs=sum(ids[m].values()), conflict=conflict,
                                 caps=set(caps[(z, m, o)]), gap=(m - segs[-1]["hi"]) if segs else None))
        # drop weak ranges (<MIN_HITS obs: likely coincidental text matches), then re-merge neighbours
        strong = [x for x in segs if x["obs"] >= MIN_HITS]
        segs = []
        for x in strong:
            if segs and segs[-1]["shift"] == x["shift"]:
                segs[-1].update(hi=x["hi"], obs=segs[-1]["obs"] + x["obs"], conflict=segs[-1]["conflict"] | x["conflict"])
                segs[-1]["caps"] |= x["caps"]
            else:
                x["gap"] = (x["lo"] - segs[-1]["hi"]) if segs else None
                segs.append(x)
        for s in segs:
            con.execute("INSERT INTO msgid_shift_master VALUES (?,?,?,?,?,?,?,?)",
                        (z, s["lo"], s["hi"], s["shift"], s["obs"], len(s["caps"]), s["gap"], s["conflict"]))
            rows += 1
    con.commit()
    return rows


def master_lookup(con, zoneid, msgid):
    """-> (shift|None, status). status: 'verified' (inside an observed range), 'extended' (between two
    ranges with the same shift), 'boundary' (between ranges with different shifts: unknown),
    'outside' (beyond observed ranges), 'none' (no data)."""
    ensure_master_tables(con)
    segs = con.execute("SELECT id_lo,id_hi,shift,conflict FROM msgid_shift_master WHERE zoneid=? ORDER BY id_lo", (zoneid,)).fetchall()
    if not segs:
        return None, "none"
    for lo, hi, sh, cf in segs:
        if lo <= msgid <= hi:
            return (None, "boundary") if cf else (sh, "verified")
    for a, b in zip(segs, segs[1:]):
        if a[1] < msgid < b[0]:
            return (a[2], "extended") if a[2] == b[2] else (None, "boundary")
    return None, "outside"


def zoneid_for_zone_db(con, zone_db):
    """Same normalization gui_server uses: NPCLogger spaced names / '[S]' -> zones.name form."""
    import re
    n = zone_db.upper().replace(" ", "_").replace("'", "").replace("-", "_")
    n = re.sub(r"_?\[S\]$", "_S", n)
    r = con.execute("SELECT zoneid FROM zones WHERE REPLACE(name,' ','_')=?", (n,)).fetchone()
    return r[0] if r else None


REPORT_PATH = r"D:\Claude\mission_toolkit\docs\shift_report.log"


def update_after_ingest(con, capture_id, report_path=None):
    """Run at the end of every capture ingest: record this capture's observations, refresh the
    per-capture measurement and the piecewise master, and APPEND one report block (never
    overwrites). Failures are reported in the log, never raised -- must not break ingestion."""
    import datetime
    import os
    path = report_path or REPORT_PATH
    lines = ["[%s] capture %s" % (datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), capture_id)]
    try:
        from workbench.captures import review_queue as rq
        rq.scan_capture(con, capture_id)
        npend = len(rq.items(con, "pending", capture_id=capture_id))
        n = observe(con, capture_id, zoneid_for_zone_db)
        per = compute(con, capture_id, zoneid_for_zone_db)
        build_master(con)
        if npend:
            lines.append("  REVIEW: %d exception(s) pending (blocking ones exclude this capture from shift evidence) "
                         "(python -m workbench.captures.review_queue list)" % npend)
            for it in rq.items(con, "pending", capture_id=capture_id):
                lines.append("    review #%s [%s] %s" % (it["review_id"], it["kind"], it["detail"].get("reason", "")))
        lines.append("  observations: %d" % n)
        for zone, zid, best, bh, tot, ru, conf in per:
            lines.append("  %s (zone %s): shift %s hits %d/%d runner-up %d %s" % (
                zone, zid, ("%+d" % best) if conf else "unverified", bh, tot, ru,
                "CONFIDENT" if conf else "no confident shift"))
        if not per:
            lines.append("  no 0x036 chat packets matched to a zone (no shift evidence)")
        for zid, in con.execute("SELECT DISTINCT zoneid FROM msgid_shift_obs WHERE capture_id=?", (capture_id,)):
            for lo, hi, sh, ob, caps, cf in con.execute(
                    "SELECT id_lo,id_hi,shift,obs,captures,conflict FROM msgid_shift_master WHERE zoneid=? ORDER BY id_lo", (zid,)):
                lines.append("  master zone %s %d-%d: %+d (obs %d, captures %d)%s" % (
                    zid, lo, hi, sh, ob, caps, " CONFLICT" if cf else ""))
    except Exception as ex:
        lines.append("  shift check FAILED: %r" % (ex,))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    return lines

