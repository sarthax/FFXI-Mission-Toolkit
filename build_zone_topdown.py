#!/usr/bin/env python3
"""
build_zone_topdown.py -- real, coordinate-aligned top-down zone silhouettes, rasterized from the
client's own real mesh rather than the client's decorative 2D minimap PNGs.

Why this exists: the client's in-game minimap images (ResourceExtractor's MapParser output,
mounted at /maps) are hand-drawn/stylized and carry no known, verified per-zone scale/rotate/
offset -- overlaying a real capture path on them would mean guessing that alignment. Real client
geometry is world-space, the SAME space captures report x/y/z in, so a top-down (x, -z)
rasterization of it is coordinate-correct by construction. Confirmed empirically 2026-09-03: real
capture path points against Ilrusi Atoll's collision mesh (zoneid 55) landed an average of 1.33
units from the nearest mesh vertex using (x, -z); the other 3 sign combinations averaged 15-33
units off. See entity_profile-adjacent capture work earlier this session for the ingested capture
data this validates against.

Builds BOTH a collision-mesh silhouette (the original, default -- clean walkable-space outline)
and a visual-mesh one (denser real terrain/wall/prop detail, cached as "<zoneid>_detailed.png").
The visual mesh was tried as the new default after the 3D zone viewer needed a real visual-mesh
export (build_zone_visual_cache.py, xi_tinkerer.parse_zone_visual_obj) -- but live comparison
found it's not a strict upgrade: some zones (Lebros Cavern in particular) have real decorative
overlay geometry (lava planes, etc.) that renders as solid blocks from directly above and hides
the actual tunnel shape the collision mesh shows cleanly. Neither mesh's OBJ export carries any
per-instance semantic label (nothing marks an instance as "this one is lava," specifically), so
there's no honest way to selectively exclude just the decorative instances -- the real, available
choice is which whole mesh to rasterize, not which pieces of one. Both are built and cached so the
GUI can offer a per-zone toggle instead of picking one for every zone.

Same real (x, -y, -z) coordinate convention for both meshes, each independently verified against
real capture points: collision mesh 1.33 units average distance to nearest vertex, visual mesh
0.91 (denser real surface detail, when it doesn't happen to be dominated by an overlay plane).

One PNG + one transform sidecar (json) per zone per mesh kind, generated once and cached --
rasterizing a zone's real mesh in Pillow takes real time (not free per-request, more so for the
visual mesh's much higher triangle count), and every future capture in a zone reuses the cache.

Usage:
    py -3 build_zone_topdown.py <zoneid>            -- build/rebuild both variants for one zone
    py -3 build_zone_topdown.py --all               -- build both variants for every zone an ingested capture references
    py -3 build_zone_topdown.py <zoneid> --collision-only   -- skip the visual-mesh variant
    py -3 build_zone_topdown.py <zoneid> --visual-only      -- skip the collision-mesh variant
"""
import argparse
import json
import sqlite3
import sys
from pathlib import Path

from PIL import Image, ImageDraw

import build_zone_visual_cache
import settings
import xi_tinkerer

TOOLS_ROOT = Path(__file__).parent
DB_PATH = TOOLS_ROOT / "ffxi_zone_database.db"
CACHE_DIR = TOOLS_ROOT / "gui" / "static" / "zone_topdown"
IMG_SIZE = 1024


def get_visual_obj_text(con, zoneid: int, ffxi_path: str) -> str | None:
    """Real visual-mesh OBJ text for a zone, reusing build_zone_visual_cache's own cache file
    (shared with the 3D viewer -- building it here for the 2D top-down means the 3D viewer never
    has to re-parse it later, and vice versa) rather than parsing it twice."""
    path = build_zone_visual_cache.CACHE_DIR / f"{zoneid}.obj"
    if not path.exists():
        con2 = sqlite3.connect(str(DB_PATH))
        ok = build_zone_visual_cache.build_one(con2, zoneid, ffxi_path)
        con2.close()
        if not ok:
            return None
    return path.read_text(encoding="utf-8") if path.exists() else None


def find_ffxi_install() -> str | None:
    """Settings' ffxi_install_path if set, else the same registry autodetection this function
    used to do inline -- now shared with every other module that needs the client path via
    settings.get_ffxi_install()."""
    return settings.get_ffxi_install()


def parse_obj_topdown(obj_text: str) -> tuple[list[tuple[float, float]], list[tuple[int, int, int]]]:
    """Real (x, z) vertices [z already negated by parse_zone_collision_obj's Wavefront
    convention -- see module docstring, this IS the space capture (x, -z) lands in] and
    1-indexed triangle faces, parsed straight out of the OBJ text."""
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
        # Image y grows downward; capture's own z sign is already folded into vertex z here
        # (see parse_obj_topdown docstring), so no further flip needed for the raster itself.
        return (
            pad + (x - minx) / span * (IMG_SIZE - 2 * pad),
            pad + (z - minz) / span * (IMG_SIZE - 2 * pad),
        )

    img = Image.new("RGBA", (IMG_SIZE, IMG_SIZE), (20, 24, 29, 255))
    draw = ImageDraw.Draw(img)
    px_verts = [px(x, z) for x, z in verts]
    for a, b, c in faces:
        try:
            draw.polygon([px_verts[a - 1], px_verts[b - 1], px_verts[c - 1]],
                         fill=(58, 68, 78, 255), outline=None)
        except IndexError:
            continue

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    img.save(img_path)

    transform = {
        "zoneid": zoneid, "zone_name": name, "img_size": IMG_SIZE, "pad": pad,
        "minx": minx, "maxx": maxx, "minz": minz, "maxz": maxz, "span": span,
        "mesh_kind": mesh_kind,
        "note": "pixel(x_px, z_px) = pad + (world_x - minx)/span*(IMG_SIZE-2*pad), same for z. "
                "world z here = -capture_z (see module docstring) -- a caller plotting a real "
                "capture point must negate its own z before applying this transform.",
    }
    json_path.write_text(json.dumps(transform, indent=2))
    print(f"  zoneid {zoneid} ({name}): {len(verts)} verts, {len(faces)} faces ({mesh_kind} mesh) -> {img_path.name}")
    return True


def build_one(con, zoneid: int, ffxi_path: str, collision: bool = True, visual: bool = True) -> bool:
    """Builds the collision-mesh variant (<zoneid>.png -- default/primary, matches original
    behavior) and/or the visual-mesh variant (<zoneid>_detailed.png -- denser real terrain detail,
    but see module docstring for why it's not strictly better everywhere) for one zone. Returns
    True if at least one variant built successfully."""
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
            ok = rasterize(zoneid, name, obj_text, "collision",
                            CACHE_DIR / f"{zoneid}.png", CACHE_DIR / f"{zoneid}.json") or ok
        except Exception as ex:
            print(f"  zoneid {zoneid} ({name}): FAILED to parse collision mesh -- {ex}")

    if visual:
        print(f"  zoneid {zoneid} ({name}): getting visual mesh...")
        obj_text = get_visual_obj_text(con, zoneid, ffxi_path)
        if obj_text:
            ok = rasterize(zoneid, name, obj_text, "visual",
                            CACHE_DIR / f"{zoneid}_detailed.png", CACHE_DIR / f"{zoneid}_detailed.json") or ok
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
        rows = con.execute("SELECT DISTINCT zone_db FROM capture_npc_entries").fetchall()
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
