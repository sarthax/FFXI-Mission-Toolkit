#!/usr/bin/env python3
"""
audit_dialog_drift.py -- cross-references each zone's IDs.lua `text` table (where entries have an
inline comment giving the expected real text, e.g. `NAME = 7541, -- "Great, you found..."`)
against that zone's real dialog table (exported fresh from OUR OWN client via xi-tinkerer/FTABLE,
not any external/possibly-different-client-version source), flagging any id whose real text
doesn't match the comment -- the same drift pattern already found and fixed 3+ times this session
(memory: topaz_client_id_offset).

Usage:
    python audit_dialog_drift.py <topaz_zone_name> [--ffxi-path PATH]

Example:
    python audit_dialog_drift.py Mamool_Ja_Training_Grounds
"""
import argparse
import io
import re
import subprocess
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

TOOLS_ROOT = Path(__file__).parent
import settings

TOPAZ_ROOT = settings.get_topaz_root()
XI_TINKERER_EXE = TOOLS_ROOT / "vendor/xi-tinkerer/target/release/xi-tinkerer-cli.exe"
# Settings' ffxi_install_path if configured (registry-autodetected too, see get_ffxi_install()),
# else this literal -- kept only as a documented last-resort example, not assumed to match anyone
# else's real install location.
DEFAULT_FFXI_PATH = settings.get_ffxi_install() or "C:/ValhallaXI/SquareEnix/FINAL FANTASY XI"

# Matches both `NAME = 1234, -- "quoted text"` and `NAME = 1234, -- unquoted text` comment styles.
ENTRY_RE = re.compile(r'^\s*([A-Z_0-9]+)\s*=\s*(\d+),\s*--\s*"?(.+?)"?\s*$', re.M)


def dat_id_for_zone(zoneid: int) -> int:
    if 0 <= zoneid <= 255:
        return 6420 + zoneid
    if 256 <= zoneid <= 511:
        return 85590 + (zoneid - 256)
    raise ValueError(zoneid)


def resolve_zoneid(zone_name: str) -> int:
    zone_lua = (TOPAZ_ROOT / "scripts/globals/zone.lua").read_text(encoding="utf-8", errors="ignore")
    m = re.search(rf"{zone_name.upper()}\s*=\s*(\d+),", zone_lua)
    if not m:
        raise SystemExit(f"Could not resolve zoneid for {zone_name}")
    return int(m.group(1))


def export_dialog(zoneid: int, ffxi_path: str, out_path: Path):
    dat_id = dat_id_for_zone(zoneid)
    result = subprocess.run(
        [str(XI_TINKERER_EXE), "export-dat", ffxi_path, "--dat-id", str(dat_id), str(out_path)],
        capture_output=True, text=True,
    )
    if result.returncode != 0 or not out_path.exists():
        raise SystemExit(f"Failed to export dialog for zoneid {zoneid}: {result.stdout} {result.stderr}")


def parse_real_dialog(path: Path) -> dict:
    lines = path.read_text(encoding="utf-8").split("\n")
    entries = {}
    i = 0
    while i < len(lines):
        m = re.match(r"^  (\d+): (.*)$", lines[i])
        if not m:
            i += 1
            continue
        idx, val = m.groups()
        val = val.strip()
        if val == "|-":
            # Multi-line block scalar: following lines indented further, until dedent.
            block_lines = []
            i += 1
            while i < len(lines) and (lines[i].startswith("    ") or lines[i] == ""):
                block_lines.append(lines[i].strip())
                i += 1
            entries[int(idx)] = " ".join(l for l in block_lines if l)
            continue
        if val.startswith("'") and val.endswith("'") and len(val) >= 2:
            val = val[1:-1].replace("''", "'")
        entries[int(idx)] = val
        i += 1
    return entries


def normalize(s: str) -> str:
    # Strip template placeholders in both notations ("<Player Name>" and "${name-player}" etc.)
    # before comparing -- these differ cosmetically between capture-derived comments and the real
    # client's own ${...} syntax without indicating an actual text drift.
    s = re.sub(r"<[^>]+>", "", s)
    s = re.sub(r"\$\{[^}]+\}", "", s)
    s = re.sub(r"\[[^\]]*/[^\]]*\]", "", s)  # choice-plurality style [singular/plural] blocks
    return re.sub(r"[^a-z0-9]", "", s.lower())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("zone_name")
    ap.add_argument("--ffxi-path", default=DEFAULT_FFXI_PATH)
    args = ap.parse_args()

    zoneid = resolve_zoneid(args.zone_name)
    ids_lua_path = TOPAZ_ROOT / "scripts/zones" / args.zone_name / "IDs.lua"
    if not ids_lua_path.exists():
        raise SystemExit(f"No IDs.lua found for {args.zone_name}")

    tmp_dir = TOOLS_ROOT / "mission_reports" / "_dialog_audit_tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    dialog_path = tmp_dir / f"dialog_{zoneid}.yml"
    print(f"Exporting real dialog for {args.zone_name} (zoneid {zoneid})...")
    export_dialog(zoneid, args.ffxi_path, dialog_path)
    real_dialog = parse_real_dialog(dialog_path)
    print(f"  {len(real_dialog)} real dialog entries loaded")

    ids_text = ids_lua_path.read_text(encoding="utf-8", errors="ignore")
    entries = ENTRY_RE.findall(ids_text)
    print(f"  {len(entries)} annotated text ids found in IDs.lua\n")

    matches, mismatches, missing = 0, [], []
    for name, num_str, expected in entries:
        num = int(num_str)
        real = real_dialog.get(num)
        if real is None:
            missing.append((name, num, expected))
            continue
        if normalize(expected) in normalize(real) or normalize(real) in normalize(expected):
            matches += 1
        else:
            mismatches.append((name, num, expected, real))

    print(f"MATCH: {matches}")
    print(f"MISMATCH: {len(mismatches)}")
    for name, num, expected, real in mismatches:
        print(f"  [{num}] {name}")
        print(f"    expected: {expected[:100]}")
        print(f"    real:     {real[:100]}")
    print(f"NO REAL ENTRY AT THAT ID: {len(missing)}")
    for name, num, expected in missing:
        print(f"  [{num}] {name} -- expected: {expected[:80]}")


if __name__ == "__main__":
    main()
