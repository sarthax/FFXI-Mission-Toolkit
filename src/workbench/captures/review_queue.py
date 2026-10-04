"""Generic capture exception queue.

A capture that is missing data, or has data we could not verify, must never sit in the database looking
normal. Every such condition becomes a row in `review_queue` (one per kind + capture + key). While a row of
a *blocking* kind is pending, the capture is quarantined: derived pipelines (msgid-shift evidence, ...) skip
it via `is_quarantined()`, and the GUI flags it everywhere. Raw data stays accessible -- quarantine hides
nothing, it only keeps unreviewed captures out of derived results.

Kinds are registered in KINDS. Each has a detector (what is wrong with a capture right now) and a decision
handler (what the reviewer's choice does). `scan_capture()` runs every detector for one capture: it raises new
items, refreshes existing ones, and marks pending items `auto_resolved` once the condition has gone away.
Decided items (resolved/dismissed) are kept and keyed on source_path, so they survive re-ingest.

CLI:  python -m workbench.captures.review_queue list [pending|all] | scan [capture_id] | resolve ID [VALUE] | dismiss ID [NOTE]
"""
import collections
import datetime
import json
import os
import re
import shutil
import sqlite3
import struct

DB_PATH = os.environ.get("MISSION_TOOLKIT_DB", r"D:\Claude\mission_toolkit\ffxi_zone_database.db")

DDL = """CREATE TABLE IF NOT EXISTS review_queue (
    review_id INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT NOT NULL, source_path TEXT, capture_id INTEGER,
    key TEXT NOT NULL DEFAULT '', detail TEXT, status TEXT NOT NULL DEFAULT 'pending',
    resolution TEXT, note TEXT, created_at TEXT, reviewed_at TEXT, UNIQUE(kind, source_path, key))"""

# status: pending | resolved | dismissed | auto_resolved
# Failed/partial ingests: a copy of the source archive is kept here for manual inspection (files only; folders stay in place).
COPY_DIR = os.environ.get("CAPTURE_REVIEW_COPY_DIR", "D:/Claude/review_quarantine")
MAX_COPY_BYTES = 4 * 1024 ** 3
_SKIP_TABLES = {"captures", "capture_tags", "capture_post_meta", "capture_msgid_shift", "msgid_shift_obs", "review_queue"}


def ensure(con):
    con.execute(DDL)


def _now():
    return datetime.datetime.now().isoformat(timespec="seconds")


def _src(con, capture_id):
    r = con.execute("SELECT source_path FROM captures WHERE capture_id=?", (capture_id,)).fetchone()
    return r[0] if r else None


def _row(r):
    d = dict(zip([c for c in ("review_id", "kind", "source_path", "capture_id", "key", "detail", "status",
                              "resolution", "note", "created_at", "reviewed_at")], r))
    d["detail"] = json.loads(d["detail"]) if d["detail"] else {}
    return d


_COLS = "review_id,kind,source_path,capture_id,key,detail,status,resolution,note,created_at,reviewed_at"


def raise_item(con, kind, source_path, capture_id, key="", detail=None):
    """Create or refresh a pending item. A previously decided item for the same (kind, source, key) is kept as is,
    except auto_resolved ones, which reopen if the condition returns."""
    ensure(con)
    d = json.dumps(detail or {}, sort_keys=True)
    cur = con.execute("SELECT review_id,status FROM review_queue WHERE kind=? AND source_path=? AND key=?",
                      (kind, source_path, key)).fetchone()
    if cur is None:
        con.execute("INSERT INTO review_queue (kind,source_path,capture_id,key,detail,created_at) VALUES (?,?,?,?,?,?)",
                    (kind, source_path, capture_id, key, d, _now()))
    elif cur[1] in ("pending", "auto_resolved"):
        con.execute("UPDATE review_queue SET detail=?, capture_id=?, status='pending', reviewed_at=NULL WHERE review_id=?",
                    (d, capture_id, cur[0]))
    else:
        con.execute("UPDATE review_queue SET capture_id=? WHERE review_id=?", (capture_id, cur[0]))
    con.commit()


def close_stale(con, kind, source_path, live_keys):
    """Pending items of this kind whose condition no longer holds -> auto_resolved (kept for audit)."""
    ensure(con)
    for rid, k in con.execute("SELECT review_id,key FROM review_queue WHERE kind=? AND source_path=? AND status='pending'",
                              (kind, source_path)).fetchall():
        if k not in live_keys:
            con.execute("UPDATE review_queue SET status='auto_resolved', reviewed_at=? WHERE review_id=?", (_now(), rid))
    con.commit()


