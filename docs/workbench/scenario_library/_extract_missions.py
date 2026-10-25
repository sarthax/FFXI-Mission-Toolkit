"""Read-only extraction of mission facts from LSB mission scripts (git-pinned). Non-executing."""
import json
import os
import re
import subprocess
import sys

REPO = r"D:\Claude\landsandboat-latest"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "lsb_mission_extract.json")


def git(*a):
    return subprocess.run(["git", "-C", REPO, *a], capture_output=True, text=True, encoding="utf-8",
                          errors="replace").stdout


commit = git("rev-parse", "--short=10", "HEAD").strip()
files = [f for f in git("ls-tree", "-r", "--name-only", "HEAD", "scripts/missions/").splitlines()
         if re.search(r"scripts/missions/(wotg/(0[1-9]|10)_|sandoria/|bastok/|windurst/)", f)]
out = {}
for f in files:
    src = git("show", "HEAD:" + f)
    lines = src.splitlines()
    title = lines[1].lstrip("- ").strip() if len(lines) > 1 else ""
    sub = lines[2].lstrip("- ").strip() if len(lines) > 2 else ""
    hdr = [l[3:].strip() for l in lines[:14] if l.startswith("-- ") and ("!addmission" in l or "!pos" in l)]
    mid = re.search(r"Mission:new\(([^,]+),\s*([^)]+)\)", src)
    nxt = re.search(r"nextMission\s*=\s*\{\s*([^}]+)\}", src)
    out[f.replace("scripts/missions/", "")] = {
        "title": title, "subtitle": sub, "header": hdr,
        "mission_id": mid and (mid.group(1).strip() + "," + mid.group(2).strip()),
        "next_mission": nxt and nxt.group(1).strip(),
        "zones": sorted(set(re.findall(r"\[xi\.zone\.(\w+)\]", src))),
        "npcs": sorted(set(re.findall(r"\['([^']+)'\]\s*=\s*mission:", src))),
        "events": sorted({int(x) for x in re.findall(r"mission:(?:progressEvent|event|progressCutscene|cutscene)\(\s*(\d+)", src)}),
        "event_finish_ids": sorted({int(x) for x in re.findall(r"\[(\d+)\]\s*=\s*function\(player, csid", src)}),
        "key_items": sorted(set(re.findall(r"xi\.keyItem\.(\w+)", src))),
        "mission_status_sets": sorted(set(re.findall(r"setMissionStatus\([^,]+,\s*(\d+)", src))),
        "items": sorted(set(re.findall(r"xi\.item\.(\w+)", src))),
        "battlefields": sorted(set(re.findall(r"BCNM|battlefield|Battlefield", src)))[:1],
        "reward_gil": re.findall(r"gil\s*=\s*(\d+)", src), "reward_rank_or_cp": re.findall(r"(rankPoints|capacityPoints|title)\s*=\s*([^,\n]+)", src)[:3],
        "lines": len(lines),
    }
json.dump({"source": "LandSandBoat landsandboat-latest@" + commit, "files": out}, open(OUT, "w", encoding="utf-8"), indent=1)
print(commit, len(out), "files")
for k, v in out.items():
    print(k, "|", v["title"], "|", v["header"][:1], "|", len(v["events"]), "ev", v["key_items"][:2])
