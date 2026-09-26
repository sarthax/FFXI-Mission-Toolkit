"""Cross-zone dialog drift overview with per-zone constant-offset detection (read-only).

Reads the existing `dialog_drift_report` (wired id vs. commented text) and `dialog_text` (real client
dialog, per zone) tables built by build_dialog_index.py. For every zone with mismatches it asks: is
there one offset k such that real_dialog[wired_id + k] matches the commented text for many of the
mismatched ids? If so, the drift is a systematic id shift (client-generation offset) rather than
scattered wrong ids, and k is the suggested correction.

This is INFERRED evidence: text normalization matches loosely, and short/generic lines can match at
several offsets, so a zone is only reported as an offset when one k explains a clear majority.
Nothing is written; ids are never changed by this module.
"""
from __future__ import annotations

import re
import sqlite3
from collections import Counter
from pathlib import Path

MAX_SHIFT = 64
MIN_TEXT_LEN = 8          # ignore very short comments; they match by chance at many offsets
MAJORITY = 0.6            # share of usable mismatches one offset must explain
MIN_EVIDENCE = 3          # ...and at least this many rows agree

_CACHE: dict[tuple[str, float], list[dict]] = {}


def normalize(s: str) -> str:
    """Same rules as audit_dialog_drift.normalize so results agree with the CLI audit."""
    s = re.sub(r"[<≺][^>≻]*[>≻]", "", s or "")
    s = re.sub(r"\$\{[^}]+\}", "", s)
    s = re.sub(r"\[[^\]]*/[^\]]*\]", "", s)
    return re.sub(r"[^a-z0-9]", "", s.lower())


def _texts_match(a: str, b: str) -> bool:
    return bool(a) and bool(b) and (a in b or b in a)


def detect_offset(mismatches: list[tuple[int, str]], dialog: dict[int, str]) -> dict:
    """mismatches: [(wired_id, commented_text)]; dialog: idx -> normalized real text."""
    votes: Counter = Counter()
    usable = 0
    for wired, commented in mismatches:
        c = normalize(commented)
        if len(c) < MIN_TEXT_LEN:
            continue
        usable += 1
        hits = [k for k in range(-MAX_SHIFT, MAX_SHIFT + 1)
                if k != 0 and (wired + k) in dialog and _texts_match(c, dialog[wired + k])]
        for k in hits:
            votes[k] += 1
    if not usable or not votes:
        return {"offset": None, "explained": 0, "usable": usable, "share": 0.0}
    k, n = votes.most_common(1)[0]
    share = n / usable
    ok = share >= MAJORITY and n >= MIN_EVIDENCE
    return {"offset": k if ok else None, "best_guess": k, "explained": n, "usable": usable, "share": round(share, 3)}


def overview(db_path: Path) -> list[dict]:
    db_path = Path(db_path)
    key = (str(db_path), db_path.stat().st_mtime)
    if key in _CACHE:
        return _CACHE[key]
    con = sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro", uri=True)
    try:
        zones = con.execute(
            "SELECT zoneid, zone_name, "
            "SUM(status='match'), SUM(status='mismatch'), SUM(status='no_real_entry'), SUM(status='unannotated') "
            "FROM dialog_drift_report GROUP BY zoneid, zone_name ORDER BY zone_name").fetchall()
        out = []
        for zoneid, name, match, mism, missing, unann in zones:
            row = {"zoneid": zoneid, "zone_name": name, "match": match, "mismatch": mism,
                   "no_real_entry": missing, "unannotated": unann,
                   "offset": None, "explained": 0, "usable": 0, "share": 0.0, "best_guess": None}
            if mism:
                bad = con.execute(
                    "SELECT wired_id, commented_text FROM dialog_drift_report "
                    "WHERE zoneid=? AND status='mismatch' AND commented_text IS NOT NULL", (zoneid,)).fetchall()
                dialog = {i: normalize(t) for i, t in
                          con.execute("SELECT idx, text FROM dialog_text WHERE zoneid=?", (zoneid,))}
                row.update(detect_offset(bad, dialog))
            out.append(row)
    finally:
        con.close()
    _CACHE.clear()
    _CACHE[key] = out
    return out


def summary(rows: list[dict]) -> dict:
    with_off = [r for r in rows if r["offset"] is not None]
    return {"zones": len(rows), "zones_with_mismatch": sum(1 for r in rows if r["mismatch"]),
            "zones_systematic": len(with_off),
            "offset_histogram": dict(Counter(r["offset"] for r in with_off).most_common())}