def items(con, status="pending", kind=None, capture_id=None):
    ensure(con)
    q, p = "SELECT %s FROM review_queue WHERE 1=1" % _COLS, []
    if status != "all":
        q += " AND status=?"
        p.append(status)
    if kind:
        q += " AND kind=?"
        p.append(kind)
    if capture_id is not None:
        q += " AND source_path=?"
        p.append(_src(con, capture_id))
    return [_row(r) for r in con.execute(q + " ORDER BY capture_id, kind, review_id", p)]


def pending_count(con, blocking_only=False):
    ensure(con)
    ks = [k for k, h in KINDS.items() if h["blocking"]] if blocking_only else list(KINDS)
    ks += [] if ks else ["__none__"]
    return con.execute("SELECT COUNT(*) FROM review_queue WHERE status='pending' AND kind IN (%s)" % ",".join("?" * len(ks)),
                       ks).fetchone()[0]


def is_quarantined(con, capture_id):
    """True while the capture has a pending item of a blocking kind. Derived pipelines should call this."""
    ensure(con)
    ks = [k for k, h in KINDS.items() if h["blocking"]]
    return con.execute("SELECT 1 FROM review_queue WHERE source_path=? AND status='pending' AND kind IN (%s) LIMIT 1"
                       % ",".join("?" * len(ks)), [_src(con, capture_id)] + ks).fetchone() is not None


def pending_by_capture(con):
    """{capture_id: [kinds]} for every capture with a pending item (any kind) -- drives GUI flags."""
    ensure(con)
    out = collections.defaultdict(list)
    for cid, k in con.execute("SELECT capture_id,kind FROM review_queue WHERE status='pending' AND capture_id IS NOT NULL"):
        out[cid].append(k)
    return out


# ---------------------------------------------------------------- detectors
def _data_tables(con):
    out = []
    for (t,) in con.execute("SELECT name FROM sqlite_master WHERE type='table'"):
        if t in _SKIP_TABLES or t.startswith("sqlite_"):
            continue
        if any(r[1] == "capture_id" for r in con.execute("PRAGMA table_info(%s)" % t)):
            out.append(t)
    return out


def detect_empty(con, capture_id):
    """A capture with no rows in ANY capture data table: ingest produced nothing."""
    for t in _data_tables(con):
        if con.execute("SELECT 1 FROM %s WHERE capture_id=? LIMIT 1" % t, (capture_id,)).fetchone():
            return {}
    return {"": {"reason": "ingest produced no rows in any capture data table"}}


def detect_zone(con, capture_id):
    from workbench.captures import msgid_shift as ms
    return ms.review_candidates(con, capture_id)


def detect_manifest(con, capture_id):
    """Discord #campaign captures that could not be linked to their post (no capture_post_meta row)."""
    r = con.execute("SELECT capture_label, source_path FROM captures WHERE capture_id=?", (capture_id,)).fetchone()
    if not r or "campaign" not in ((r[0] or "") + (r[1] or "")).lower():
        return {}
    if con.execute("SELECT 1 FROM capture_post_meta WHERE capture_id=?", (capture_id,)).fetchone():
        return {}
    from workbench.core.services import campaign_manifest as cm
    import difflib
    try:
        rows = json.load(open(cm.MANIFEST_PATH, encoding="utf-8"))
    except Exception:
        return {}
    _, _, amb = cm.match(con, rows=rows, only_ids={capture_id})
    tail = cm._norm(re.split(r"campaign - |:: ", r[0] or "", flags=re.I)[-1])
    if amb:
        cands, why = amb[0][1], "ambiguous: more than one manifest title matches"
    else:
        sc = sorted(((difflib.SequenceMatcher(None, tail, cm._norm(x.get("title", ""))).ratio(), x.get("title", ""))
                     for x in rows), reverse=True)[:8]
        cands, why = [t for _, t in sc], "no confident manifest match; closest titles listed"
    return {"": {"reason": why, "candidates": cands}}


def link_manifest(con, capture_id, title):
    from workbench.core.services import campaign_manifest as cm
    rows = json.load(open(cm.MANIFEST_PATH, encoding="utf-8"))
    hit = [x for x in rows if x.get("title") == title]
    if len(hit) != 1:
        raise ValueError("manifest has %d rows titled %r (need exactly 1)" % (len(hit), title))
    cm.ensure_table(con)
    cm.link(con, capture_id, hit[0], "manual-review")


# ---------------------------------------------------------------- decision handlers
def _decide_zone(con, row, action, value):
    from workbench.captures import msgid_shift as ms
    if action == "resolve":
        if not value or ms.zoneid_for_zone_db(con, value) is None:
            raise ValueError("choose a zone that exists in zones (got %r)" % (value,))
        return value
    return None


def _after_zone(con, row):
    from workbench.captures import msgid_shift as ms
    ms.update_after_ingest(con, row["capture_id"])


