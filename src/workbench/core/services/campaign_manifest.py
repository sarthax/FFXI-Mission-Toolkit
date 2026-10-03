"""Cross-link ingested captures to their Discord #campaign posts (post date, uploader, video, category).

Source: D:\\Claude\\docs\\campaign\\campaign_manifest.json (built by build_manifest.py from
CAPTURE_INDEX.md; one row per downloadable file). Nothing here invents data: a capture is only
linked when its label/source path contains the manifest row's own title (or, for Dropbox zips, the
zip's real filename). Ambiguous or unmatched captures are reported, never guessed.

Writes:
  * capture_post_meta (new, additive table) -- one row per linked capture
  * captures.video_url -- only when currently empty
  * capture_tags -- INSERT OR IGNORE of real CAPTURE_TAGS names (never deletes existing tags)
"""
import json
import os
import re
import sqlite3
from pathlib import Path

MANIFEST_PATH = Path(os.environ.get("CAMPAIGN_MANIFEST", r"D:\Claude\docs\campaign\campaign_manifest.json"))

# manifest capture_type / tag -> real CAPTURE_TAGS names (see _build_index_impl.CAPTURE_TAGS)
_TYPE_TAGS = {
    "ops-menu": ["Missions"], "reconnaissance": ["Missions"], "voting": ["Missions"],
    "evaluation-promotion": ["Missions"], "headhunting": ["Missions"],
    "npc-text": ["NPC"], "campaign-battle": ["Battle"],
    "mechanics-test": ["Research"], "mob-data": ["Research"], "packet-log": ["Research"],
    "influence-tracking": ["Research"], "pathing": ["Research"],
}
_TAG_TAGS = {"nm-unit": ["Notorious Monsters"]}


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (s or "").lower())


_PREFIX = _norm("Conflict - Campaign - ")


def ensure_table(con: sqlite3.Connection):
    con.execute("""CREATE TABLE IF NOT EXISTS capture_post_meta (
        capture_id INTEGER PRIMARY KEY, file_url TEXT, host TEXT, post_date TEXT, date_note TEXT,
        uploader TEXT, title TEXT, video_url TEXT, extra_video_urls TEXT, capture_type TEXT,
        secondary_types TEXT, tags TEXT, manifest_zones TEXT, ops_missions TEXT, matched_by TEXT)""")


def _keys(row: dict) -> list[tuple[str, str]]:
    ks = []
    fn = row.get("expected_filename") or ""
    if fn:
        ks.append((_norm(re.sub(r"\.\w+$", "", fn)), "filename"))
    t = _norm(row.get("title", ""))
    if t.startswith(_PREFIX):
        t = t[len(_PREFIX):]
    if len(t) >= 8:
        ks.append((t, "title"))
    return ks


def match(con, rows=None, only_ids=None):
    """-> (matches[(capture_id,row,how)], unmatched_rows, ambiguous[(capture_id,[titles])])."""
    rows = rows if rows is not None else json.load(open(MANIFEST_PATH, encoding="utf-8"))
    q = "SELECT capture_id, capture_label, source_path FROM captures"
    caps = [c for c in con.execute(q) if only_ids is None or c[0] in only_ids]
    hay = {cid: _norm((label or "") + " " + (path or "")) for cid, label, path in caps}
    cand = {}
    for i, r in enumerate(rows):
        for k, how in _keys(r):
            for cid, h in hay.items():
                if k and k in h:
                    cand.setdefault(cid, []).append((len(k), i, how))
    matches, used_rows, ambiguous = [], set(), []
    for cid, lst in cand.items():
        lst.sort(reverse=True)
        best = [x for x in lst if x[0] == lst[0][0]]
        if len({x[1] for x in best}) > 1:
            ambiguous.append((cid, [rows[x[1]]["title"] for x in best]))
            continue
        _, i, how = best[0]
        matches.append((cid, rows[i], how))
        used_rows.add(i)
    # pass 2: folders renamed/truncated at download time -- label tail inside a manifest title
    # (or a close, clearly-best fuzzy match). Only for campaign_captures folders, only when unique.
    import difflib
    done = {m[0] for m in matches} | {a[0] for a in ambiguous}
    for cid, label, path in caps:
        if cid in done or "campaign_captures" not in (path or "") + (label or ""):
            continue
        tail = _norm(re.split(r"campaign - |:: ", label or "", flags=re.I)[-1])
        tail = tail[len(_PREFIX):] if tail.startswith(_PREFIX) else tail
        if len(tail) < 10:
            continue
        scored = []
        for i, r in enumerate(rows):
            if i in used_rows:
                continue
            for k, how in _keys(r):
                if how != "title":
                    continue
                s = 1.0 if tail in k else difflib.SequenceMatcher(None, tail, k).ratio()
                scored.append((s, i))
        scored.sort(reverse=True)
        if scored and scored[0][0] >= 0.85 and (len(scored) == 1 or scored[0][0] - scored[1][0] >= 0.1 or scored[0][0] == 1.0 and scored[1][0] < 1.0):
            i = scored[0][1]
            matches.append((cid, rows[i], "title-fuzzy"))
            used_rows.add(i)
    unmatched = [r for i, r in enumerate(rows) if i not in used_rows]
    return matches, unmatched, ambiguous


def apply(con, only_ids=None, dry_run=False, verbose=True):
    ensure_table(con)
    matches, unmatched, ambiguous = match(con, only_ids=only_ids)
    n_tags = n_vid = 0
    for cid, r, how in matches:
        if dry_run:
            continue
        con.execute("""INSERT OR REPLACE INTO capture_post_meta VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (cid, r["file_url"], r["host"], r["post_date"], r["date_note"], r["uploader"], r["title"],
                     r["video_url"], r["extra_video_urls"], r["capture_type"], r["secondary_types"], r["tags"],
                     r["zones"], r["ops_missions"], how))
        if r["video_url"]:
            n_vid += con.execute("UPDATE captures SET video_url=? WHERE capture_id=? AND (video_url IS NULL OR video_url='')",
                                 (r["video_url"], cid)).rowcount
        tags = {"Conflict", "Campaign"}  # type + channel-kind (Discord #campaign)
        for t in [r["capture_type"]] + [x for x in r["secondary_types"].split(";") if x]:
            tags.update(_TYPE_TAGS.get(t, []))
        for t in r["tags"].split(";"):
            tags.update(_TAG_TAGS.get(t, []))
        for t in sorted(tags):
            n_tags += con.execute("INSERT OR IGNORE INTO capture_tags (capture_id, tag) VALUES (?,?)", (cid, t)).rowcount
    if not dry_run:
        con.commit()
    if verbose:
        print(f"campaign manifest: {len(matches)} capture(s) linked ({n_vid} video_url set, {n_tags} tag rows added)"
              f"{' [dry run]' if dry_run else ''}; {len(ambiguous)} ambiguous; {len(unmatched)} manifest file(s) not yet ingested")
        for cid, titles in ambiguous:
            print(f"  AMBIGUOUS capture {cid}: {titles}")
    return matches, unmatched, ambiguous
