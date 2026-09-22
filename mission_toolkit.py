#!/usr/bin/env python3
"""
mission_toolkit.py -- one-stop FFXI zone/mission data puller.

Chains together every FFXI dat tool we've found so far, each of which only
covers one piece of the puzzle:

  1. Topaz's own scripts/globals/zone.lua + sql/zone_settings.sql
       -> resolve a topaz zone name/id pair
  2. AltanaViewer's zones.csv (FFXI-Tools/ffxi/reference/AltanaViewer_zones.csv)
       -> the zone's real 3D geometry dat id (for mapViewer / Noesis)
  3. dat-extractor's `--resolve` (FFXI-Tools/dat-extractor), which reads the real
     client FTABLE.DAT/VTABLE.DAT for ground-truth dat-id -> physical ROM path
       -> resolves the zone's events/dialog/entities dat ids to real files
  4. xi-tinkerer-py (FFXI-Tools/xi-tinkerer-py, PyO3 bindings onto xi-tinkerer's
     real Rust `dats` crate) -- parses those DAT files DIRECTLY in-process
       -> native dicts, no subprocess/temp-YAML round trip
  5. XiEvents' documented opcode table (FFXI-Tools/XiEvents/opcode_table.json)
       -> disassembles every event's byte code, flagging interesting opcodes

2026-08-31: previously shelled out to a separately-built `xi-tinkerer-cli.exe`
per category and round-tripped through a YAML file that then had to be
re-parsed with regex (a real source of bugs -- e.g. unquoted hex byte_code in
that YAML got silently auto-parsed as a Python int by PyYAML, not a string,
which every downstream consumer had to work around). Native xi-tinkerer-py
gives the exact same structure (`{"blocks": [{"entity_id", "events", "data"}]}`
for events, `{"entries": {...}}` for dialog, `{"names": {...}}` for entities)
directly as real Python objects -- no serialization round trip, no regex, no
int/str byte_code ambiguity. See ffxi_event_tooling_reference memory for the
full validation writeup. The on-disk `events.yml`/`dialog.yml`/`entities.yml`
output format is UNCHANGED (same shape downstream tools already parse --
`decompile_from_mission_toolkit.py`, `smart_disassemble.py`) -- only the
internal extraction mechanism changed. Real per-recommendation caveat: check
[[ffxi_event_tooling_reference]] first for whether FFXI-EventsDump already has
what you need pre-generated before running this at all.

Usage:
    python mission_toolkit.py <topaz_zone_name_or_id> [--out-dir DIR] [--ffxi-path PATH]

Example:
    python mission_toolkit.py Mamool_Ja_Training_Grounds
    python mission_toolkit.py 66

Output: a folder under --out-dir (default: ./mission_reports/<zone_name>/) containing
    geometry.txt   -- resolved mapid + ROM path for the zone's 3D geometry
    events.yml     -- full events DAT export (all NPCs/entities in the zone)
    events_disasm.txt -- disassembly of every event's byte code, flagging interesting opcodes
    dialog.yml     -- dialog text DAT export (zones 0-255/256-511 only; best-effort)
    entities.yml   -- entity names DAT export (best-effort)
    SUMMARY.md     -- human-readable index of everything above

This does NOT replace investigation -- it just gets the raw, verified material onto disk fast
so a session can start from real data instead of re-deriving ids by hand every time.
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

import yaml
from xi_tinkerer import parse_dialog, parse_entity_names, parse_events

import settings

TOOLS_ROOT = Path(__file__).parent
TOPAZ_ROOT = settings.get_topaz_root()
DEFAULT_FFXI_PATH = settings.get_ffxi_install() or "C:/ValhallaXI/SquareEnix/FINAL FANTASY XI"
DAT_EXTRACTOR_DLL = TOOLS_ROOT / "vendor/dat-extractor/bin/Debug/net9.0/dat-extractor.dll"
ALTANA_ZONES_CSV = TOOLS_ROOT / "vendor/ffxi/reference/AltanaViewer_zones.csv"
OPCODE_TABLE = json.loads((TOOLS_ROOT / "vendor/XiEvents/opcode_table.json").read_text())
SIZES = {int(k): v for k, v in OPCODE_TABLE["sizes"].items()}
NAMES = {int(k): v for k, v in OPCODE_TABLE["names"].items()}

FLAGGED_OPCODES = {
    0x46: "CodeDEFCAMERA -- enables/disables player camera control, hides menus for cutscenes",
    0x6C: "CodeTRANSPAR -- fades an entity's color/alpha in and out over time",
}

# category -> which native xi_tinkerer parser handles that dat type
PARSERS = {
    "events": parse_events,
    "dialog": parse_dialog,
    "entities": parse_entity_names,
}


def normalize(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


def resolve_topaz_zone(query: str) -> tuple[int, str]:
    """Returns (zoneid, zone_name) from either a numeric zoneid or a zone.lua constant name."""
    zone_lua = (TOPAZ_ROOT / "scripts/globals/zone.lua").read_text(encoding="utf-8", errors="ignore")

    if query.isdigit():
        zoneid = int(query)
        m = re.search(rf"(\w+)\s*=\s*{zoneid},", zone_lua)
        name = m.group(1) if m else f"ZONE_{zoneid}"
        return zoneid, name

    # Try matching against the zone.lua constant name (e.g. Mamool_Ja_Training_Grounds).
    const_name = query.upper()
    m = re.search(rf"{re.escape(const_name)}\s*=\s*(\d+),", zone_lua)
    if m:
        return int(m.group(1)), query

    # Fall back to fuzzy matching against zone_settings.sql's display name column.
    settings_sql = (TOPAZ_ROOT / "sql/zone_settings.sql").read_text(encoding="utf-8", errors="ignore")
    target = normalize(query)
    for row_match in re.finditer(r"VALUES \((\d+),\d+,'[^']*',\d+,'([^']+)'", settings_sql):
        zid, zname = row_match.groups()
        if normalize(zname) == target:
            return int(zid), zname

    raise SystemExit(f"Could not resolve topaz zone '{query}' via zone.lua or zone_settings.sql.")


def resolve_geometry_mapid(zone_name: str) -> tuple[int, str] | None:
    """Looks up the zone's real 3D geometry dat id from the AltanaViewer zones.csv."""
    target = normalize(zone_name.replace("_", " "))
    with open(ALTANA_ZONES_CSV, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("@") or "," not in line:
                continue
            path_part, csv_name = line.split(",", 1)
            if normalize(csv_name) != target:
                continue
            parts = path_part.split("/")
            if len(parts) == 2:
                dir_, file_ = int(parts[0]), int(parts[1])
                sub = 0
            elif len(parts) == 3:
                dir_, sub, file_ = int(parts[0]), int(parts[1]), int(parts[2])
            else:
                continue
            mapid = dir_ * 1_000_000 + sub * 1000 + file_
            rom_path = f"ROM{'' if dir_ == 0 else dir_}\\{sub}\\{file_}.DAT"
            return mapid, rom_path
    return None


def dat_id_for_zone(zoneid: int, category: str) -> int | None:
    """Reproduces xi-tinkerer's crates/dats/src/id_mapping.rs DatIdMapping offsets."""
    offsets_0_255 = {"zone_data": 100, "events": 5820, "dialog": 6420, "entities": 6720}
    offsets_256_511 = {"zone_data": 83891, "events": 84991, "dialog": 85590, "entities": 86491}

    if category not in offsets_0_255:
        return None
    if 0 <= zoneid <= 255:
        return offsets_0_255[category] + zoneid
    if 256 <= zoneid <= 511:
        return offsets_256_511[category] + (zoneid - 256)
    return None


def resolve_rom_paths(ffxi_path: str, dat_ids: list[int]) -> dict[int, str]:
    """Resolves dat-ids to real physical ROM paths in one batched dat-extractor call (it accepts
    multiple file numbers per invocation) -- real FTABLE.DAT/VTABLE.DAT lookup, ground truth.
    xi-tinkerer-py has no path-resolution helper of its own (only raw-file parsers), so this one
    piece still shells out -- it's a fast, single lookup, not the expensive part (that was always
    the actual DAT parsing, which is now native).
    """
    if not dat_ids:
        return {}
    result = subprocess.run(
        ["dotnet", "exec", str(DAT_EXTRACTOR_DLL), "--resolve", ffxi_path, *[str(d) for d in dat_ids]],
        capture_output=True,
        text=True,
    )
    paths = {}
    for line in result.stdout.splitlines():
        parts = line.split("\t")
        if len(parts) >= 2 and parts[0].isdigit():
            paths[int(parts[0])] = parts[1]
    return paths


def _int_keyed(entries: dict) -> dict:
    """xi-tinkerer-py's parse_dialog returns string keys ('0', '1', ...) -- the on-disk YAML
    convention every downstream consumer this session was built around (smart_disassemble.py,
    decompile_from_mission_toolkit.py) expects int keys (matching how the old CLI+YAML round trip
    happened to serialize them). Converting once here keeps every existing consumer working
    unchanged."""
    out = {}
    for k, v in entries.items():
        try:
            out[int(k)] = v
        except (TypeError, ValueError):
            out[k] = v
    return out


def export_dat_native(category: str, rom_path: str, out_path: Path) -> bool:
    """Parses a DAT file natively via xi-tinkerer-py and writes it to disk in the SAME on-disk
    shape the old CLI-based export produced, so nothing downstream needs to change."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    parser = PARSERS[category]
    try:
        data = parser(rom_path)
    except Exception as e:
        print(f"  ! native parse failed for {category} ({rom_path}): {e}")
        return False

    if category == "dialog" and "entries" in data:
        data = {**data, "entries": _int_keyed(data["entries"])}

    with open(out_path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, allow_unicode=True, sort_keys=False, default_flow_style=False)
    return True


def disassemble_events_native(events_data: dict, out_path: Path) -> int:
    """Same shallow opcode-table disassembly as before, now reading the native dict directly --
    no regex re-parsing of serialized YAML text, no byte_code int/str ambiguity to work around.
    For real semantic decoding (message/data[] resolution, menu/branch decode), use
    xi-events-py/decompile_from_mission_toolkit.py on a specific event instead -- see
    ffxi_event_tooling_reference memory. This pass stays intentionally shallow: it's meant to get
    everything onto disk fast for a first look, not replace real investigation."""
    lines = []
    blocks = events_data.get("blocks", [])
    for block in blocks:
        entity_id = block.get("entity_id")
        for ev in block.get("events", []):
            event_id = ev.get("id")
            bc_raw = ev.get("byte_code", "")
            hexstr = bc_raw[2:] if isinstance(bc_raw, str) and bc_raw.startswith("0x") else str(bc_raw)
            if len(hexstr) % 2:
                hexstr = "0" + hexstr
            try:
                byte_code = bytes.fromhex(hexstr)
            except ValueError:
                continue
            lines.append(f"=== entity {entity_id} / event {event_id} ({len(byte_code)} bytes) ===")
            i = 0
            found_flags = []
            while i < len(byte_code):
                opcode = byte_code[i]
                size = SIZES.get(opcode)
                if size is None:
                    lines.append(f"  [{i:4d}] {opcode:02X} ?? -- UNKNOWN OPCODE, stopping disassembly here.")
                    break
                name = NAMES.get(opcode)
                flag = FLAGGED_OPCODES.get(opcode)
                operand = byte_code[i + 1 : i + size].hex().upper()
                name_str = f" ({name})" if name else ""
                flag_str = f"   <<< {flag}" if flag else ""
                lines.append(f"  [{i:4d}] {opcode:02X}{name_str:30s} operand={operand}{flag_str}")
                if flag:
                    found_flags.append((i, opcode, flag))
                i += size
            if found_flags:
                lines.append(f"  ** FLAGGED: {found_flags}")
            lines.append("")
    out_path.write_text("\n".join(lines), encoding="utf-8")
    return len(blocks)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("zone", help="topaz zone name (zone.lua constant, e.g. Mamool_Ja_Training_Grounds) or numeric zoneid")
    ap.add_argument("--out-dir", default="mission_reports")
    ap.add_argument("--ffxi-path", default=DEFAULT_FFXI_PATH)
    args = ap.parse_args()

    zoneid, zone_name = resolve_topaz_zone(args.zone)
    print(f"Resolved zone: {zone_name} (topaz zoneid {zoneid})")

    out_dir = Path(args.out_dir) / zone_name
    out_dir.mkdir(parents=True, exist_ok=True)

    summary = [f"# Mission Toolkit Report: {zone_name} (zoneid {zoneid})\n"]

    # 1. Geometry
    geo = resolve_geometry_mapid(zone_name)
    if geo:
        mapid, rom_path = geo
        (out_dir / "geometry.txt").write_text(f"mapid={mapid}\nrom_path={rom_path}\n")
        summary.append(f"- **3D geometry**: mapid `{mapid}` (`{rom_path}`) -- see `geometry.txt`\n")
        print(f"  geometry: mapid {mapid} ({rom_path})")
    else:
        summary.append("- **3D geometry**: not found in AltanaViewer_zones.csv\n")
        print("  geometry: not found in AltanaViewer_zones.csv")

    # 2. Events / dialog / entities DATs -- resolve real ROM paths in one batched call, then parse
    # each natively via xi-tinkerer-py (no more per-category subprocess + temp YAML round trip).
    categories = [("events", "events.yml"), ("dialog", "dialog.yml"), ("entities", "entities.yml")]
    dat_ids = {cat: dat_id_for_zone(zoneid, cat) for cat, _ in categories}
    rom_paths = resolve_rom_paths(args.ffxi_path, [d for d in dat_ids.values() if d is not None])

    events_data = None
    for category, filename in categories:
        dat_id = dat_ids[category]
        if dat_id is None:
            continue
        rom_path = rom_paths.get(dat_id)
        if not rom_path:
            print(f"  ! could not resolve a real ROM path for {category} (dat-id {dat_id})")
            summary.append(f"- **{category}**: dat-id `{dat_id}` -- path resolution failed\n")
            continue
        out_path = out_dir / filename
        print(f"  exporting {category} (dat-id {dat_id}, {rom_path}) -> {out_path}")
        # dat-extractor --resolve already returns the full absolute path -- don't re-prepend ffxi_path.
        ok = export_dat_native(category, rom_path, out_path)
        if ok:
            summary.append(f"- **{category}**: dat-id `{dat_id}` (`{rom_path}`) -- see `{filename}`\n")
            if category == "events":
                events_data = yaml.safe_load(out_path.read_text(encoding="utf-8"))
        else:
            summary.append(f"- **{category}**: dat-id `{dat_id}` -- native parse failed, see console output\n")

    # 3. Disassemble events
    if events_data:
        disasm_path = out_dir / "events_disasm.txt"
        n = disassemble_events_native(events_data, disasm_path)
        summary.append(f"- **events disassembly**: {n} entity blocks -- see `events_disasm.txt`\n")
        print(f"  disassembled events -> {disasm_path}")

    (out_dir / "SUMMARY.md").write_text("".join(summary), encoding="utf-8")
    print(f"\nDone. Report written to: {out_dir}")


if __name__ == "__main__":
    main()