def _decide_manifest(con, row, action, value):
    if action == "resolve":
        link_manifest(con, row["capture_id"], value)
        return value
    return None


def _decide_noop(con, row, action, value):
    return None


KINDS = {
    "zone": {"label": "Packet zone unresolved", "blocking": True, "detect": detect_zone, "decide": _decide_zone,
             "after": _after_zone, "actions": [("resolve", "Approve zone"), ("dismiss", "Reject")], "value": "zone",
             "help": "0x036 chat packets whose zone no automatic fallback could resolve. Approve with the real zone."},
    "empty_ingest": {"label": "Empty ingest", "blocking": True, "detect": detect_empty, "decide": _decide_noop,
                     "after": None, "actions": [("dismiss", "Confirm empty / ignore")], "value": None,
                     "help": "Ingest produced no data at all. Fix the source/parser and re-scan (it clears itself), or dismiss with a note if the capture really is empty."},
    "manifest_link": {"label": "Campaign post not linked", "blocking": False, "detect": detect_manifest,
                      "decide": _decide_manifest, "after": None,
                      "actions": [("resolve", "Link to post"), ("dismiss", "Not a campaign capture")], "value": "title",
                      "help": "Discord #campaign capture with no post metadata. Pick the matching manifest title."},
}


KINDS["ingest_failed"] = {
    "label": "Ingest failed", "blocking": True, "detect": None, "decide": _decide_noop, "after": None,
    "actions": [("resolve", "Mark fixed"), ("dismiss", "Ignore")], "value": None, "needs_note": True,
    "help": "The source could not be ingested. A copy of the archive is in the review folder for manual inspection; fix the parser/source and re-ingest (this clears itself), or dismiss with a note."}
KINDS["file_error"] = {
    "label": "File failed to parse", "blocking": True, "detect": None, "decide": _decide_noop, "after": None,
    "actions": [("resolve", "Mark fixed"), ("dismiss", "Ignore")], "value": None, "needs_note": True,
    "help": "A recognized log file threw while parsing, so its data is missing from this capture."}
KINDS["unrecognized_file"] = {
    "label": "Unrecognized file", "blocking": False, "detect": None, "decide": _decide_noop, "after": None,
    "actions": [("resolve", "Reviewed"), ("dismiss", "Ignore")], "value": None,
    "help": "Files in the bundle matched no known capture format and were not ingested (a known gap or a new format)."}

KINDS["duplicate_source"] = {
    "label": "Duplicate source skipped", "blocking": False, "detect": None, "decide": _decide_noop, "after": None,
    "actions": [("resolve", "Reviewed"), ("dismiss", "Ignore")], "value": None,
    "help": "This archive has the same content as an already-ingested capture and was skipped. Re-ingest with --force if it should be separate."}

# ---------------------------------------------------------------- event-driven kinds (raised by ingest, no detector)
EVENT_KINDS = ("ingest_failed", "file_error", "unrecognized_file", "duplicate_source")


def copy_for_review(path):
    """Copy a failed archive into COPY_DIR so it can be opened by hand. -> {copy_path, copy_note}. Never raises."""
    try:
        p = os.path.abspath(str(path))
        if not os.path.exists(p):
            return {"copy_path": None, "copy_note": "source no longer exists at %s" % p}
        if os.path.isdir(p):
            return {"copy_path": None, "copy_note": "source is a folder; original left in place"}
        size = os.path.getsize(p)
        if size > MAX_COPY_BYTES:
            return {"copy_path": None, "copy_note": "source is %.1f GB (> %.0f GB limit); original left in place" % (size / 1e9, MAX_COPY_BYTES / 1e9)}
        os.makedirs(COPY_DIR, exist_ok=True)
        dest = os.path.join(COPY_DIR, datetime.datetime.now().strftime("%Y%m%d-%H%M%S_") + os.path.basename(p))
        shutil.copy2(p, dest)
        return {"copy_path": dest, "copy_note": "copied %.1f MB" % (size / 1e6)}
    except Exception as ex:
        return {"copy_path": None, "copy_note": "copy failed: %r" % (ex,)}


def _reopen_event(con, source_path):
    """A new ingest attempt supersedes earlier event-driven items for this source (kept as auto_resolved)."""
    ensure(con)
    con.execute("UPDATE review_queue SET status='auto_resolved', reviewed_at=? WHERE source_path=? AND status='pending' AND kind IN (%s)"
                % ",".join("?" * len(EVENT_KINDS)), [_now(), source_path] + list(EVENT_KINDS))
    con.commit()


