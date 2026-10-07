#!/usr/bin/env python3
"""Build cached Wavefront OBJ files from FFXI zone visual geometry.

Canonical src-layout implementation for the zone visual-cache builder.
The generated cache intentionally remains under ``gui/static/zone_visual``.
"""
from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

import xi_tinkerer

from workbench.runtime.legacy_settings import get_ffxi_install
from workbench.runtime.paths import DATABASE_PATH, GUI_ROOT

DB_PATH = DATABASE_PATH
CACHE_DIR = GUI_ROOT / "static" / "zone_visual"


def visual_mesh_api_available() -> bool:
    """Return whether the installed xi_tinkerer exposes the extended visual-mesh API."""
    return callable(getattr(xi_tinkerer, "parse_zone_visual_obj", None))


def visual_mesh_api_error() -> str:
    return (
        "The installed xi_tinkerer module does not expose parse_zone_visual_obj. "
        "The normal 3D viewer can use the newer in-browser live DAT parser when the FFXI install "
        "and zone geometry DAT are configured. The legacy OBJ-cache fallback requires the toolkit's "
        "vendored extended xi-tinkerer-py binding, not the basic upstream release wheel."
    )


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

    if not visual_mesh_api_available():
        print(f"  zoneid {zoneid} ({name}): FAILED to parse -- {visual_mesh_api_error()}")
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

    ffxi_path = get_ffxi_install()
    if not ffxi_path:
        raise SystemExit(
            "Could not find FFXI install -- is it installed/registered on this machine, "
            "or set ffxi_install_path in Settings?"
        )
    print(f"FFXI install: {ffxi_path}")

    con = sqlite3.connect(str(DB_PATH))

    if args.all:
        from workbench.captures import review_queue as _rq   # skip quarantined captures
        rows = con.execute("SELECT DISTINCT zone_db FROM capture_npc_entries WHERE 1=1" + _rq.exclude_sql(con)).fetchall()
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
