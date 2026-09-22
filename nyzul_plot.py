"""Nyzul Isle plot tool backend: parses the DSP Lua spawn data + Nyzul_Isle.nav (pure Python)
and computes per-layout reachability (connected components of the navmesh from each entrance).
Everything is read live from the DSP repo so re-running picks up edits."""
import json
import math
import re
import struct
from pathlib import Path

DSP = Path(r"D:\Claude\dsp-fresh")
FLOOR_LAYOUTS = DSP / "scripts/globals/nyzul/floor_layouts.lua"
NYZUL_LUA = DSP / "scripts/globals/nyzul.lua"
IDS_LUA = DSP / "scripts/zones/Nyzul_Isle/IDs.lua"
NAV = DSP / "navmeshes/Nyzul_Isle.nav"
EXCL_FILE = Path(__file__).parent / "data" / "nyzul_exclusions.json"

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
    fl = FLOOR_LAYOUTS.read_text(encoding="utf-8", errors="replace")
    lamp_blk = _block(fl, r"(?m)^Nyzul\.lampSpawnPoints\s*=")
    lay_blk = _block(fl, r"(?m)^Nyzul\.layoutSpawnPoints\s*=")
    lamps = _per_layout(lamp_blk, r"\{\s*" + NUM + r"\s*,\s*" + NUM + r"\s*,\s*" + NUM + r"\s*\}")
    points = _per_layout(lay_blk, r"x\s*=\s*" + NUM + r"\s*,\s*y\s*=\s*" + NUM + r"\s*,\s*z\s*=\s*" + NUM)

    nz = NYZUL_LUA.read_text(encoding="utf-8", errors="replace")
    ent = {}
    for m in re.finditer(r"\[\s*(\d+)\]\s*=\s*\{\s*" + NUM + r",\s*" + NUM + r",\s*" + NUM + r"\s*\}", _block(nz, r"Nyzul\.FloorLayout\s*=")):
        ent[int(m.group(1))] = [float(m.group(2)), float(m.group(3)), float(m.group(4))]

    ids = IDS_LUA.read_text(encoding="utf-8", errors="replace")
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
    path = Path(path or NAV)
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


def _components(path=None):
    """Weld vertices, union polys that share an edge. Returns (poly->comp, spatial grid)."""
    path = Path(path or NAV)
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
