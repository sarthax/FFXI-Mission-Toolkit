"""Binary zone mesh (.zmesh): welded float32 positions + uint32 triangle indices, little-endian.
Layout: b'ZMS1' | u32 nverts | u32 ntris | f32[nverts*3] (raw OBJ coords, viewer applies nothing) | u32[ntris*3].
Built from the cached OBJ (build_zone_visual_cache.py); the viewer makes normals client-side.
  py -3 zmesh.py <zid|--all>"""
import array
import struct
import sys
from pathlib import Path

DIR = Path(__file__).parent / "gui" / "static" / "zone_visual"


# LOD = minimum triangle extent (world units) to keep; smaller triangles (props, trim, clutter) are dropped.
LODS = {0: 0.0, 1: 0.75, 2: 1.5, 3: 3.0}


def convert(zid, force=False, lod=0):
    if lod:
        return _lod(zid, lod)
    src, dst = DIR / f"{zid}.obj", DIR / f"{zid}.zmesh"
    if not src.exists():
        return None
    if dst.exists() and not force and dst.stat().st_mtime >= src.stat().st_mtime:
        return dst
    weld, pos, remap, idx = {}, array.array("f"), [], array.array("I")
    with src.open("r", encoding="ascii", errors="replace") as f:
        for line in f:
            if line[:2] == "v ":
                key = line[2:].strip()
                i = weld.get(key)
                if i is None:
                    i = weld[key] = len(weld)
                    pos.extend(map(float, key.split()))
                remap.append(i)
            elif line[:2] == "f ":
                p = [remap[int(t.split("/")[0]) - 1] for t in line[2:].split()]
                for k in range(1, len(p) - 1):
                    if p[0] != p[k] and p[k] != p[k + 1] and p[0] != p[k + 1]:
                        idx.extend((p[0], p[k], p[k + 1]))
    tmp = dst.with_suffix(".tmp")
    with tmp.open("wb") as o:
        o.write(b"ZMS1" + struct.pack("<II", len(pos) // 3, len(idx) // 3))
        pos.tofile(o)
        idx.tofile(o)
    tmp.replace(dst)
    return dst


def _lod(zid, lod):
    base = convert(zid)
    if not base:
        return None
    dst = DIR / f"{zid}.lod{lod}.zmesh"
    if dst.exists() and dst.stat().st_mtime >= base.stat().st_mtime:
        return dst
    thr = LODS[lod]
    b = base.read_bytes()
    nv, nt = struct.unpack_from("<II", b, 4)
    pos = array.array("f"); pos.frombytes(b[12:12 + nv * 12])
    idx = array.array("I"); idx.frombytes(b[12 + nv * 12:12 + nv * 12 + nt * 12])
    keep, remap, npos, nidx = {}, {}, array.array("f"), array.array("I")
    for t in range(0, len(idx), 3):
        a, c, d = idx[t] * 3, idx[t + 1] * 3, idx[t + 2] * 3
        ext = 0.0
        for k in range(3):
            lo = min(pos[a + k], pos[c + k], pos[d + k]); hi = max(pos[a + k], pos[c + k], pos[d + k])
            ext = max(ext, hi - lo)
        if ext < thr:
            continue
        for v in (idx[t], idx[t + 1], idx[t + 2]):
            n = remap.get(v)
            if n is None:
                n = remap[v] = len(remap)
                npos.extend(pos[v * 3:v * 3 + 3])
            nidx.append(n)
    with dst.open("wb") as o:
        o.write(b"ZMS1" + struct.pack("<II", len(npos) // 3, len(nidx) // 3))
        npos.tofile(o); nidx.tofile(o)
    return dst


if __name__ == "__main__":
    ids = [p.stem for p in DIR.glob("*.obj")] if sys.argv[1:] == ["--all"] else sys.argv[1:]
    for z in ids:
        d = convert(z, True)
        print(z, d and f"{(DIR / f'{z}.obj').stat().st_size >> 20} MB obj -> {d.stat().st_size >> 20} MB zmesh")
