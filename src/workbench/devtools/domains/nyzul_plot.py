"""Nyzul Isle plot tool backend: parses the DSP Lua spawn data + Nyzul_Isle.nav (pure Python)
and computes per-layout reachability (connected components of the navmesh from each entrance).
Everything is read live from the DSP repo (Settings' dsp_server_path) so re-running picks up
edits. The packaged spatial Zone Plot backend also imports this module's generic nav_polys()/nav_triangles_bytes() for
every zone (Topaz included), so the DSP root below is resolved lazily per-call, never at import
time -- importing this module must not require dsp_server_path to be configured."""
import json
import math
import re
import struct
from pathlib import Path

from workbench.runtime.legacy_settings import get_dsp_root
from workbench.runtime.paths import DATA_ROOT

EXCL_FILE = DATA_ROOT / "nyzul_exclusions.json"


def _dsp_root() -> Path:
    root = get_dsp_root()
    if root is None:
        raise ValueError("DSP server path isn't configured yet -- set it on the Settings page first")
    return root


def _floor_layouts() -> Path:
    return _dsp_root() / "scripts/globals/nyzul/floor_layouts.lua"


def _nyzul_lua() -> Path:
    return _dsp_root() / "scripts/globals/nyzul.lua"


def _ids_lua() -> Path:
    return _dsp_root() / "scripts/zones/Nyzul_Isle/IDs.lua"


def _default_nav() -> Path:
    return _dsp_root() / "navmeshes/Nyzul_Isle.nav"

NUM = r"(-?\d+(?:\.\d+)?)"


def _block(text, start_pat):
    m = re.search(start_pat, text)
    i = text.index("{", m.end())
    depth, j = 0, i
    while True:
        c = text[j]
        depth += c == "{"
        depth -= c == "}"
        j += 1
        if depth == 0:
            return text[i:j]


def _per_layout(block, item_re):
    """Split a `[n] = { ... }` table of tables into {layout: [points]}."""
    out = {}
    for m in re.finditer(r"^\s{4}\[(\d+)\]\s*=[^\n{]*\n\s{4}\{", block, re.M):
        start = m.end() - 1
        depth, j = 0, start
        while True:
            depth += block[j] == "{"
            depth -= block[j] == "}"
            j += 1
            if depth == 0:
                break
        out[int(m.group(1))] = [[float(a), float(b), float(c)] for a, b, c in re.findall(item_re, block[start:j])]
    return out


