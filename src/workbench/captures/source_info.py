"""Capture source information (who posted a capture, when, video link, type, tags) -- entered by hand,
picked from the Discord #campaign post list, or bulk-imported from a CSV sheet.

The sheet is a plain CSV: download the template (blank or pre-filled with the captures that still need
source info), fill it in, upload it. Every row is validated; bad rows are reported by line and nothing
from them is written.
"""
import csv
import datetime
import io
import os
import re

from workbench.core.services import campaign_manifest as cm

COLUMNS = ["capture_id", "capture_file", "uploader", "post_date", "title", "video_url",
           "capture_type", "secondary_types", "tags", "zones", "notes"]
HELP = [
    "# Capture source information sheet. Lines starting with # are ignored.",
    "# Identify each capture by capture_id (preferred) OR capture_file (the zip/folder name, e.g. My Capture.zip).",
    "# At least one of uploader / title / video_url is required. Leave a cell blank to leave that field empty.",
    "# post_date: YYYY-MM-DD.  video_url: full http(s) link.  capture_type: one value from the allowed list shown on the import page.",
    "# secondary_types and tags: separate several values with ;   Existing source info is only replaced when overwrite is ticked.",
]


def allowed_types(con):
    s = set(cm._TYPE_TAGS)
    try:
        s |= {r[0] for r in con.execute("SELECT DISTINCT capture_type FROM capture_post_meta WHERE capture_type<>''")}
    except Exception:
        pass
    return sorted(s)


def template_csv(con, scope="pending"):
    """scope 'pending' pre-fills one row per capture with a pending manifest_link item; 'blank' is headers only."""
    out = io.StringIO()
    w = csv.writer(out, lineterminator="\n")
    for h in HELP:
        out.write(h + "\n")
    w.writerow(COLUMNS)
    if scope == "pending":
        for cid, label, sp in con.execute(
                """SELECT c.capture_id, c.capture_label, c.source_path FROM captures c
                   WHERE c.capture_id IN (SELECT capture_id FROM review_queue WHERE kind='manifest_link' AND status='pending')
                   ORDER BY c.capture_id""").fetchall():
            base = os.path.basename((sp or "").split("::")[0].replace("\\", "/"))
            w.writerow([cid, base, "", "", label or "", "", "", "", "", "", ""])
    return out.getvalue()


def _find(con, cid, fname):
    if cid:
        try:
            r = con.execute("SELECT capture_id FROM captures WHERE capture_id=?", (int(cid),)).fetchone()
        except ValueError:
            return None, "capture_id %r is not a number" % cid
        return (r[0], None) if r else (None, "no capture with id %s" % cid)
    if fname:
        hits = con.execute("SELECT capture_id FROM captures WHERE lower(source_path)=lower(?) OR lower(source_path) LIKE lower(?) "
                           "OR lower(source_path) LIKE lower(?)", (fname, "%\\" + fname + "%", "%/" + fname + "%")).fetchall()
        if len(hits) == 1:
            return hits[0][0], None
        return None, ("no capture matches file %r" % fname) if not hits else "%d captures match file %r -- use capture_id" % (len(hits), fname)
    return None, "row needs capture_id or capture_file"


def validate(con, row, types):
    """-> (clean dict or None, error or None)"""
    g = lambda k: (row.get(k) or "").strip()
    if not (g("uploader") or g("title") or g("video_url")):
        return None, "needs at least one of uploader / title / video link"
    d = g("post_date")
    if d:
        try:
            datetime.date.fromisoformat(d)
        except ValueError:
            return None, "post_date %r is not YYYY-MM-DD" % d
    v = g("video_url")
    if v and not re.match(r"^https?://\S+$", v):
        return None, "video_url %r is not a full http(s) link" % v
    t = g("capture_type")
    if t and t not in types:
        return None, "capture_type %r not allowed (one of: %s)" % (t, ", ".join(types))
    sec = [x.strip() for x in g("secondary_types").split(";") if x.strip()]
    for t2 in sec:
        if t2 not in types:
            return None, "secondary type %r not allowed" % t2
    return {"uploader": g("uploader"), "post_date": d, "title": g("title"), "video_url": v, "capture_type": t,
            "secondary_types": ";".join(sec),
            "tags": ";".join(x.strip() for x in g("tags").split(";") if x.strip()),
            "zones": g("zones"), "notes": g("notes")}, None


def apply_one(con, cid, f, how="manual", commit=True):
    """Write one capture's source info via the same code path the Discord manifest uses."""
    cm.ensure_table(con)
    r = {"file_url": "", "host": "manual", "post_date": f["post_date"], "date_note": "entered" if f["post_date"] else "",
         "uploader": f["uploader"], "title": f["title"], "video_url": f["video_url"], "extra_video_urls": "",
         "capture_type": f["capture_type"], "secondary_types": f["secondary_types"], "tags": f["tags"],
         "zones": f["zones"], "ops_missions": ""}
    return cm.link(con, cid, r, how, commit=commit)


def import_csv(con, text, dry_run=True, overwrite=False):
    """-> {'applied':[(line,cid)], 'errors':[(line,msg)], 'skipped':[(line,msg)]}. Nothing is written for a row
    with an error. dry_run validates only."""
    rep = {"applied": [], "errors": [], "skipped": []}
    text = text.lstrip("﻿")
    kept = [(i + 1, l) for i, l in enumerate(text.splitlines()) if not l.lstrip().startswith("#") and l.strip()]
    if not kept:
        rep["errors"].append((0, "the sheet is empty"))
        return rep
    rdr = csv.reader(io.StringIO("\n".join(l for _, l in kept)))
    header = [h.strip() for h in next(rdr)]
    if "capture_id" not in header and "capture_file" not in header:
        rep["errors"].append((kept[0][0], "header row must include capture_id or capture_file (got %s)" % header))
        return rep
    cm.ensure_table(con)
    types = allowed_types(con)
    seen = set()
    for n, vals in enumerate(rdr):
        line = kept[n + 1][0] if n + 1 < len(kept) else 0
        row = dict(zip(header, vals))
        cid, err = _find(con, (row.get("capture_id") or "").strip(), (row.get("capture_file") or "").strip())
        if err:
            rep["errors"].append((line, err))
            continue
        if cid in seen:
            rep["errors"].append((line, "capture %s appears twice in the sheet" % cid))
            continue
        seen.add(cid)
        clean, err = validate(con, row, types)
        if err:
            rep["errors"].append((line, "capture %s: %s" % (cid, err)))
            continue
        if not overwrite and con.execute("SELECT 1 FROM capture_post_meta WHERE capture_id=?", (cid,)).fetchone():
            rep["skipped"].append((line, "capture %s already has source info (tick overwrite to replace)" % cid))
            continue
        if not dry_run:
            apply_one(con, cid, clean, "sheet", commit=False)
        rep["applied"].append((line, cid))
    if not dry_run and rep["applied"]:
        con.commit()
        from workbench.captures import review_queue as rq
        for _, cid in rep["applied"]:
            rq.scan_capture(con, cid)          # clears the 'no source info' item
    return rep
