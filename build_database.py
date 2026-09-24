#!/usr/bin/env python3
"""
build_database.py -- consolidates every FFXI dat tool's output into one queryable SQLite database.

Sources ingested:
  - C:\\topaz\\scripts\\globals\\zone.lua          -> zones (zoneid, name)
  - ffxi/reference/AltanaViewer_zones.csv         -> zones.geometry_mapid / geometry_rom_path
  - FFXI-DATS/Info/Door or Objects.json            -> door_props (ALL zones, global coverage)
  - FFXI-DATS/Info/Elevators.json                  -> elevators (ALL zones, global coverage)
  - FFXI-DATS/Info/Zone Lines.json                 -> zone_lines (ALL zones, global coverage)
  - FFXI-DATS/Entities/<zoneid>.json               -> entities (ALL zones with a file present)
  - xi-tinkerer export-dat (events)                -> events + events_disasm (per zone, run on demand
                                                       via --zones, since each requires a live FTABLE
                                                       parse + export -- not pre-bulk-loadable for free)

Usage:
    python build_database.py                        # (re)load all globally-available sources
    python build_database.py --zones 66 68 69        # also pull events for specific zones
    python build_database.py --zones all             # pull events for every zone (slow, ~361 zones)

Output: ffxi_zone_database.db (SQLite) in this directory.
"""
import argparse
import gzip
import json
import re
import shutil
import sqlite3
import subprocess
from datetime import datetime
from pathlib import Path

import xi_tinkerer
import settings

TOOLS_ROOT = Path(__file__).parent
TOPAZ_ROOT = settings.get_topaz_root()
LSB_ROOT = TOOLS_ROOT / "LandSandBoat"
DB_PATH = TOOLS_ROOT / "ffxi_zone_database.db"
DEFAULT_FFXI_PATH = settings.get_ffxi_install() or "C:/ValhallaXI/SquareEnix/FINAL FANTASY XI"
XI_TINKERER_EXE = TOOLS_ROOT / "vendor/xi-tinkerer/target/release/xi-tinkerer-cli.exe"
DAT_EXTRACTOR_EXE = TOOLS_ROOT / "vendor/dat-extractor/bin/Debug/net9.0/dat-extractor.exe"
ALTANA_ZONES_CSV = TOOLS_ROOT / "vendor/ffxi/reference/AltanaViewer_zones.csv"
FFXI_RESOURCES_DIST = TOOLS_ROOT / "FFXI-Resources-dist"
OPCODE_TABLE = json.loads((TOOLS_ROOT / "vendor/XiEvents/opcode_table.json").read_text())
SIZES = {int(k): v for k, v in OPCODE_TABLE["sizes"].items()}
NAMES = {int(k): v for k, v in OPCODE_TABLE["names"].items()}
FLAGGED_OPCODES = {0x46: "CodeDEFCAMERA", 0x6C: "CodeTRANSPAR"}

