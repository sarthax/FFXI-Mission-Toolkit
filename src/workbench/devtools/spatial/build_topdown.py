#!/usr/bin/env python3
"""Build coordinate-aligned top-down zone silhouettes from real client geometry.

Canonical src-layout implementation for zone top-down cache generation.
Generated PNG/JSON cache files intentionally remain under ``gui/static/zone_topdown``.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path

from PIL import Image, ImageDraw
import xi_tinkerer

from workbench.devtools.spatial import build_visual_cache
from workbench.runtime.legacy_settings import get_ffxi_install
from workbench.runtime.paths import DATABASE_PATH, GUI_ROOT

DB_PATH = DATABASE_PATH
CACHE_DIR = GUI_ROOT / "static" / "zone_topdown"
IMG_SIZE = 1024


def get_visual_obj_text(con, zoneid: int, ffxi_path: str) -> str | None:
    """Return the shared cached visual-mesh OBJ text for a zone, building it if necessary."""
    path = build_visual_cache.CACHE_DIR / f"{zoneid}.obj"
    if not path.exists():
        con2 = sqlite3.connect(str(DB_PATH))
        ok = build_visual_cache.build_one(con2, zoneid, ffxi_path)
        con2.close()
        if not ok:
            return None
    return path.read_text(encoding="utf-8") if path.exists() else None


def find_ffxi_install() -> str | None:
    """Return the configured or auto-detected FFXI installation path."""
    return get_ffxi_install()


def parse_obj_topdown(obj_text: str) -> tuple[list[tuple[float, float]], list[tuple[int, int, int]]]:
    """Parse OBJ vertices into the toolkit's real top-down ``(x, z)`` coordinate space."""
    verts = []
    faces = []
    for line in obj_text.splitlines():
        if line.startswith("v "):
            _, x, _y, z = line.split()
            verts.append((float(x), float(z)))
        elif line.startswith("f "):
            _, a, b, c = line.split()
            faces.append((int(a), int(b), int(c)))
    return verts, faces


def rasterize(zoneid: int, name: str, obj_text: str, mesh_kind: str, img_path: Path, json_path: Path) -> bool:
    verts, faces = parse_obj_topdown(obj_text)
    if not verts:
        print(f"  zoneid {zoneid} ({name}): no vertices in {mesh_kind} mesh -- skipping")
        return False
    print(f"  zoneid {zoneid} ({name}): rasterizing {len(faces)} real {mesh_kind}-mesh faces...")

    xs = [v[0] for v in verts]
    zs = [v[1] for v in verts]
    minx, maxx = min(xs), max(xs)
    minz, maxz = min(zs), max(zs)
    span = max(maxx - minx, maxz - minz, 1e-6)
    pad = 12

    def px(x, z):
        return (
            pad + (x - minx) / span * (IMG_SIZE - 2 * pad),
            pad + (z - minz) / span * (IMG_SIZE - 2 * pad),
        )

    img = Image.new("RGBA", (IMG_SIZE, IMG_SIZE), (20, 24, 29, 255))
    draw = ImageDraw.Draw(img)
    px_verts = [px(x, z) for x, z in verts]
    for a, b, c in faces:
        try:
            draw.polygon(
                [px_verts[a - 1], px_verts[b - 1], px_verts[c - 1]],
                fill=(58, 68, 78, 255),
                outline=None,
            )
        except IndexError:
            continue

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    img.save(img_path)

    transform = {
        "zoneid": zoneid,
        "zone_name": name,
        "img_size": IMG_SIZE,
        "pad": pad,
        "minx": minx,
        "maxx": maxx,
        "minz": minz,
        "maxz": maxz,
        "span": span,
        "mesh_kind": mesh_kind,
        "note": "pixel(x_px, z_px) = pad + (world_x - minx)/span*(IMG_SIZE-2*pad), same for z. "
        "world z here = -capture_z; a caller plotting a real capture point must negate its own z "
        "before applying this transform.",
    }
    json_path.write_text(json.dumps(transform, indent=2))
    print(
        f"  zoneid {zoneid} ({name}): {len(verts)} verts, {len(faces)} faces "
        f"({mesh_kind} mesh) -> {img_path.name}"
    )
    return True


def build_one(con, zoneid: int, ffxi_path: str, collision: bool = True, visual: bool = True) -> bool:
    """Build collision and/or visual top-down cache variants for one zone."""
    row = con.execute("SELECT name, geometry_rom_path FROM zones WHERE zoneid=?", (zoneid,)).fetchone()
    if not row or not row[1]:
        print(f"  zoneid {zoneid}: no geometry_rom_path in zones table -- skipping")
        return False
    name, rom_path = row
    dat_path = str(Path(ffxi_path) / rom_path)
    if not Path(dat_path).exists():
        print(f"  zoneid {zoneid} ({name}): dat not found at {dat_path}")
        return False

    ok = False

    if collision:
        print(f"  zoneid {zoneid} ({name}): parsing collision mesh...")
        try:
            obj_text = xi_tinkerer.parse_zone_collision_obj(dat_path)
            ok = rasterize(
                zoneid,
                name,
                obj_text,
                "collision",
                CACHE_DIR / f"{zoneid}.png",
                CACHE_DIR / f"{zoneid}.json",
            ) or ok
        except Exception as ex:
            print(f"  zoneid {zoneid} ({name}): FAILED to parse collision mesh -- {ex}")

    if visual:
        print(f"  zoneid {zoneid} ({name}): getting visual mesh...")
        obj_text = get_visual_obj_text(con, zoneid, ffxi_path)
        if obj_text:
            ok = rasterize(
                zoneid,
                name,
                obj_text,
                "visual",
                CACHE_DIR / f"{zoneid}_detailed.png",
                CACHE_DIR / f"{zoneid}_detailed.json",
            ) or ok
        else:
            print(f"  zoneid {zoneid} ({name}): no visual mesh available -- skipping detailed variant")

    return ok


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("zoneid", type=int, nargs="?")
    ap.add_argument("--all", action="store_true", help="build every zone an ingested capture references")
    ap.add_argument("--collision-only", action="store_true", help="skip the visual-mesh (detailed) variant")
    ap.add_argument("--visual-only", action="store_true", help="skip the collision-mesh (default) variant")
    args = ap.parse_args()
    do_collision = not args.visual_only
    do_visual = not args.collision_only

    ffxi_path = find_ffxi_install()
    if not ffxi_path:
        raise SystemExit("Could not find FFXI install via registry -- is it installed on this machine?")
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
        print(f"Building top-down cache for {len(zoneids)} zone(s) referenced by ingested captures...")
        for zid in sorted(zoneids):
            build_one(con, zid, ffxi_path, collision=do_collision, visual=do_visual)
    elif args.zoneid:
        build_one(con, args.zoneid, ffxi_path, collision=do_collision, visual=do_visual)
    else:
        ap.print_help()

    con.close()


if __name__ == "__main__":
    main()
