#!/usr/bin/env python3
"""
build_zone_visual_cache.py -- real zone VISUAL mesh (walls, buildings, props -- what the client
actually renders, not the invisible collision/navmesh build_zone_topdown.py uses), cached as a
raw Wavefront OBJ per zone for the browser-side 3D viewer to fetch directly.

Why this exists: informed by reading Soverance/Vanalytics (MIT-licensed) -- a real, mature
FFXI web companion app with its own from-scratch TypeScript DAT parser and a React Three Fiber
zone/model viewer. Its own commit history says its zone parser was written "learning from
[the] tinkerer project" (xi-tinkerer, already in this toolkit) -- meaning xi-tinkerer's own Rust
code already parses the same real MMB/MZB visual-mesh chunks, just via a function
(`processor::wavefront_obj::make_model_wavefront_file`) that was never bound to Python. Rather
than port Vanalytics' TypeScript parser, this exposes that already-real, already-tested Rust
function through a new xi-tinkerer-py binding (`parse_zone_visual_obj`) -- same repo, same
AGPLv3 license, no new parsing logic to get wrong. Vanalytics' own architecture (place markers
directly in the 3D world mesh, never the decorative minimap) also independently confirms the
approach build_zone_topdown.py already took.

Coordinate convention: same (x, -y, -z) as parse_zone_collision_obj, verified empirically against
this SAME mesh (not just assumed to carry over) -- real capture path points landed an average of
0.91 units from the nearest visual-mesh vertex under (x, -z), even tighter than the collision
mesh's 1.33 (denser real surface detail).

No textures/materials -- Topaz's own MMB/MZB parsing doesn't carry per-triangle texture
assignment out to xi-tinkerer's chunk structs, so this is real geometry, honestly untextured.

Usage:
    py -3 build_zone_visual_cache.py <zoneid>     -- build/rebuild one zone's cache
    py -3 build_zone_visual_cache.py --all        -- build every zone referenced by an ingested capture
"""
import argparse
import sqlite3
import sys
from pathlib import Path

import settings
import xi_tinkerer

TOOLS_ROOT = Path(__file__).parent
DB_PATH = TOOLS_ROOT / "ffxi_zone_database.db"
CACHE_DIR = TOOLS_ROOT / "gui" / "static" / "zone_visual"


def build_one(con, zoneid: int, ffxi_path: str) -> bool:
    row = con.execute("SELECT name, geometry_rom_path FROM zones WHERE zoneid=?", (zoneid,)).fetchone()
    if not row or not row[1]:
        print(f"  zoneid {zoneid}: no geometry_rom_path in zones table -- skipping")
        return False
    name, rom_path = row
    dat_path = str(Path(ffxi_path) / rom_path)
    if not Path(dat_path).exists():
        print(f"  zoneid {zoneid} ({name}): dat not found at {dat_path}")
        return False

    print(f"  zoneid {zoneid} ({name}): parsing visual mesh...")
    try:
        obj_text = xi_tinkerer.parse_zone_visual_obj(dat_path)
    except Exception as ex:
        print(f"  zoneid {zoneid} ({name}): FAILED to parse -- {ex}")
        return False

    if not obj_text.strip():
        print(f"  zoneid {zoneid} ({name}): no visual mesh data -- skipping")
        return False

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    out_path = CACHE_DIR / f"{zoneid}.obj"
    out_path.write_text(obj_text, encoding="utf-8")
    n_verts = obj_text.count("\nv ")
    n_faces = obj_text.count("\nf ")
    size_mb = out_path.stat().st_size / (1024 * 1024)
    print(f"  zoneid {zoneid} ({name}): {n_verts} verts, {n_faces} faces, {size_mb:.1f} MB -> {out_path.name}")
    return True


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("zoneid", type=int, nargs="?")
    ap.add_argument("--all", action="store_true", help="build every zone an ingested capture references")
    args = ap.parse_args()

    ffxi_path = settings.get_ffxi_install()
    if not ffxi_path:
        raise SystemExit("Could not find FFXI install -- is it installed/registered on this machine, "
                          "or set ffxi_install_path in Settings?")
    print(f"FFXI install: {ffxi_path}")

    con = sqlite3.connect(str(DB_PATH))

    if args.all:
        rows = con.execute("SELECT DISTINCT zone_db FROM capture_npc_entries").fetchall()
        zoneids = set()
        for (zone_db,) in rows:
            norm = zone_db.upper().replace(" ", "_").replace("'", "")
            r = con.execute("SELECT zoneid FROM zones WHERE REPLACE(name, ' ', '_') = ?", (norm,)).fetchone()
            if r:
                zoneids.add(r[0])
        print(f"Building visual-mesh cache for {len(zoneids)} zone(s) referenced by ingested captures...")
        for zid in sorted(zoneids):
            build_one(con, zid, ffxi_path)
    elif args.zoneid:
        build_one(con, args.zoneid, ffxi_path)
    else:
        ap.print_help()

    con.close()


if __name__ == "__main__":
    main()