SCHEMA = """
CREATE TABLE IF NOT EXISTS zones (
    zoneid INTEGER PRIMARY KEY,
    name TEXT,
    geometry_mapid INTEGER,
    geometry_rom_path TEXT
);
CREATE TABLE IF NOT EXISTS door_props (
    zoneid INTEGER, identifier TEXT, x REAL, y REAL, z REAL,
    rot_x REAL, rot_y REAL, rot_z REAL,
    scale_x REAL, scale_y REAL, scale_z REAL, type TEXT
);
CREATE TABLE IF NOT EXISTS elevators (
    zoneid INTEGER, identifier TEXT, x REAL, y REAL, z REAL, raw_json TEXT
);
CREATE TABLE IF NOT EXISTS zone_lines (
    zoneid INTEGER, identifier TEXT, x REAL, y REAL, z REAL, raw_json TEXT
);
CREATE TABLE IF NOT EXISTS entities (
    zoneid INTEGER, server_id INTEGER, name TEXT, target_index INTEGER
);
CREATE TABLE IF NOT EXISTS events (
    zoneid INTEGER, entity_id INTEGER, event_id INTEGER, byte_code_hex TEXT
);
CREATE TABLE IF NOT EXISTS events_disasm_flags (
    zoneid INTEGER, entity_id INTEGER, event_id INTEGER, byte_offset INTEGER,
    opcode INTEGER, opcode_name TEXT
);
CREATE TABLE IF NOT EXISTS entities_ours (
    zoneid INTEGER, server_id INTEGER, name TEXT
);
CREATE TABLE IF NOT EXISTS id_drift (
    zoneid INTEGER, server_id INTEGER,
    name_external TEXT, name_ours TEXT, drift_type TEXT
);
CREATE TABLE IF NOT EXISTS items_external (
    id INTEGER, name TEXT, norm_name TEXT
);
CREATE TABLE IF NOT EXISTS items_ours (
    itemid INTEGER, name TEXT, norm_name TEXT
);
CREATE TABLE IF NOT EXISTS keyitems_external (
    id INTEGER, name TEXT, norm_name TEXT
);
CREATE TABLE IF NOT EXISTS keyitems_ours (
    id INTEGER, const_name TEXT, norm_name TEXT
);
CREATE INDEX IF NOT EXISTS idx_door_props_zone ON door_props(zoneid);
CREATE INDEX IF NOT EXISTS idx_entities_zone ON entities(zoneid);
CREATE INDEX IF NOT EXISTS idx_events_zone ON events(zoneid);
CREATE INDEX IF NOT EXISTS idx_entities_ours_zone ON entities_ours(zoneid);
CREATE INDEX IF NOT EXISTS idx_items_external_norm ON items_external(norm_name);
CREATE INDEX IF NOT EXISTS idx_items_ours_norm ON items_ours(norm_name);
CREATE INDEX IF NOT EXISTS idx_keyitems_external_norm ON keyitems_external(norm_name);
CREATE INDEX IF NOT EXISTS idx_keyitems_ours_norm ON keyitems_ours(norm_name);
"""


