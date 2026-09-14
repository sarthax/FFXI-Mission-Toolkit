#!/usr/bin/env python3
"""
explore_event.py -- Mission Toolkit GUI, Phase 3 scoped slice (event/dialogue explorer).

One command for "decompile this CSID with real text substituted in" -- the single most manual
step this session (reading raw opcode dumps line by line to find where a menu's option values
actually come from, done by hand for the Vending Box mechanic). This is a thin wrapper: the real
decompiler is xi-events-py (via its own mission_toolkit.py bridge script), which already renders
message ids with dialog.yml's text inline. This script just:
  - auto-generates a zone's events.yml/dialog.yml via mission_toolkit.py if not already cached
  - resolves an entity by name (via npc_names) instead of requiring the raw id
  - cross-checks every message id the decompiler renders against OUR OWN dialog_text index
    (built by build_dialog_index.py via dat-extractor -- a second, independently-extracted
    source from dialog.yml's xi-tinkerer extraction) and flags any disagreement between the two,
    the same two-source-agreement discipline used throughout this toolkit

Usage:
    py -3 explore_event.py Nyzul_Isle "Vending Box" 202
    py -3 explore_event.py Nyzul_Isle 17093430 202
"""
import argparse
import io
import re
import sqlite3
import subprocess
import sys
from pathlib import Path


TOOLS_ROOT = Path(__file__).parent
DB_PATH = TOOLS_ROOT / "ffxi_zone_database.db"
MISSION_REPORTS = TOOLS_ROOT / "mission_reports"
XI_EVENTS_BRIDGE = TOOLS_ROOT / "xi-events-py/decompile_from_mission_toolkit.py"
DEFAULT_FFXI_PATH = "C:/ValhallaXI/SquareEnix/FINAL FANTASY XI"


def resolve_entity(con: sqlite3.Connection, zoneid: int, query: str) -> int | None:
    if query.isdigit():
        return int(query)
    rows = con.execute(
        "SELECT npcid, name FROM npc_names WHERE zoneid = ? AND name LIKE ?",
        (zoneid, f"%{query}%"),
    ).fetchall()
    if not rows:
        return None
    if len(rows) > 1:
        print(f"{len(rows)} name matches -- pass a specific id instead:")
        for npcid, name in rows:
            print(f"  {npcid}  {name!r}")
        return None
    return rows[0][0]


def ensure_export(zone_folder_name: str, ffxi_path: str) -> Path:
    out_dir = MISSION_REPORTS / zone_folder_name
    events_yml = out_dir / "events.yml"
    dialog_yml = out_dir / "dialog.yml"
    if events_yml.exists() and dialog_yml.exists():
        return out_dir
    print(f"[{zone_folder_name}] no cached events/dialog export -- generating via mission_toolkit.py...")
    # mission_toolkit.py's own --out-dir defaults to the RELATIVE path "mission_reports", resolved
    # against the subprocess's cwd -- without cwd=TOOLS_ROOT here, this silently inherited whatever
    # directory the GUI server process itself happened to be started from (e.g. D:\Claude, not
    # D:\Claude\mission_toolkit), writing real generated output to a stray mission_reports/ next to
    # the wrong directory every time. events_yml.exists() below then correctly found nothing at the
    # real path, and the page just rendered "0 events found" with no error -- confirmed live: 12
    # zones' worth of real exports had silently piled up at D:\Claude\mission_reports\ this way.
    result = subprocess.run(
        [sys.executable, str(TOOLS_ROOT / "mission_toolkit.py"), zone_folder_name, "--ffxi-path", ffxi_path],
        capture_output=True, text=True, cwd=str(TOOLS_ROOT),
    )
    if result.returncode != 0:
        raise SystemExit(f"mission_toolkit.py failed:\n{result.stdout}\n{result.stderr}")
    return out_dir


# Matches the decompiler's own inline-comment rendering, e.g. `vm:systemMessage(7465)  -- There...`
# or `npc:dialog(7466, 0, 0)  -- Obtain a temporary item?` -- captures the message id to cross-check.
MESSAGE_ID_RE = re.compile(r"(?:systemMessage|dialog|messageSpecial)\((\d+)")


def cross_check(con: sqlite3.Connection, zoneid: int, decompiled: str) -> list[tuple[int, str, str]]:
    """Returns [(message_id, our_text, note), ...] for every message id referenced, our_text is
    what our own dat-extractor-based index says is really there. note flags disagreement."""
    results = []
    seen = set()
    for m in MESSAGE_ID_RE.finditer(decompiled):
        msg_id = int(m.group(1))
        if msg_id in seen:
            continue
        seen.add(msg_id)
        row = con.execute(
            "SELECT text FROM dialog_text WHERE zoneid = ? AND idx = ?", (zoneid, msg_id)
        ).fetchone()
        our_text = row[0] if row else None
        if our_text is None:
            note = "NOT FOUND in our own dialog_text index"
        else:
            note = "OK"
        results.append((msg_id, our_text, note))
    return results


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("zone", help="Zone folder name under scripts/zones (e.g. Nyzul_Isle)")
    ap.add_argument("entity", help="Entity id, or a name substring to search for in this zone")
    ap.add_argument("csid", type=int, help="Event/CSID number")
    ap.add_argument("--ffxi-path", default=DEFAULT_FFXI_PATH)
    args = ap.parse_args()

    con = sqlite3.connect(DB_PATH)
    zoneid_row = con.execute("SELECT zoneid FROM zones WHERE name = ?", (args.zone.upper(),)).fetchone()
    if not zoneid_row:
        raise SystemExit(f"Could not resolve zoneid for {args.zone}")
    zoneid = zoneid_row[0]

    entity_id = resolve_entity(con, zoneid, args.entity)
    if entity_id is None:
        raise SystemExit(f"Could not resolve entity {args.entity!r} in {args.zone}")

    out_dir = ensure_export(args.zone, args.ffxi_path)

    result = subprocess.run(
        [sys.executable, str(XI_EVENTS_BRIDGE), str(out_dir / "events.yml"), str(entity_id),
         str(args.csid), str(out_dir / "dialog.yml"), str(zoneid)],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        print(result.stdout)
        print(result.stderr)
        raise SystemExit(1)

    decompiled = result.stdout
    print(decompiled)

    print("=" * 70)
    print("Cross-check against our own dialog_text index (dat-extractor, independent of xi-tinkerer):")
    checks = cross_check(con, zoneid, decompiled)
    if not checks:
        print("  (no systemMessage/dialog/messageSpecial calls found to check)")
    for msg_id, our_text, note in checks:
        flag = "  [!]" if note != "OK" else "     "
        preview = (our_text or "")[:80].replace("\n", " ").replace("\r", "")
        print(f"{flag} {msg_id}: {note} -- {preview!r}")

    disasm_path = out_dir / "events_disasm.txt"
    if disasm_path.exists():
        print(f"\nRaw disassembly available for cross-checking: {disasm_path}")

    con.close()


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    main()
