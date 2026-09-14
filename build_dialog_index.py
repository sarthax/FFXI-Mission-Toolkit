#!/usr/bin/env python3
"""
build_dialog_index.py -- Mission Toolkit GUI, Phase 1 scoped slice.

Builds a persisted, searchable index of every zone's real client dialog table (via
dat-extractor --extract-id, using the real 6420+zoneid / 85590+(zoneid-256) file-id formula
confirmed against our own client this session -- see [[ffxi_mission_toolkit]] /
TOOLING_OVERVIEW.md), then cross-references it against every zone's IDs.lua `text{}` block to
flag drift -- the automated version of the Nyzul Isle / Whitegate audits done by hand.

This does NOT replace audit_dialog_drift.py (which only checks ids that already carry an
inline `-- "real text"` comment, via xi-tinkerer). This tool indexes the FULL real dialog table
per zone (every id, not just annotated ones) into ffxi_zone_database.db, so:
  - every IDs.lua constant gets checked, commented or not
  - the raw text is kept for later full-text search (Phase 1's other stated goal)
  - re-running is a cache refresh, not a fresh per-id extraction

Usage:
    py -3 build_dialog_index.py --zone Nyzul_Isle          # index + audit one zone
    py -3 build_dialog_index.py --all                       # index + audit every zone with an IDs.lua
    py -3 build_dialog_index.py --zone Nyzul_Isle --search "vending"   # FTS search after indexing
"""
import argparse
import io
import json
import re
import sqlite3
import subprocess
import sys
from pathlib import Path

import settings

TOOLS_ROOT = Path(__file__).parent
TOPAZ_ROOT = settings.get_topaz_root()
DB_PATH = TOOLS_ROOT / "ffxi_zone_database.db"
DAT_EXTRACTOR_EXE = TOOLS_ROOT / "vendor/dat-extractor/bin/Debug/net9.0/dat-extractor.exe"
DEFAULT_FFXI_PATH = "C:/ValhallaXI/SquareEnix/FINAL FANTASY XI"

# NAME = 1234[, -- optional comment] -- matches every entry in a zone's IDs.lua text{} block,
# not just ones with an inline real-text comment (audit_dialog_drift.py's ENTRY_RE requires one).
TEXT_ENTRY_RE = re.compile(r'^\s*([A-Z_][A-Z0-9_]*)\s*=\s*(\d+)\s*,', re.M)


def dat_id_for_zone(zoneid: int) -> int:
    """Real POLUtils MassExtractor formula, confirmed against our client this session
    (6420+77=6497 -> Nyzul Isle's real table, 7692 entries exact match)."""
    if 0 <= zoneid <= 255:
        return 6420 + zoneid
    if 256 <= zoneid <= 511:
        return 85590 + (zoneid - 256)
    raise ValueError(f"zoneid {zoneid} out of known formula range")


def init_db(con: sqlite3.Connection):
    con.executescript("""
        CREATE TABLE IF NOT EXISTS dialog_text (
            zoneid INTEGER,
            idx INTEGER,
            text TEXT,
            PRIMARY KEY (zoneid, idx)
        );
        -- Deliberately NOT an external-content table (content='dialog_text'): that mode needs
        -- matching AFTER DELETE / AFTER UPDATE triggers to keep the shadow index in sync, and a
        -- missing delete trigger left this exact table corrupted after a single --force re-run
        -- (rowids got reused by fresh inserts while stale FTS shadow rows from the deleted rows
        -- stuck around, and MATCH + a plain zoneid filter returned nothing at all as a result).
        -- Standalone, self-contained FTS5 table instead -- indexed and rebuilt explicitly per
        -- zone in code, no trigger synchronization to get wrong.
        CREATE VIRTUAL TABLE IF NOT EXISTS dialog_text_fts USING fts5(
            text, zoneid UNINDEXED, idx UNINDEXED
        );
        CREATE TABLE IF NOT EXISTS dialog_drift_report (
            zoneid INTEGER,
            zone_name TEXT,
            constant_name TEXT,
            wired_id INTEGER,
            real_text TEXT,
            has_comment INTEGER,
            commented_text TEXT,
            status TEXT,       -- 'match', 'mismatch', 'no_real_entry', 'unannotated'
            zone_content_tags TEXT,  -- distinct npc_list content_tag values present anywhere in
                                     -- this zone (comma-joined), e.g. 'TOAU,SOA' -- a zone-level
                                     -- heads-up, not a per-id property (dialog-text ids are a
                                     -- different id space from npc_list rows and have no
                                     -- content_tag of their own). A non-empty value here is a
                                     -- reminder that this zone hosts other tagged content, same
                                     -- caution as lookup_entity.py's -- see that tool's own note
                                     -- and the real Nyzul Isle Moogle/prop sweep this session.
            checked_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
    """)
    # Migrate an existing table from before zone_content_tags existed.
    cols = [r[1] for r in con.execute("PRAGMA table_info(dialog_drift_report)").fetchall()]
    if "zone_content_tags" not in cols:
        con.execute("ALTER TABLE dialog_drift_report ADD COLUMN zone_content_tags TEXT")
    con.commit()