def load_data():
    fl = _floor_layouts().read_text(encoding="utf-8", errors="replace")
    lamp_blk = _block(fl, r"(?m)^Nyzul\.lampSpawnPoints\s*=")
    lay_blk = _block(fl, r"(?m)^Nyzul\.layoutSpawnPoints\s*=")
    lamps = _per_layout(lamp_blk, r"\{\s*" + NUM + r"\s*,\s*" + NUM + r"\s*,\s*" + NUM + r"\s*\}")
    points = _per_layout(lay_blk, r"x\s*=\s*" + NUM + r"\s*,\s*y\s*=\s*" + NUM + r"\s*,\s*z\s*=\s*" + NUM)

    nz = _nyzul_lua().read_text(encoding="utf-8", errors="replace")
    ent = {}
    for m in re.finditer(r"\[\s*(\d+)\]\s*=\s*\{\s*" + NUM + r",\s*" + NUM + r",\s*" + NUM + r"\s*\}", _block(nz, r"Nyzul\.FloorLayout\s*=")):
        ent[int(m.group(1))] = [float(m.group(2)), float(m.group(3)), float(m.group(4))]

    ids = _ids_lua().read_text(encoding="utf-8", errors="replace")
    fam = {}
    for m in re.finditer(r"\[(\d+)\]\s*=\s*\{\s*--\s*([^\n]*)\n(.*?)\n\s*\},", _block(ids, r"ENEMY_LAYOUTS\s*="), re.S):
        fam[int(m.group(1))] = {
            "label": m.group(2).strip(),
            "groups": [{"id": int(a), "count": int(b), "name": c.strip()}
                       for a, b, c in re.findall(r"id\s*=\s*(\d+),\s*count\s*=\s*(\d+)\s*\},?\s*--\s*([^\n(]*)", m.group(3))],
        }

    def named(block):
        return [{"id": int(a), "name": re.sub(r"\s+", " ", b).strip()}
                for a, b in re.findall(r"^\s*[A-Z_0-9]+\s*=\s*(\d{8}),\s*--\s*([^\n]*)", block, re.M)]

    leaders = named(ids[re.search(r"MOKKE\s+=",ids).start():ids.index("SPECIFIED_GROUPS")])
    leaders = [l for l in leaders if "Qiqirn_Mine" not in l["name"]]
    groups = [{"id": int(a), "count": int(b), "name": c.strip()} for a, b, c in
              re.findall(r"\{\s*id\s*=\s*(\d+),\s*count\s*=\s*(\d+)\s*\},\s*--\s*([^\n]*)", _block(ids, r"SPECIFIED_GROUPS\s*="))]
    nm = {}
    for key in ("NM_EVEN", "NM_ODD"):
        nm[key] = [int(a) for a in re.findall(r"id\s*=\s*(\d+)", _block(ids, key + r"\s*="))]
    bosses = {k: int(v) for k, v in re.findall(r"^\s*(ADAMANTOISE|BEHEMOTH|FAFNIR|KHIMAIRA|HYDRA|CERBERUS|ARCHAIC_RAMPART|DAHAK|GEAR_OFFSET)\s*=\s*(\d+)", ids, re.M)}
    return {"lamps": lamps, "points": points, "entrances": ent, "families": fam, "leaders": leaders,
            "groups": groups, "nm": nm, "bosses": bosses}


# ---- navmesh -------------------------------------------------------------------------------
_nav_cache = {}


def nav_polys(path=None):
    """Return list of polygons, each a list of (x,y,z) in FFXI world coords."""
    path = Path(path or _default_nav())
    if ("polys", path) in _nav_cache:
        return _nav_cache[("polys", path)]
    b = path.read_bytes()
    assert b[:4] == b"TESM", "not a navmeshset"
    ntiles = struct.unpack_from("<i", b, 8)[0]
    off, polys = 40, []
    for _ in range(ntiles):
        if off + 8 > len(b):
            break
        size = struct.unpack_from("<i", b, off + 4)[0]
        off += 8
        ts = off
        off += size
        if size <= 0 or b[ts:ts + 4] != b"VAND":
            continue
        pc, vc = struct.unpack_from("<ii", b, ts + 24)
        omb = struct.unpack_from("<i", b, ts + 56)[0]
        vo = ts + 100
        verts = [(lambda x, y, z: (x, -y, -z))(*struct.unpack_from("<fff", b, vo + i * 12)) for i in range(vc)]
        po = vo + vc * 12
        n = min(pc, omb) if omb > 0 else pc
        for i in range(n):
            p = po + i * 32
            nv = b[p + 30]
            if nv < 3:
                continue
            idx = struct.unpack_from("<6H", b, p + 4)
            polys.append([verts[k] for k in idx[:nv]])
    _nav_cache[("polys", path)] = polys
    return polys


def nav_triangles_bytes(path=None):
    import array
    arr = array.array("f")
    for poly in nav_polys(path):
        for i in range(1, len(poly) - 1):
            for v in (poly[0], poly[i], poly[i + 1]):
                arr.extend(v)
    return arr.tobytes()


