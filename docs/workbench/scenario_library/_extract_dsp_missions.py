"""Read-only extraction of nation rank 1-2 mission facts from DSP main NPC scripts. Non-executing."""
import json
import os
import re
import subprocess
import sys

PIN = "febdc00209"  # immutable DSP revision this snapshot is pinned to
REPO = os.environ.get("DSP_REPO") or (sys.argv[1] if len(sys.argv) > 1 else None)
if not REPO:
    sys.exit("usage: _extract_dsp_missions.py <dsp-repo-path> (or set DSP_REPO)")
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dsp_mission_extract.json")
ZONE_IDS = {}
# nation index, mission number, DSP constant (scripts/globals/missions.lua on main)
MISSIONS = [
    (0, 0, "SMASH_THE_ORCISH_SCOUTS"), (0, 1, "BAT_HUNT"), (0, 2, "SAVE_THE_CHILDREN"), (0, 3, "THE_RESCUE_DRILL"), (0, 4, "THE_DAVOI_REPORT"),
    (1, 0, "THE_ZERUHN_REPORT"), (1, 1, "GEOLOGICAL_SURVEY"), (1, 2, "FETICHISM"), (1, 3, "THE_CRYSTAL_LINE"), (1, 4, "WADING_BEASTS"),
    (2, 0, "THE_HORUTOTO_RUINS_EXPERIMENT"), (2, 1, "THE_HEART_OF_THE_MATTER"), (2, 2, "THE_PRICE_OF_PEACE"), (2, 3, "LOST_FOR_WORDS"), (2, 4, "A_TESTING_TIME"),
]


def git(*a):
    return subprocess.run(["git", "-C", REPO, *a], capture_output=True, text=True, encoding="utf-8", errors="replace").stdout


commit = git("rev-parse", "--short=10", PIN).strip()
if commit != PIN:
    sys.exit("refusing to regenerate: %s resolves to %r, expected pinned %s" % (REPO, commit, PIN))
npc_sql = git("show", PIN + ":sql/npc_list.sql")
for zm in re.finditer(r"INSERT INTO `zone_settings` VALUES \((\d+),\d+,'[^']*',\d+,'([^']*)'", git("show", PIN + ":sql/zone_settings.sql")):
    ZONE_IDS[zm.group(2)] = int(zm.group(1))
rows = {}
for m in re.finditer(r"VALUES \((\d+),'([^']*)','([^']*)',(-?\d+),(-?[\d.]+),(-?[\d.]+),(-?[\d.]+)", npc_sql):
    rows.setdefault(m.group(2), []).append((int(m.group(1)), m.group(5), m.group(6), m.group(7)))


def zone_of(i):
    return ((i - 0x1000000) >> 12) & 0xFFF


out = {}
for nation, num, const in MISSIONS:
    hits = git("grep", "-l", r"\b%s\b" % const, PIN, "--", "scripts/zones").splitlines()
    npcs = []
    for h in hits:
        m = re.match(r"%s:scripts/zones" % PIN + r"/([^/]+)/npcs/([^/]+)\.lua$", h)
        if not m:
            continue
        zdir, name = m.groups()
        src = git("show", h)
        if not re.search(r"\b%s\b" % const, src):
            continue
        row = next((r for r in rows.get(name, []) if zone_of(r[0]) == ZONE_IDS.get(zdir)), None)
        npcs.append({"zone_dir": zdir, "zone_id": ZONE_IDS.get(zdir), "npc": name, "path": "scripts/zones/%s/npcs/%s.lua" % (zdir, name),
                     "startEvent": sorted(set(re.findall(r"startEvent\(\s*(0x[0-9a-fA-F]+|\d+)", src))),
                     "keyitems": sorted(set(re.findall(r"(?:has|add|del)KeyItem\(\s*(\w+)", src))),
                     "mission_status_sets": sorted(set(re.findall(r"setMissionStatus\([^,]+,\s*(\d+)", src))),
                     "npc_list": row and {"id": row[0], "pos": row[1:]}})
    out["%d_%d_%s" % (nation, num, const)] = {"nation": nation, "number": num, "constant": const, "npcs": npcs}
json.dump({"source": "dsp-branches@main:" + commit, "missions": out}, open(OUT, "w", encoding="utf-8"), indent=1)
print(commit, len(out), "missions")
for k, v in out.items():
    print(k, len(v["npcs"]), [(n["npc"], bool(n["npc_list"])) for n in v["npcs"]][:5])
