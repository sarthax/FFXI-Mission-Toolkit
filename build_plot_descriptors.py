"""Builds plot_descriptors/*.json (data-driven spawn mechanics for the Zone Plot page) from the DSP
Lua sources, so re-running after Lua edits refreshes them. Descriptor ops (see zone_plot.html):
  regionDraw  - regions of candidate points; `always` regions each place one chest, then `random`
                more regions are drawn (shuffled, without replacement), one random point per region.
  markOne     - pick one of the placements made by an earlier op (e.g. the Figurehead chest).
  spawnIds    - fixed spawns looked up by id from the zone's rows (positions come from the DB).
  groupChoice - pick one of several id-range groups to spawn (all positions from DB rows)."""
import json, re
from pathlib import Path

import settings

_dsp_root = settings.get_dsp_root()
if _dsp_root is None:
    raise SystemExit("DSP server path isn't configured yet -- set it on the Settings page first")
Z = _dsp_root / "scripts/zones"
OUT = Path(__file__).parent / "plot_descriptors"
OUT.mkdir(exist_ok=True)
NUM = r"(-?\d+(?:\.\d+)?)"


def golden_salvage():
    s = (Z / "Ilrusi_Atoll/GoldenSalvageData.lua").read_text(encoding="utf-8")
    rb = s[s.index("regions = {"):]
    regions = []
    for m in re.finditer(r"--\s*Region\s+(\d+):\s*([^\n(]*?)\s*(?:\((\d+) points?\))?(?:\s*-\s*BOAT CHEST)?\n\s*\{(.*?)\n\s*\},", rb, re.S):
        pts = [[float(a), float(b), float(c)] for a, b, c in re.findall(r"x\s*=\s*" + NUM + r",\s*y\s*=\s*" + NUM + r",\s*z\s*=\s*" + NUM, m.group(4))]
        regions.append({"id": int(m.group(1)), "name": m.group(2).strip(), "points": pts})
    boat = [int(x) for x in re.search(r"boatChestRegions\s*=\s*\{([^}]*)\}", s).group(1).split(",") if x.strip()]
    chest_ids = [int(x) for x in re.search(r"chestIds\s*=\s*\{([^}]*)\}", s, re.S).group(1).replace("\n", " ").split(",") if x.strip()]
    for r in regions:
        r["always"] = r["id"] in boat
    g = (Z / "Ilrusi_Atoll/instances/golden_salvage.lua").read_text(encoding="utf-8")
    fish = [int(x) for x in re.search(r"PERCIPIENT_FISH\s*=\s*\{([^}]*)\}", g).group(1).split(",") if x.strip()]
    return {
        "id": "golden_salvage", "zone": 55, "title": "Golden Salvage (Ilrusi Atoll) - chest placement",
        "source": "scripts/zones/Ilrusi_Atoll/GoldenSalvageData.lua + instances/golden_salvage.lua",
        "notes": "4 boat regions always spawn, 8 more regions drawn at random (one random point each); one placed chest holds the Figurehead; the rest are Mimics.",
        "ops": [
            {"op": "regionDraw", "label": "Chest", "regions": regions, "random": 8, "ids": chest_ids},
            {"op": "markOne", "label": "FIGUREHEAD", "from": "Chest"},
            {"op": "spawnIds", "label": "Percipient Fish", "ids": fish},
        ],
    }


def arrapago():
    s = (Z / "Arrapago_Remnants/IDs.lua").read_text(encoding="utf-8")
    st = re.search(r"\[1\]\s*=\s*\{\s*\[2\]\s*=\s*\{\s*mobs_start\s*=\s*(\d+),\s*mobs_end\s*=\s*(\d+),\s*rampart\s*=\s*(\d+),\s*sabotender\s*=\s*(\d+)", s)
    blk = s[s.index("[2] = {", st.end()):]
    groups = [{"name": f"Region {k} group", "from": int(a), "to": int(b)} for k, a, b in
              re.findall(r"\[(\d)\]\s*=\s*\{\s*mobs_start\s*=\s*(\d+),\s*mobs_end\s*=\s*(\d+)", blk)]
    groups.sort(key=lambda g: g["name"])
    astro = int(re.search(r"astrologer\s*=\s*(\d+)", blk).group(1))
    zone = ((int(st.group(1)) - 16777216) >> 12) & 511
    return {
        "id": "arrapago_remnants", "zone": zone, "title": "Arrapago Remnants - stage 1 mobs + region-triggered group",
        "source": "scripts/zones/Arrapago_Remnants/IDs.lua + instances/arrapago_remnants.lua",
        "notes": "Stage 1 (fixed) = mobs_start..mobs_end plus rampart and sabotender. One region group is spawned by the region event that fires (not a random draw); astrologer is a fixed spawn.",
        "ops": [
            {"op": "spawnIds", "label": "Stage1", "ranges": [[int(st.group(1)), int(st.group(2))]], "ids": [int(st.group(3)), int(st.group(4))]},
            {"op": "groupChoice", "label": "Region group", "groups": groups},
            {"op": "spawnIds", "label": "Astrologer", "ids": [astro]},
        ],
    }


for d in (golden_salvage(), arrapago()):
    (OUT / f"{d['id']}.json").write_text(json.dumps(d, indent=1))
    print(d["id"], [(o["op"], len(o.get("regions", o.get("groups", o.get("ids", []))))) for o in d["ops"]])
