#!/usr/bin/env python3
"""Audit server IDs.lua dialog comments against the configured retail client.

The audit exports the real zone dialog table through xi-tinkerer and compares annotated
IDs.lua text entries against that client-owned evidence. Repository-owned paths are resolved
through ``workbench.runtime.paths`` so this module remains valid from the src layout.
"""
from __future__ import annotations

import argparse
import io
import re
import subprocess
import sys
from pathlib import Path

from workbench.runtime.legacy_settings import get_active_server_root, get_ffxi_install
from workbench.runtime.paths import REPO_ROOT, VENDOR_ROOT

TOPAZ_ROOT = get_active_server_root()
XI_TINKERER_EXE = VENDOR_ROOT / "xi-tinkerer/target/release/xi-tinkerer-cli.exe"
DEFAULT_FFXI_PATH = get_ffxi_install() or "C:/ValhallaXI/SquareEnix/FINAL FANTASY XI"
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
        capture_output=True,
        text=True,
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
            block_lines = []
            i += 1
            while i < len(lines) and (lines[i].startswith("    ") or lines[i] == ""):
                block_lines.append(lines[i].strip())
                i += 1
            entries[int(idx)] = " ".join(line for line in block_lines if line)
            continue
        if val.startswith("'") and val.endswith("'") and len(val) >= 2:
            val = val[1:-1].replace("''", "'")
        entries[int(idx)] = val
        i += 1
    return entries


def normalize(s: str) -> str:
    s = re.sub(r"<[^>]+>", "", s)
    s = re.sub(r"\$\{[^}]+\}", "", s)
    s = re.sub(r"\[[^\]]*/[^\]]*\]", "", s)
    return re.sub(r"[^a-z0-9]", "", s.lower())


def _configure_stdout() -> None:
    stream = getattr(sys.stdout, "buffer", None)
    if stream is not None:
        sys.stdout = io.TextIOWrapper(stream, encoding="utf-8", errors="replace")


def main():
    _configure_stdout()
    ap = argparse.ArgumentParser()
    ap.add_argument("zone_name")
    ap.add_argument("--ffxi-path", default=DEFAULT_FFXI_PATH)
    args = ap.parse_args()

    zoneid = resolve_zoneid(args.zone_name)
    ids_lua_path = TOPAZ_ROOT / "scripts/zones" / args.zone_name / "IDs.lua"
    if not ids_lua_path.exists():
        raise SystemExit(f"No IDs.lua found for {args.zone_name}")

    tmp_dir = REPO_ROOT / "mission_reports" / "_dialog_audit_tmp"
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
