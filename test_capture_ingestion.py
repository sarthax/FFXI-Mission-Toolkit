#!/usr/bin/env python3
"""
test_capture_ingestion.py -- regression test against real capturer-tool folder layouts, so a fix
for one capturer's real quirk (e.g. an optional capturer-name subfolder) never silently re-breaks
another capturer's layout the way npclogger/logs/ regressed relative to npclogger/tables/ and
npclogger/database/ before 2026-09-08 -- those three patterns were meant to be handled identically
but only two of them actually got the fix when it was made.

Fixtures under test_fixtures/captures/ are REAL capture bundles (trimmed of nothing but their
original outer folder name), not synthesized -- each represents one real capturer tool's actual
on-disk layout:
    foxmulder_bhaflau_remnants/   -- from a real Bhaflau Remnants.zip capture, "Foxmulder" capturer
    tacocat_leujaoam_sanctum/     -- from a real Leujaoam Sanctum capture, "Tacocat" capturer,
                                      confirmed to nest several files one level shallower than the
                                      Foxmulder layout (no capturer subfolder under npclogger/logs/)
                                      and to additionally write whole-session combined files
                                      (eventview/raw.log, packetviewer/full.log, etc.) alongside
                                      the per-zone/per-opcode files Foxmulder's layout also has.
    thris_ilrusi_atoll/           -- from a real Ilrusi Atoll capture, "Thris" capturer -- a
                                      titlecase CapLog/ folder (not lowercase caplog/) whose real
                                      content is a genuinely different [EView] packet-block shape
                                      (short time-only header + a separate comma-separated field
                                      line) from the other two fixtures' [Tag] single-line shape,
                                      confirmed real and consistent across 88 sampled real captures.

Each fixture has a KNOWN_GAPS allowlist below for files that are expected to fail. Any failure not
on that list is a real regression and fails this script.

Usage:
    py -3 test_capture_ingestion.py
"""
import sqlite3
import sys
from pathlib import Path

import build_capture_index as bci

TOOLS_ROOT = Path(__file__).parent
FIXTURES_DIR = TOOLS_ROOT / "test_fixtures" / "captures"

# Per-fixture allowlist of relative-path regex fragments (plain substring match against the
# reported filename) that are known, tracked, non-regression gaps -- not "this test is broken",
# a real missing parser someone can grep this file to find and fix later.
KNOWN_GAPS = {
    "foxmulder_bhaflau_remnants": [],
    # caplog/ was here until 2026-09-08 -- now has a real parser (ingest_caplog), removed from
    # this allowlist so a future regression there gets caught like any other real failure.
    "tacocat_leujaoam_sanctum": [],
    # A third real capturer variant ("Thris") -- titlecase CapLog/ folder with a genuinely
    # different [EView] packet-block format, added 2026-09-08 alongside its parser. No known gaps.
    "thris_ilrusi_atoll": [],
}


def run_fixture(name: str, root: Path) -> bool:
    if not root.is_dir():
        print(f"[{name}] SKIPPED -- fixture directory missing: {root}")
        return True

    con = sqlite3.connect(":memory:")
    bci.init_db(con)
    src = bci.Source(root)
    file_results: list[dict] = []
    counts = bci.ingest_from_source(con, 1, src, subroot=None, file_results=file_results)

    gaps = KNOWN_GAPS.get(name, [])
    unexpected_failures = [
        r for r in file_results
        if r["error"] is not None and not any(g in r["filename"] for g in gaps)
    ]
    known_gap_hits = [
        r for r in file_results
        if r["error"] is not None and any(g in r["filename"] for g in gaps)
    ]

    print(f"[{name}] {len(file_results)} file(s) seen, counts={counts}")
    if known_gap_hits:
        print(f"  {len(known_gap_hits)} known/tracked gap(s) (not a regression):")
        for r in known_gap_hits:
            print(f"    - {r['filename']}")

    if unexpected_failures:
        print(f"  ❌ {len(unexpected_failures)} UNEXPECTED failure(s) -- real regression:")
        for r in unexpected_failures:
            print(f"    - {r['filename']}: {r['error']}")
        return False

    print("  ✓ no unexpected failures")
    return True


def main():
    ok = True
    for name in sorted(KNOWN_GAPS):
        ok = run_fixture(name, FIXTURES_DIR / name) and ok
        print()

    if not ok:
        print("FAILED -- one or more fixtures regressed. See above.")
        sys.exit(1)
    print("All capture-ingestion fixtures passed.")


if __name__ == "__main__":
    main()