def normalize(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


def load_zones(conn):
    zone_lua = (TOPAZ_ROOT / "scripts/globals/zone.lua").read_text(encoding="utf-8", errors="ignore")
    zones = re.findall(r"^\s+([A-Z_0-9]+)\s*=\s*(\d+),$", zone_lua, re.M)

    geo_by_name = {}
    with open(ALTANA_ZONES_CSV, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("@") or "," not in line:
                continue
            path_part, csv_name = line.split(",", 1)
            parts = path_part.split("/")
            if len(parts) == 2:
                # A 2-part entry ("254/8") is a direct (dir, file) pair meant to be resolved
                # through the BASE client's own FTABLE.DAT/VTABLE.DAT -- i.e. it lives under the
                # plain "ROM" folder as ROM\<dir>\<file>.DAT, NOT under a folder literally named
                # "ROM<dir>". Confirmed 2026-09-23 against a real client: for zone 216 (Abyssea -
                # Misareaux), dat-extractor's real VTABLE/FTABLE resolver proved the zone's other
                # assets exist under plain ROM, and ROM\254\8.DAT itself exists and parses as a
                # valid 1.1M-vert zone mesh via xi_tinkerer.parse_zone_visual_obj -- while
                # ROM254\0\8.DAT (the old, wrong construction) doesn't exist at all. The previous
                # "ROM{dir_}\\0\\{file_}.DAT" form only ever worked by coincidence for dir_ 0-9.
                dir_, file_ = int(parts[0]), int(parts[1])
                sub = 0
                rom_path = f"ROM\\{dir_}\\{file_}.DAT"
            elif len(parts) == 3:
                # A 3-part entry ("3/0/24") is a literal ROM<n> folder suffix plus its own
                # dir/file -- these have their own separate VTABLE<n>/FTABLE<n> and really do
                # live under a folder named "ROM<n>" on disk. Unaffected by the above.
                dir_, sub, file_ = int(parts[0]), int(parts[1]), int(parts[2])
                rom_path = f"ROM{'' if dir_ == 0 else dir_}\\{sub}\\{file_}.DAT"
            else:
                continue
            mapid = dir_ * 1_000_000 + sub * 1000 + file_
            geo_by_name[normalize(csv_name)] = (mapid, rom_path)

    rows = []
    for const, zid in zones:
        key = normalize(const.replace("_", " "))
        mapid, rom_path = geo_by_name.get(key, (None, None))
        rows.append((int(zid), const, mapid, rom_path))
    conn.executemany("INSERT OR REPLACE INTO zones VALUES (?,?,?,?)", rows)
    print(f"  zones: {len(rows)} loaded ({sum(1 for r in rows if r[2] is not None)} with geometry)")


def load_door_objects(conn):
    path = TOOLS_ROOT / "FFXI-DATS/Info/Door or Objects.json"
    if not path.exists():
        print("  door_props: FFXI-DATS not found, skipping")
        return
    data = json.loads(path.read_text(encoding="utf-8"))
    rows = [
        (
            e.get("ZoneId"), (e.get("Identifier") or "").strip(),
            e.get("X"), e.get("Y"), e.get("Z"),
            e.get("RotationX"), e.get("RotationY"), e.get("RotationZ"),
            e.get("ScaleX"), e.get("ScaleY"), e.get("ScaleZ"),
            e.get("Type"),
        )
        for e in data
    ]
    conn.executemany("INSERT INTO door_props VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", rows)
    print(f"  door_props: {len(rows)} loaded (all zones)")


def load_simple_positions(conn, filename: str, table: str):
    path = TOOLS_ROOT / "FFXI-DATS/Info" / filename
    if not path.exists():
        print(f"  {table}: {filename} not found, skipping")
        return
    data = json.loads(path.read_text(encoding="utf-8"))
    rows = []
    for e in data:
        rows.append((
            e.get("ZoneId"), (e.get("Identifier") or "").strip(),
            e.get("X"), e.get("Y"), e.get("Z"), json.dumps(e),
        ))
    conn.executemany(f"INSERT INTO {table} VALUES (?,?,?,?,?,?)", rows)
    print(f"  {table}: {len(rows)} loaded (all zones)")


def load_entities(conn):
    entities_dir = TOOLS_ROOT / "FFXI-DATS/Entities"
    if not entities_dir.exists():
        print("  entities: FFXI-DATS/Entities not found, skipping")
        return
    total = 0
    for f in entities_dir.glob("*.json"):
        data = json.loads(f.read_text(encoding="utf-8"))
        zoneid = data.get("zoneID")
        rows = [
            (zoneid, e.get("serverID"), e.get("name"), e.get("targetIndex"))
            for e in data.get("entities", [])
        ]
        conn.executemany("INSERT INTO entities VALUES (?,?,?,?)", rows)
        total += len(rows)
    print(f"  entities: {total} loaded across {len(list(entities_dir.glob('*.json')))} zone files")


def dat_id_for_zone(zoneid: int, category: str):
    offsets_0_255 = {"zone_data": 100, "events": 5820, "dialog": 6420, "entities": 6720}
    offsets_256_511 = {"zone_data": 83891, "events": 84991, "dialog": 85590, "entities": 86491}
    if 0 <= zoneid <= 255:
        return offsets_0_255[category] + zoneid
    if 256 <= zoneid <= 511:
        return offsets_256_511[category] + (zoneid - 256)
    return None


def _resolve_dat_path(ffxi_path: str, dat_id: int) -> Path | None:
    """Resolves a real physical dat path for a numeric dat id via dat-extractor.exe --resolve --
    confirmed live this session that this uses the exact same numbering as xi-tinkerer-cli's own
    scan-dats/DatId (dat-extractor --resolve 5894 and scan-dats' "Events: DatId(5894)" both point
    at the identical ROM4/0/79.DAT), so this is a safe, already-proven-reliable substitute for
    resolving a path -- used here specifically to avoid xi-tinkerer-cli's own `export-dat`
    subcommand, which panics (`Option::unwrap() on a None value` in crates/dats/src/base.rs:140)
    on every dat id tested, not just Events ones -- confirmed a real bug in that binary, not a
    dat-id math error on our side."""
    if not DAT_EXTRACTOR_EXE.exists():
        return None
    result = subprocess.run(
        [str(DAT_EXTRACTOR_EXE), "--resolve", ffxi_path, str(dat_id)],
        capture_output=True, text=True,
    )
    for line in result.stdout.splitlines():
        parts = line.split("\t")
        if len(parts) >= 2:
            path = Path(parts[1])
            if path.exists():
                return path
    return None


def load_events_for_zone(conn, zoneid: int, ffxi_path: str, tmp_dir: Path):
    dat_id = dat_id_for_zone(zoneid, "events")
    if dat_id is None:
        return 0
    dat_path = _resolve_dat_path(ffxi_path, dat_id)
    if dat_path is None:
        return 0

    # xi_tinkerer's own Python binding (parse_events) reads the resolved dat directly and returns
    # real structured data (blocks -> entity_id + events[{id, byte_code}]) -- no YAML text/regex
    # parsing needed at all, and no dependency on xi-tinkerer-cli's broken export-dat command.
    try:
        parsed = xi_tinkerer.parse_events(str(dat_path))
    except Exception:
        return 0

    event_rows, flag_rows = [], []
    for block in parsed.get("blocks", []):
        entity_id = block.get("entity_id")
        if entity_id is None:
            continue
        for ev in block.get("events", []):
            event_id = ev.get("id")
            hexstr = str(ev.get("byte_code", "0x")).removeprefix("0x")
            if event_id is None or not hexstr:
                continue
            event_rows.append((zoneid, entity_id, int(event_id), hexstr))
            byte_code = bytes.fromhex(hexstr)
            i = 0
            while i < len(byte_code):
                opcode = byte_code[i]
                size = SIZES.get(opcode)
                if size is None:
                    break
                if opcode in FLAGGED_OPCODES:
                    flag_rows.append((zoneid, entity_id, int(event_id), i, opcode, FLAGGED_OPCODES[opcode]))
                i += size

    conn.executemany("INSERT INTO events VALUES (?,?,?,?)", event_rows)
    conn.executemany("INSERT INTO events_disasm_flags VALUES (?,?,?,?,?,?)", flag_rows)
    return len(event_rows)


def load_our_entities_for_zone(conn, zoneid: int, ffxi_path: str, tmp_dir: Path):
    """Pulls entity names directly from OUR OWN registered client via xi-tinkerer (FTABLE-backed),
    as ground truth to compare against external pre-extracted snapshots (which may come from a
    different, newer client version and carry their own id drift)."""
    dat_id = dat_id_for_zone(zoneid, "entities")
    if dat_id is None:
        return 0
    out_path = tmp_dir / f"entities_{zoneid}.yml"
    result = subprocess.run(
        [str(XI_TINKERER_EXE), "export-dat", ffxi_path, "--dat-id", str(dat_id), str(out_path)],
        capture_output=True, text=True,
    )
    if result.returncode != 0 or not out_path.exists():
        return 0

    text = out_path.read_text(encoding="utf-8")
    rows = [
        (zoneid, int(m.group(1)), m.group(2).strip())
        for m in re.finditer(r"- id: (\d+)\n\s*name: (.+)", text)
    ]
    conn.executemany("INSERT INTO entities_ours VALUES (?,?,?)", rows)
    return len(rows)


def compute_id_drift(conn):
    """Compares entities_ours (our real client, via xi-tinkerer/FTABLE) against entities
    (external FFXI-DATS snapshot, possibly a different client version) for the same zoneid+server_id.
    Flags real name mismatches as drift -- these are exactly the cases where trusting the external
    tool's id numbering without cross-checking against our own client would be wrong."""
    conn.execute("DELETE FROM id_drift")
    rows = conn.execute("""
        SELECT o.zoneid, o.server_id, e.name, o.name
        FROM entities_ours o
        JOIN entities e ON e.zoneid = o.zoneid AND e.server_id = o.server_id
        WHERE e.name != o.name
    """).fetchall()
    conn.executemany(
        "INSERT INTO id_drift VALUES (?,?,?,?,?)",
        [(z, sid, ext, ours, "entity_name_mismatch") for z, sid, ext, ours in rows],
    )
    return len(rows)


def load_items_external(conn):
    """items.ndjson.gz -- LSB/retail-era item catalogue (FFXI-Resources, version 30260805_0).
    Confirmed useful for research/naming even though the numeric id space can drift for some
    categories (see [[topaz_client_id_offset]]) -- items_ours below is the ground truth to
    cross-check any id against before trusting it on Topaz."""
    path = FFXI_RESOURCES_DIST / "items.ndjson.gz"
    if not path.exists():
        print("  items_external: FFXI-Resources-dist not found, skipping")
        return
    rows = []
    with gzip.open(path, "rt", encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            name = (d.get("name") or {}).get("english") or ""
            rows.append((d.get("id"), name, normalize(name)))
    conn.executemany("INSERT INTO items_external VALUES (?,?,?)", rows)
    print(f"  items_external: {len(rows)} loaded")


def load_items_ours(conn):
    """LandSandBoat/sql/item_basic.sql -- the active primary source's (LSB's) own live-used item
    ids and internal (snake_case) names. Repointed from Topaz to LSB per CORE_AGNOSTIC_DESIGN.md's
    LSB-primary rework -- the Topaz-vs-LSB comparison this used to drive now lives in the backport
    module (build_topaz_index.py's topaz_item_basic, diffed in gui_server.py's _iddrift_items)."""
    path = LSB_ROOT / "sql/item_basic.sql"
    if not path.exists():
        print("  items_ours: item_basic.sql not found, skipping")
        return
    text = path.read_text(encoding="utf-8", errors="ignore")
    rows = []
    for m in re.finditer(r"INSERT INTO `item_basic` VALUES \((\d+),\d+,'((?:[^'\\]|\\.)*)'", text):
        itemid, name = m.groups()
        name = name.replace("_", " ")
        rows.append((int(itemid), name, normalize(name)))
    conn.executemany("INSERT INTO items_ours VALUES (?,?,?)", rows)
    print(f"  items_ours: {len(rows)} loaded")


def load_keyitems_external(conn):
    """keyitems.ndjson.gz -- LSB/retail-era key item catalogue. CONFIRMED to drift hard against
    Topaz for at least some ids (LC quest tubes: 794/814 resolved to totally unrelated retail
    items) -- never trust the numeric id alone, always cross-check via keyitems_ours."""
    path = FFXI_RESOURCES_DIST / "keyitems.ndjson.gz"
    if not path.exists():
        print("  keyitems_external: FFXI-Resources-dist not found, skipping")
        return
    rows = []
    with gzip.open(path, "rt", encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            name = d.get("name") or ""
            rows.append((d.get("id"), name, normalize(name)))
    conn.executemany("INSERT INTO keyitems_external VALUES (?,?,?)", rows)
    print(f"  keyitems_external: {len(rows)} loaded")


def load_keyitems_ours(conn):
    """LandSandBoat/scripts/enum/key_item.lua -- the active primary source's (LSB's) own
    live-used key item ids (xi.keyItem.CONST_NAME = id). Repointed from Topaz to LSB per
    CORE_AGNOSTIC_DESIGN.md's LSB-primary rework -- the Topaz-vs-LSB comparison this used to
    drive now lives in the backport module (build_topaz_index.py's topaz_keyitems, diffed in
    gui_server.py's _iddrift_keyitems)."""
    path = LSB_ROOT / "scripts/enum/key_item.lua"
    if not path.exists():
        print("  keyitems_ours: key_item.lua not found, skipping")
        return
    text = path.read_text(encoding="utf-8", errors="ignore")
    rows = []
    for m in re.finditer(r"^\s+([A-Z_0-9]+)\s*=\s*(\d+),?\s*$", text, re.M):
        const, kid = m.groups()
        name = const.replace("_", " ")
        rows.append((int(kid), const, normalize(name)))
    conn.executemany("INSERT INTO keyitems_ours VALUES (?,?,?)", rows)
    print(f"  keyitems_ours: {len(rows)} loaded")


DB_BACKUPS_DIR = TOOLS_ROOT / "db_backups"


def backup_database_file(min_interval_seconds: float = 0):
    """Cheap insurance modeled on Topaz's own tools/dbtool.py (backup_db(), which runs
    automatically before every update/reset) -- a real timestamped copy of the whole database
    file before anything touches it, so even a future bug (in this file or in gui_server.py's own
    /rebuild/{source} route, which calls this same function) is a file-copy away from undone.
    Confirmed the real need for this live this session: a plain CLI run of this file with no
    dangerous-looking flags at all still wiped 64 tables down to 9, back when main()
    unconditionally unlinked the whole file. min_interval_seconds lets a caller that fires many
    times per session (gui_server.py, once per Rebuild click) coalesce to one real copy per
    window instead of one per click; the CLI here always wants a fresh one (default 0)."""
    if not DB_PATH.exists():
        return
    import time
    global _last_backup_at
    now = time.time()
    if now - _last_backup_at < min_interval_seconds:
        return
    DB_BACKUPS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    shutil.copy2(DB_PATH, DB_BACKUPS_DIR / f"ffxi_zone_database-{stamp}.db")
    _last_backup_at = now
    # Keep only the N most recent (real user setting, see settings.py's own comment -- a safety
    # net for "undo my last few actions," not a permanent archive; unbounded growth would just
    # quietly fill the disk with db-sized copies). Read fresh here rather than cached, so a
    # Settings change applies to the very next backup.
    import settings as _settings
    keep_con = sqlite3.connect(DB_PATH)
    try:
        retention = int(_settings.get(keep_con, "backup_retention_count") or _settings.DEFAULTS["backup_retention_count"])
    except (ValueError, TypeError):
        retention = int(_settings.DEFAULTS["backup_retention_count"])
    finally:
        keep_con.close()
    backups = sorted(DB_BACKUPS_DIR.glob("ffxi_zone_database-*.db"))
    for old in backups[:-retention] if retention > 0 else backups:
        old.unlink()


_last_backup_at = 0.0


NO_PK_TABLES = ("door_props", "elevators", "zone_lines", "entities",
                "items_external", "items_ours", "keyitems_external", "keyitems_ours")


def safe_rebuild(conn: sqlite3.Connection):
    """The one real implementation of "reload this module's own tables" -- DELETE-then-reload for
    the 8 tables above (confirmed live they have no primary key/unique constraint at all, so a
    plain re-INSERT against an already-populated table silently doubles every row; clicking a
    Rebuild button twice in a row exactly doubled items_external/items_ours/etc before this fix),
    load_zones() alone stays INSERT OR REPLACE since zoneid is a real primary key.

    This function -- not a copy of it, not a reimplementation -- is what both gui_server.py's
    rebuild_database() and this file's own CLI main() call. They used to diverge: main() instead
    unconditionally ran DB_PATH.unlink(), deleting the ENTIRE database file (every other module's
    tables too -- dialog_text, npc_names, sql_*, lsb_*, everything) just to reload these 9. That
    divergence is exactly what caused a real incident this session: a plain, seemingly read-only
    `python build_database.py --ffxi-path ...` CLI call (run to test a hypothesis, not to rebuild
    anything) silently wiped 64 tables' worth of already-built data down to just these 9, because
    nothing about the command looked destructive. Routing both callers through this single
    function makes that divergence structurally impossible instead of a rule to remember."""
    conn.executescript(SCHEMA)
    for table in NO_PK_TABLES:
        conn.execute(f"DELETE FROM {table}")
    load_zones(conn)
    load_door_objects(conn)
    load_simple_positions(conn, "Elevators.json", "elevators")
    load_simple_positions(conn, "Zone Lines.json", "zone_lines")
    load_entities(conn)
    load_items_external(conn)
    load_items_ours(conn)
    load_keyitems_external(conn)
    load_keyitems_ours(conn)
    conn.commit()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--zones", nargs="*", default=[], help="zoneids (or 'all') to pull live events for")
    ap.add_argument("--ffxi-path", default=DEFAULT_FFXI_PATH)
    ap.add_argument("--wipe-everything", action="store_true",
                     help="DANGER: deletes the entire database file (every table from every "
                          "module -- dialog, npc names, SQL index, LSB cross-reference, events, "
                          "everything), not just this script's own 9 tables. Only ever needed to "
                          "recover from real corruption; a normal rebuild never needs this.")
    ap.add_argument("--i-am-sure", action="store_true",
                     help="required alongside --wipe-everything, so the destructive path can "
                          "never fire from a flag typo or a copied command alone")
    args = ap.parse_args()

    backup_database_file()

    if args.wipe_everything:
        if not args.i_am_sure:
            raise SystemExit(
                "--wipe-everything also needs --i-am-sure -- this deletes the ENTIRE database "
                "file (every table from every module, not just this script's own), not a normal "
                "rebuild. If that's really what you want, add --i-am-sure too."
            )
        if DB_PATH.exists():
            DB_PATH.unlink()

    conn = sqlite3.connect(DB_PATH)
    print("Loading globally-available sources...")
    safe_rebuild(conn)

    if args.zones:
        tmp_dir = TOOLS_ROOT / "mission_reports" / "_events_tmp"
        tmp_dir.mkdir(parents=True, exist_ok=True)
        if args.zones == ["all"]:
            zoneids = [r[0] for r in conn.execute("SELECT zoneid FROM zones")]
        else:
            zoneids = [int(z) for z in args.zones]
        print(f"Pulling live events for {len(zoneids)} zone(s)...")
        for zid in zoneids:
            n = load_events_for_zone(conn, zid, args.ffxi_path, tmp_dir)
            print(f"  zone {zid}: {n} events")
        conn.commit()

        print(f"Pulling entities from OUR OWN client for {len(zoneids)} zone(s) (drift check)...")
        for zid in zoneids:
            n = load_our_entities_for_zone(conn, zid, args.ffxi_path, tmp_dir)
            print(f"  zone {zid}: {n} entities from our client")
        conn.commit()

        n_drift = compute_id_drift(conn)
        conn.commit()
        print(f"id_drift: {n_drift} mismatches found between our client and external (FFXI-DATS) data")
        if n_drift:
            for row in conn.execute("SELECT zoneid, server_id, name_external, name_ours FROM id_drift LIMIT 20"):
                print(f"    zone {row[0]} id {row[1]}: external='{row[2]}' vs ours='{row[3]}'")

    counts = {row[0]: row[1] for row in conn.execute(
        "SELECT 'zones', COUNT(*) FROM zones UNION ALL "
        "SELECT 'door_props', COUNT(*) FROM door_props UNION ALL "
        "SELECT 'elevators', COUNT(*) FROM elevators UNION ALL "
        "SELECT 'zone_lines', COUNT(*) FROM zone_lines UNION ALL "
        "SELECT 'entities', COUNT(*) FROM entities UNION ALL "
        "SELECT 'events', COUNT(*) FROM events UNION ALL "
        "SELECT 'events_disasm_flags', COUNT(*) FROM events_disasm_flags UNION ALL "
        "SELECT 'items_external', COUNT(*) FROM items_external UNION ALL "
        "SELECT 'items_ours', COUNT(*) FROM items_ours UNION ALL "
        "SELECT 'keyitems_external', COUNT(*) FROM keyitems_external UNION ALL "
        "SELECT 'keyitems_ours', COUNT(*) FROM keyitems_ours"
    )}
    print(f"\nDatabase written to: {DB_PATH}")
    for table, count in counts.items():
        print(f"  {table}: {count} rows")
    conn.close()


if __name__ == "__main__":
    main()
