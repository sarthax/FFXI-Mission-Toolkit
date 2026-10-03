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


def compute(con, capture_id, zoneid_for_zone_db):
    ensure_table(con)
    zmap = {(r[0], r[1]): r[2] for r in con.execute(
        "SELECT entity_id, message_id, zone_db FROM capture_events WHERE capture_id=? "
        "AND message_id IS NOT NULL AND opcode_name LIKE '%Chat%'", (capture_id,))}
    chat = collections.defaultdict(list)
    for ts, t in con.execute("SELECT ts,text FROM capture_caplog_chat WHERE capture_id=?", (capture_id,)):
        chat[ts].append(t or "")
    per = collections.defaultdict(list)
    for ts, hx in con.execute("SELECT ts, raw_hex FROM capture_raw_packets WHERE capture_id=? AND opcode='0X036'", (capture_id,)):
        b = bytes.fromhex(hx.replace(" ", ""))
        if len(b) < 12:
            continue
        uid = struct.unpack_from("<I", b, 4)[0]
        m = struct.unpack_from("<H", b, 10)[0] & 0x7FFF
        zone = zmap.get((uid, m))
        if zone:
            per[zone].append((m, " | ".join(chat.get((ts or "")[11:], []))))
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
    zmap = {(r[0], r[1]): r[2] for r in con.execute(
        "SELECT entity_id, message_id, zone_db FROM capture_events WHERE capture_id=? "
        "AND message_id IS NOT NULL AND opcode_name LIKE '%Chat%'", (capture_id,))}
    chat = collections.defaultdict(list)
    for ts, t in con.execute("SELECT ts,text FROM capture_caplog_chat WHERE capture_id=?", (capture_id,)):
        chat[ts].append(t or "")
    dcache, found = {}, collections.Counter()
    for ts, hx in con.execute("SELECT ts, raw_hex FROM capture_raw_packets WHERE capture_id=? AND opcode='0X036'", (capture_id,)):
        b = bytes.fromhex(hx.replace(" ", ""))
        if len(b) < 12:
            continue
        m = struct.unpack_from("<H", b, 10)[0] & 0x7FFF
        zone = zmap.get((struct.unpack_from("<I", b, 4)[0], m))
        lines = " | ".join(chat.get((ts or "")[11:], []))
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