def get_zone_content_tags(con: sqlite3.Connection, zoneid: int) -> str:
    """Distinct real content_tag values present anywhere in this zone's npc_names (built by
    build_npc_index.py) -- empty string if that index hasn't been built yet for this zone, or the
    zone genuinely has no tagged content."""
    rows = con.execute(
        "SELECT DISTINCT content_tag FROM npc_names WHERE zoneid = ? AND content_tag IS NOT NULL",
        (zoneid,),
    ).fetchall()
    return ",".join(sorted(r[0] for r in rows))


def resolve_zoneid(con: sqlite3.Connection, zone_folder_name: str) -> int | None:
    zone_constant = zone_folder_name.upper()
    row = con.execute("SELECT zoneid FROM zones WHERE name = ?", (zone_constant,)).fetchone()
    return row[0] if row else None


def extract_dialog(zoneid: int, ffxi_path: str) -> list[dict] | None:
    """Runs dat-extractor --extract-id for this zone's real dialog table file id, returns the
    parsed [{"Index":N,"Text":"..."}] entries, or None if the file doesn't resolve/parse."""
    dat_id = dat_id_for_zone(zoneid)
    out_path = TOOLS_ROOT / "mission_reports" / "_dialog_index_tmp" / f"{dat_id}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        [str(DAT_EXTRACTOR_EXE), "--extract-id", ffxi_path, str(dat_id), str(out_path)],
        capture_output=True, text=True,
    )
    if result.returncode != 0 or not out_path.exists():
        print(f"    [!] extract-id {dat_id} failed: {result.stdout.strip()} {result.stderr.strip()}")
        return None
    with open(out_path, encoding="utf-8-sig") as f:
        return json.load(f)


def index_zone_dialog(con: sqlite3.Connection, zoneid: int, ffxi_path: str, force: bool = False) -> int:
    """Populates dialog_text for this zone from the real client dat, unless already cached."""
    if not force:
        existing = con.execute("SELECT COUNT(*) FROM dialog_text WHERE zoneid = ?", (zoneid,)).fetchone()[0]
        if existing:
            return existing
    entries = extract_dialog(zoneid, ffxi_path)
    if entries is None:
        return 0
    con.execute("DELETE FROM dialog_text WHERE zoneid = ?", (zoneid,))
    con.execute("DELETE FROM dialog_text_fts WHERE zoneid = ?", (zoneid,))
    con.executemany(
        "INSERT INTO dialog_text (zoneid, idx, text) VALUES (?, ?, ?)",
        [(zoneid, e["Index"], e["Text"]) for e in entries],
    )
    con.executemany(
        "INSERT INTO dialog_text_fts (zoneid, idx, text) VALUES (?, ?, ?)",
        [(zoneid, e["Index"], e["Text"]) for e in entries],
    )
    con.commit()
    return len(entries)


# Matches audit_dialog_drift.py's parser: `NAME = 1234, -- "real text"` or `-- real text` (unquoted).
# Deliberately [ \t]* (not \s*) between the comma and `--` -- \s matches newlines too, which let
# this bridge a bare `NAME = NUM,` line into an unrelated standalone `--` comment on the *next*
# line (found live: PATHOS_RECEIVED = 7346, has no inline comment at all, but this bug attached
# the following line's documentation comment to it as if it were real wired text).
COMMENT_ENTRY_RE = re.compile(r'^[ \t]*([A-Z_][A-Z0-9_]*)[ \t]*=[ \t]*(\d+),[ \t]*--[ \t]*"?(.+?)"?[ \t]*$', re.M)