def report_ingest_failure(con, source_path, path, error, capture_id=None, content_type=None, subroot=None):
    """Ingest of this source threw. Records the error, the ingest parameters (so it can be retried) and a copy of
    the archive. Any half-written capture row stays but is quarantined by this blocking item."""
    _reopen_event(con, source_path)
    detail = {"reason": "ingest failed -- nothing (or only part) of this source reached the database",
              "error": "%s: %s" % (type(error).__name__, error), "path": str(path),
              "content_type": content_type, "subroot": subroot}
    detail.update(copy_for_review(path))
    raise_item(con, "ingest_failed", source_path, capture_id, "", detail)


_BENIGN = ("manifest.txt", "thumbs.db", "desktop.ini", ".ds_store")


def report_file_results(con, source_path, capture_id, file_results):
    """Per-file outcome of an ingest. Files that matched a known format but threw -> blocking `file_error`
    (data is missing); files matching no known format -> non-blocking `unrecognized_file` (visible, listed)."""
    _reopen_event(con, source_path)
    errs = [{"filename": f["filename"], "error": f["error"]} for f in file_results
            if f.get("error") and not f["error"].startswith("not a recognized capture-log format")]
    unrec = [{"filename": f["filename"], "error": f["error"]} for f in file_results
             if f.get("error") and f["error"].startswith("not a recognized capture-log format")
             and f["filename"].rsplit("/", 1)[-1].lower() not in _BENIGN]
    if errs:
        raise_item(con, "file_error", source_path, capture_id, "",
                   {"reason": "%d recognized file(s) failed to parse; their data is missing" % len(errs), "files": errs})
    if unrec:
        raise_item(con, "unrecognized_file", source_path, capture_id, "",
                   {"reason": "%d file(s) matched no known capture format and were not ingested" % len(unrec), "files": unrec})


def decide(con, review_id, action, value=None, note=None):
    """action: 'resolve' | 'dismiss'. Returns the item. Raises ValueError on invalid input (nothing saved)."""
    ensure(con)
    r = con.execute("SELECT %s FROM review_queue WHERE review_id=?" % _COLS, (review_id,)).fetchone()
    if not r:
        raise ValueError("no such review_id %s" % review_id)
    row = _row(r)
    h = KINDS.get(row["kind"])
    if h is None:
        raise ValueError("unknown kind %r" % row["kind"])
    if action not in dict(h["actions"]):
        raise ValueError("%s does not support %r" % (row["kind"], action))
    if action == "dismiss" and (row["kind"] == "empty_ingest" or h.get("needs_note")) and not (note or "").strip():
        raise ValueError("dismissing needs a note saying why")
    resolution = h["decide"](con, row, action, value)
    con.execute("UPDATE review_queue SET status=?, resolution=?, note=?, reviewed_at=? WHERE review_id=?",
                ("resolved" if action == "resolve" else "dismissed", resolution, note, _now(), review_id))
    con.commit()
    if h["after"]:
        h["after"](con, row)
    return row


# ---------------------------------------------------------------- scan
def scan_capture(con, capture_id):
    """Run every detector for one capture. Never raises (must not break ingestion). Returns pending items."""
    ensure(con)
    src = _src(con, capture_id)
    if src is None:
        return []
    for kind, h in KINDS.items():
        if h["detect"] is None:      # event-driven kinds are raised by ingest, never closed by a scan
            continue
        try:
            live = h["detect"](con, capture_id)
            for key, detail in live.items():
                raise_item(con, kind, src, capture_id, key, detail)
            close_stale(con, kind, src, set(live))
        except Exception as ex:
            print("  [review scan %s failed for capture %s: %r]" % (kind, capture_id, ex))
    return items(con, "pending", capture_id=capture_id)


def _cli(argv):
    con = sqlite3.connect(DB_PATH, timeout=60)
    cmd = argv[0] if argv else "list"
    if cmd == "list":
        for r in items(con, argv[1] if len(argv) > 1 else "pending"):
            print("#%s [%s] %s cap %s key=%r %s | %s" % (r["review_id"], r["status"], r["kind"], r["capture_id"], r["key"],
                  r["resolution"] or "", json.dumps(r["detail"])[:160]))
    elif cmd == "scan":
        ids = [int(argv[1])] if len(argv) > 1 else [r[0] for r in con.execute("SELECT capture_id FROM captures")]
        n = 0
        for i in ids:
            n += len(scan_capture(con, i))
        print("scanned %d capture(s); pending items now %d" % (len(ids), pending_count(con)))
    elif cmd in ("resolve", "dismiss"):
        r = decide(con, int(argv[1]), cmd, argv[2] if cmd == "resolve" else None, argv[2] if cmd == "dismiss" and len(argv) > 2 else None)
        print("#%s %s -> %s" % (r["review_id"], r["kind"], cmd))
    else:
        print(__doc__)


if __name__ == "__main__":
    import sys
    _cli(sys.argv[1:])