def nav_polys_with_area(path=None):
    """Same triangulation as nav_polys(), but each polygon also carries its raw dtPoly
    areaAndtype byte (offset 31 of the 32-byte dtPoly record -- area = low 6 bits,
    polyType = top 2 bits, per the standard Recast/Detour dtPoly layout; verified against
    this file's existing p+4/p+30 (verts/vertCount) field offsets, which the FFXI client's
    navmesh already confirms are correct)."""
    path = Path(path or _default_nav())
    if ("polys_area", path) in _nav_cache:
        return _nav_cache[("polys_area", path)]
    b = path.read_bytes()
    assert b[:4] == b"TESM", "not a navmeshset"
    ntiles = struct.unpack_from("<i", b, 8)[0]
    off, polys = 40, []
    for _ in range(ntiles):
        if off + 8 > len(b):
            break
        size = struct.unpack_from("<i", b, off + 4)[0]
        off += 8
        ts = off
        off += size
        if size <= 0 or b[ts:ts + 4] != b"VAND":
            continue
        pc, vc = struct.unpack_from("<ii", b, ts + 24)
        omb = struct.unpack_from("<i", b, ts + 56)[0]
        vo = ts + 100
        verts = [(lambda x, y, z: (x, -y, -z))(*struct.unpack_from("<fff", b, vo + i * 12)) for i in range(vc)]
        po = vo + vc * 12
        n = min(pc, omb) if omb > 0 else pc
        for i in range(n):
            p = po + i * 32
            nv = b[p + 30]
            if nv < 3:
                continue
            idx = struct.unpack_from("<6H", b, p + 4)
            areaAndtype = b[p + 31]
            polys.append(([verts[k] for k in idx[:nv]], areaAndtype & 0x3f, areaAndtype >> 6))
    _nav_cache[("polys_area", path)] = polys
    return polys


def nav_triangle_meta_bytes(path=None):
    """Per-triangle metadata parallel to nav_triangles_bytes()'s triangle order: for each
    triangle, (yMin, yMax, area, polyType) as 4 float32s. yMin/yMax are the real min/max Y
    (already sign-flipped to FFXI world coords) across that triangle's *source polygon*
    vertices -- i.e. the vertical band the polygon occupies, not a guess."""
    import array
    arr = array.array("f")
    for poly, area, ptype in nav_polys_with_area(path):
        ys = [v[1] for v in poly]
        ymin, ymax = min(ys), max(ys)
        for i in range(1, len(poly) - 1):
            arr.extend((ymin, ymax, float(area), float(ptype)))
    return arr.tobytes()