def normalize(s: str) -> str:
    s = re.sub(r"<[^>]+>", "", s)
    s = re.sub(r"\$\{[^}]+\}", "", s)
    s = re.sub(r"\[[^\]]*/[^\]]*\]", "", s)
    # The real dat's own placeholder tokens (≺Numeric Parameter 0≻, ≺Possible Special Code: 01≻,
    # ≺Prompt≻, ≺Selection Dialog≻, ≺Singular/Plural Choice (Parameter 0)≻, etc.) vs. the wired
    # comment's own shorthand (<number>, <item>) -- both mean "there's a placeholder here", so
    # strip both rather than let the differing syntax read as a text mismatch.
    s = re.sub(r"≺[^≻]*≻", "", s)
    return re.sub(r"[^a-z0-9]", "", s.lower())


def audit_zone(con: sqlite3.Connection, zoneid: int, zone_name: str, ids_lua_path: Path) -> dict:
    """Cross-references every id in this zone's IDs.lua text{} block against the indexed real
    dialog table. Returns a summary dict; writes per-id rows into dialog_drift_report."""
    ids_text = ids_lua_path.read_text(encoding="utf-8", errors="ignore")

    # Scope to the text{} block only, not the whole file (mob{}/npc{} tables use the same
    # NAME = NUMBER shape and would otherwise get misread as dialog ids).
    block_match = re.search(r"\btext\s*=\s*\{(.*?)\n\s*\},", ids_text, re.S)
    if not block_match:
        return {"annotated": 0, "unannotated": 0, "match": 0, "mismatch": 0, "no_real_entry": 0}
    block = block_match.group(1)

    commented = {name: (int(num), txt) for name, num, txt in COMMENT_ENTRY_RE.findall(block)}
    all_entries = {name: int(num) for name, num in TEXT_ENTRY_RE.findall(block)}

    con.execute("DELETE FROM dialog_drift_report WHERE zoneid = ?", (zoneid,))

    summary = {"annotated": 0, "unannotated": 0, "match": 0, "mismatch": 0, "no_real_entry": 0}
    rows = []
    for name, wired_id in all_entries.items():
        real_row = con.execute(
            "SELECT text FROM dialog_text WHERE zoneid = ? AND idx = ?", (zoneid, wired_id)
        ).fetchone()
        real_text = real_row[0] if real_row else None
        has_comment = name in commented
        commented_text = commented[name][1] if has_comment else None

        if real_text is None:
            status = "no_real_entry"
            summary["no_real_entry"] += 1
        elif not has_comment:
            status = "unannotated"
            summary["unannotated"] += 1
        else:
            summary["annotated"] += 1
            if normalize(commented_text) in normalize(real_text) or normalize(real_text) in normalize(commented_text):
                status = "match"
                summary["match"] += 1
            else:
                status = "mismatch"
                summary["mismatch"] += 1

        rows.append((zoneid, zone_name, name, wired_id, real_text, int(has_comment), commented_text, status))

    zone_content_tags = get_zone_content_tags(con, zoneid)
    con.executemany(
        """INSERT INTO dialog_drift_report
           (zoneid, zone_name, constant_name, wired_id, real_text, has_comment, commented_text, status, zone_content_tags)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        [row + (zone_content_tags,) for row in rows],
    )
    con.commit()
    summary["zone_content_tags"] = zone_content_tags
    return summary


def print_zone_report(con: sqlite3.Connection, zoneid: int, zone_name: str, entry_count: int, summary: dict, quiet: bool = False):
    if quiet:
        print(f"  {entry_count} entries -- IDs.lua: {summary['annotated']} annotated, "
              f"{summary['unannotated']} unannotated, {summary['no_real_entry']} no_real_entry -- "
              f"annotated check: {summary['match']} match, {summary['mismatch']} mismatch")
        return
    print(f"  {entry_count} real dialog entries indexed")
    if summary.get("zone_content_tags"):
        print(f"  [!] zone hosts other tagged content ({summary['zone_content_tags']}) -- see "
              f"lookup_entity.py's caution note before assuming any entity here is Assault-owned")
    print(f"  IDs.lua: {summary['annotated']} annotated, {summary['unannotated']} unannotated, "
          f"{summary['no_real_entry']} point at a nonexistent real id")
    print(f"  Annotated check: {summary['match']} match, {summary['mismatch']} MISMATCH")
    if summary["mismatch"]:
        rows = con.execute(
            """SELECT constant_name, wired_id, commented_text, real_text FROM dialog_drift_report
               WHERE zoneid = ? AND status = 'mismatch' ORDER BY wired_id""",
            (zoneid,),
        ).fetchall()
        for name, wired_id, commented_text, real_text in rows:
            print(f"    [{wired_id}] {name}")
            print(f"      wired comment: {commented_text[:90]}")
            print(f"      real text:     {real_text[:90]}")
    if summary["no_real_entry"]:
        rows = con.execute(
            """SELECT constant_name, wired_id FROM dialog_drift_report
               WHERE zoneid = ? AND status = 'no_real_entry' ORDER BY wired_id""",
            (zoneid,),
        ).fetchall()
        for name, wired_id in rows:
            print(f"    [{wired_id}] {name} -- no real dialog entry at this id")


def process_zone(con: sqlite3.Connection, zone_folder_name: str, ffxi_path: str, force: bool, quiet: bool = False):
    ids_lua_path = TOPAZ_ROOT / "scripts/zones" / zone_folder_name / "IDs.lua"
    if not ids_lua_path.exists():
        print(f"[{zone_folder_name}] no IDs.lua, skipping")
        return
    zoneid = resolve_zoneid(con, zone_folder_name)
    if zoneid is None:
        print(f"[{zone_folder_name}] could not resolve zoneid (not in zones table), skipping")
        return
    zone_name = zone_folder_name.upper()
    print(f"[{zone_folder_name}] zoneid={zoneid}, dat file={dat_id_for_zone(zoneid)}")
    entry_count = index_zone_dialog(con, zoneid, ffxi_path, force=force)
    if entry_count == 0:
        print("  no real dialog table resolved for this zone -- skipping audit")
        return
    summary = audit_zone(con, zoneid, zone_name, ids_lua_path)
    print_zone_report(con, zoneid, zone_name, entry_count, summary, quiet=quiet)


def search(con: sqlite3.Connection, query: str, zoneid: int | None = None):
    sql = "SELECT zoneid, idx, text FROM dialog_text_fts WHERE dialog_text_fts MATCH ?"
    params = [query]
    if zoneid is not None:
        sql += " AND zoneid = ?"
        params.append(zoneid)
    sql += " LIMIT 50"
    rows = con.execute(sql, params).fetchall()
    if not rows:
        print("  no matches")
        return
    for zid, idx, text in rows:
        zname = con.execute("SELECT name FROM zones WHERE zoneid = ?", (zid,)).fetchone()
        zname = zname[0] if zname else "?"
        print(f"  [{zname} #{idx}] {text[:120]!r}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--zone", help="Zone folder name under scripts/zones (e.g. Nyzul_Isle)")
    ap.add_argument("--all", action="store_true", help="Process every zone with an IDs.lua")
    ap.add_argument("--ffxi-path", default=DEFAULT_FFXI_PATH)
    ap.add_argument("--force", action="store_true", help="Re-extract even if already cached")
    ap.add_argument("--search", help="FTS search across the indexed dialog text (after any indexing)")
    ap.add_argument("--quiet", action="store_true",
                     help="Condensed one-line-per-zone summary (suppresses per-mismatch text dumps); "
                          "for automated/setup use, full audit detail is still the default")
    args = ap.parse_args()

    if not args.zone and not args.all and not args.search:
        ap.error("Specify --zone NAME, --all, or --search QUERY")

    con = sqlite3.connect(DB_PATH)
    init_db(con)

    if args.zone:
        process_zone(con, args.zone, args.ffxi_path, args.force, quiet=args.quiet)
    elif args.all:
        zones_dir = TOPAZ_ROOT / "scripts/zones" if TOPAZ_ROOT else None
        if not zones_dir or not zones_dir.is_dir():
            print("[build_dialog_index] --all needs a real Topaz checkout (scripts/zones/*/IDs.lua "
                  "supplies the per-zone dialog-audit worklist; nothing else in this toolkit currently "
                  f"provides an equivalent). Configured topaz_server_path: {TOPAZ_ROOT}")
            con.close()
            return
        for zone_dir in sorted(zones_dir.iterdir()):
            if (zone_dir / "IDs.lua").exists():
                process_zone(con, zone_dir.name, args.ffxi_path, args.force, quiet=args.quiet)

    if args.search:
        zoneid = resolve_zoneid(con, args.zone) if args.zone else None
        print(f"\nSearch results for {args.search!r}" + (f" in {args.zone}" if args.zone else " (all zones)") + ":")
        search(con, args.search, zoneid)

    con.close()


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    main()
