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