def _components(path=None):
    """Weld vertices, union polys that share an edge. Returns (poly->comp, spatial grid)."""
    path = Path(path or _default_nav())
    if ("comp", path) in _nav_cache:
        return _nav_cache[("comp", path)]
    polys = nav_polys(path)
    parent = list(range(len(polys)))

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    q = lambda v: (round(v[0] * 10), round(v[1] * 4), round(v[2] * 10))
    edges = {}
    for pi, poly in enumerate(polys):
        n = len(poly)
        for i in range(n):
            a, b = q(poly[i]), q(poly[(i + 1) % n])
            key = (a, b) if a < b else (b, a)
            if key in edges:
                ra, rb = find(edges[key]), find(pi)
                if ra != rb:
                    parent[ra] = rb
            else:
                edges[key] = pi
    comp = [find(i) for i in range(len(polys))]
    grid = {}
    C = 8.0
    for pi, poly in enumerate(polys):
        xs, zs = [v[0] for v in poly], [v[2] for v in poly]
        for gx in range(int(min(xs) // C), int(max(xs) // C) + 1):
            for gz in range(int(min(zs) // C), int(max(zs) // C) + 1):
                grid.setdefault((gx, gz), []).append(pi)
    _nav_cache[("comp", path)] = (comp, grid, C)
    return _nav_cache[("comp", path)]


def _in_poly(x, z, poly):
    inside = False
    n = len(poly)
    j = n - 1
    for i in range(n):
        xi, zi, xj, zj = poly[i][0], poly[i][2], poly[j][0], poly[j][2]
        if (zi > z) != (zj > z) and x < (xj - xi) * (z - zi) / (zj - zi + 1e-12) + xi:
            inside = not inside
        j = i
    return inside


def _closest_point_triangle(p, a, b, c):
    """Closest point on triangle ABC to point P (Real-Time Collision Detection region tests)."""
    px, py, pz = p
    ax, ay, az = a
    bx, by, bz = b
    cx, cy, cz = c
    ab = (bx - ax, by - ay, bz - az)
    ac = (cx - ax, cy - ay, cz - az)
    ap = (px - ax, py - ay, pz - az)
    d1 = sum(ab[i] * ap[i] for i in range(3))
    d2 = sum(ac[i] * ap[i] for i in range(3))
    if d1 <= 0 and d2 <= 0:
        return a
    bp = (px - bx, py - by, pz - bz)
    d3 = sum(ab[i] * bp[i] for i in range(3))
    d4 = sum(ac[i] * bp[i] for i in range(3))
    if d3 >= 0 and d4 <= d3:
        return b
    vc = d1 * d4 - d3 * d2
    if vc <= 0 and d1 >= 0 and d3 <= 0:
        v = d1 / (d1 - d3)
        return tuple(a[i] + v * ab[i] for i in range(3))
    cp = (px - cx, py - cy, pz - cz)
    d5 = sum(ab[i] * cp[i] for i in range(3))
    d6 = sum(ac[i] * cp[i] for i in range(3))
    if d6 >= 0 and d5 <= d6:
        return c
    vb = d5 * d2 - d1 * d6
    if vb <= 0 and d2 >= 0 and d6 <= 0:
        w = d2 / (d2 - d6)
        return tuple(a[i] + w * ac[i] for i in range(3))
    va = d3 * d6 - d5 * d4
    if va <= 0 and (d4 - d3) >= 0 and (d5 - d6) >= 0:
        bc = (cx - bx, cy - by, cz - bz)
        w = (d4 - d3) / ((d4 - d3) + (d5 - d6))
        return tuple(b[i] + w * bc[i] for i in range(3))
    denom = 1.0 / (va + vb + vc)
    v = vb * denom
    w = vc * denom
    return tuple(a[i] + ab[i] * v + ac[i] * w for i in range(3))


def point_diagnostics(x, y, z, path=None):
    """Exact nearest nav polygon/triangle diagnostics for an FFXI world-space point."""
    path = Path(path or _default_nav())
    polys_area = nav_polys_with_area(path)
    comp, _, _ = _components(path)
    p = (float(x), float(y), float(z))
    best = None
    best_d2 = float("inf")
    for pi, (poly, area, ptype) in enumerate(polys_area):
        for ti in range(1, len(poly) - 1):
            q = _closest_point_triangle(p, poly[0], poly[ti], poly[ti + 1])
            d2 = sum((q[i] - p[i]) ** 2 for i in range(3))
            if d2 < best_d2:
                best_d2 = d2
                best = (pi, ti - 1, poly, area, ptype, q)
    if best is None:
        return None
    pi, tri, poly, area, ptype, q = best
    xs = [v[0] for v in poly]
    ys = [v[1] for v in poly]
    zs = [v[2] for v in poly]
    return {
        "polygon": pi,
        "triangle": tri,
        "component": comp[pi],
        "distance": best_d2 ** 0.5,
        "nearest": {"x": q[0], "y": q[1], "z": q[2]},
        "bounds": {
            "xmin": min(xs), "xmax": max(xs),
            "ymin": min(ys), "ymax": max(ys),
            "zmin": min(zs), "zmax": max(zs),
        },
        "area": area,
        "poly_type": ptype,
        "placement_valid": locate(x, y, z, path) is not None,
    }


def locate(x, y, z, path=None):
    """Component id of the navmesh polygon under (x,z) closest in height to y, else None."""
    comp, grid, C = _components(path)
    polys = nav_polys(path)
    best, bd = None, 1e9
    for pi in grid.get((int(x // C), int(z // C)), []):
        poly = polys[pi]
        if _in_poly(x, z, poly):
            d = abs(sum(v[1] for v in poly) / len(poly) - y)
            if d < bd:
                best, bd = pi, d
    if best is None or bd > 6:
        return None
    return comp[best]


def reachability():
    """{layout: {"entrance_comp": c, "points": [comp,...], "lamps": [comp,...]}} + summary flags."""
    d = load_data()
    out = {}
    for lay, ent in d["entrances"].items():
        if lay == 0:
            continue
        ec = locate(*ent)
        pts = [locate(*p) for p in d["points"].get(lay, [])]
        lps = [locate(*p) for p in d["lamps"].get(lay, [])]
        f = lambda cs: ["ok" if c is not None and c == ec else ("off" if c is None else "blocked") for c in cs]
        out[lay] = {"entrance": ec, "points": f(pts), "lamps": f(lps)}
    return out


def load_exclusions():
    try:
        return json.loads(EXCL_FILE.read_text())
    except Exception:
        return {"points": {}, "lamps": {}}


def save_exclusions(obj):
    EXCL_FILE.parent.mkdir(exist_ok=True)
    EXCL_FILE.write_text(json.dumps(obj, indent=1))


def _poly_locate(x, y, z, path):
    comp, grid, C = _components(path)
    polys = nav_polys(path)
    best, bd = None, 1e9
    for pi in grid.get((int(x // C), int(z // C)), []):
        poly = polys[pi]
        if _in_poly(x, z, poly):
            d = abs(sum(v[1] for v in poly) / len(poly) - y)
            if d < bd:
                best, bd = pi, d
    return best if best is not None and bd <= 6 else None


def nav_route(a, b, path=None):
    """A* across navmesh polygons between world points a and b (x,y,z).
    Returns {"ok", "points": [[x,y,z]..], "length"} ; ok False with a reason when unreachable."""
    import heapq
    path = Path(path or _default_nav())
    polys = nav_polys(path)
    if ("adj", path) not in _nav_cache:
        q = lambda v: (round(v[0] * 10), round(v[1] * 4), round(v[2] * 10))
        edges, adj = {}, {}
        for pi, poly in enumerate(polys):
            n = len(poly)
            for i in range(n):
                k1, k2 = q(poly[i]), q(poly[(i + 1) % n])
                key = (k1, k2) if k1 < k2 else (k2, k1)
                mid = tuple((poly[i][j] + poly[(i + 1) % n][j]) / 2 for j in range(3))
                if key in edges:
                    pj, _m = edges[key]
                    adj.setdefault(pi, []).append((pj, mid))
                    adj.setdefault(pj, []).append((pi, mid))
                else:
                    edges[key] = (pi, mid)
        cen = [tuple(sum(v[j] for v in p) / len(p) for j in range(3)) for p in polys]
        _nav_cache[("adj", path)] = (adj, cen)
    adj, cen = _nav_cache[("adj", path)]
    sa, sb = _poly_locate(*a, path), _poly_locate(*b, path)
    if sa is None or sb is None:
        return {"ok": False, "reason": "point is off the navmesh"}
    d3 = lambda p, q_: math.dist(p, q_)
    # nodes are (poly) entered through an edge midpoint; state = poly, position = entry midpoint
    start = tuple(a)
    goal = tuple(b)
    best = {sa: 0.0}
    pos = {sa: start}
    prev = {}
    heap = [(d3(start, goal), sa)]
    done = set()
    while heap:
        _f, pi = heapq.heappop(heap)
        if pi in done:
            continue
        done.add(pi)
        if pi == sb:
            break
        for pj, mid in adj.get(pi, []):
            if pj in done:
                continue
            g = best[pi] + d3(pos[pi], mid)
            if g < best.get(pj, 1e18):
                best[pj] = g
                pos[pj] = mid
                prev[pj] = pi
                heapq.heappush(heap, (g + d3(mid, goal), pj))
    if sb not in done:
        return {"ok": False, "reason": "no navmesh route (different walkable areas)"}
    chain = [sb]
    while chain[-1] in prev:
        chain.append(prev[chain[-1]])
    chain.reverse()
    pts = [list(start)] + [list(pos[p]) for p in chain[1:]] + [list(goal)]
    length = sum(d3(pts[i], pts[i + 1]) for i in range(len(pts) - 1))
    return {"ok": True, "points": pts, "length": length}


# Install named-server/modern-LSB routing onto this packaged backend after the legacy
# functions are defined. The bridge imports this module and replaces only the profile-sensitive
# hooks, so importing the canonical module directly now has the same behavior the retired root
# compatibility launcher previously established.
from workbench.devtools.domains import _nyzul_profile_bridge as _profile_bridge  # noqa: E402,F401
