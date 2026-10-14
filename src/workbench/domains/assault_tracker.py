"""Assault issue tracking from the preserved Topaz release source.

Topaz status is historical, not proof of DSP implementation or validation.
"""
from __future__ import annotations
import re
from pathlib import Path

TRACKER = Path(__file__).resolve().parents[3] / "data" / "assault" / "Assault_Issue_Tracker_topaz_release.md"
ZONES = ("Leujaoam Sanctum", "Mamool Ja Training Grounds", "Lebros Cavern", "Periqia", "Ilrusi Atoll")
RANKS = ("PSC", "PFC", "SP", "LC", "C", "S", "SM", "CS", "SL", "FL")
MISSION_RE = re.compile(r"^### (.+?) \((.+?), mission (\d+)\)\s*$", re.M)
SECTION_RE = re.compile(r"^## (.+)$", re.M)
STATUS_RE = re.compile(r"\*\*Overall status:\s*([^*\n]+)", re.I)
SYMBOLS = ("✅", "🟢", "🟡", "🔴")


def overview():
    source = TRACKER.read_text(encoding="utf-8")
    sections = list(SECTION_RE.finditer(source))
    shared = []
    for i, match in enumerate(sections):
        label = match.group(1)
        if label.startswith(("Status grid", "PSC ", "PFC ", "SP ", "LC ", "C ", "S ", "SM ", "CS ", "SL ", "FL ", "How to use")):
            continue
        end = sections[i + 1].start() if i + 1 < len(sections) else len(source)
        shared.append({"title": label, "comments": source[match.end():end].strip()})
    missions = []
    found = list(MISSION_RE.finditer(source))
    for i, match in enumerate(found):
        title, zone, number = match.group(1), match.group(2), int(match.group(3))
        end = found[i+1].start() if i+1<len(found) else len(source)
        next_section = source.find("\n## ", match.end())
        if next_section >= 0:
            end = min(end, next_section)
        comments = source[match.end():end].strip()
        overall = STATUS_RE.search(comments)
        marker = next((s for s in SYMBOLS if overall and s in overall.group(1)), "❔")
        rank_index = (number - 1) % 10
        missions.append({
            "number": number, "name": title, "zone": zone,
            "rank": RANKS[rank_index], "topaz_status": marker,
            "topaz_status_text": overall.group(1).strip() if overall else "Not specified",
            "comments": comments,
            "topaz_reference": f"https://github.com/sarthax/Topaz-to-Valhalla/blob/release/documentation/Assault_Issue_Tracker.md",
            "dsp_implementation": "unverified",
            "dsp_port": "pending_review" if rank_index >= 4 else "unverified",
            "dsp_validation": "not_verified",
        })
    missions.sort(key=lambda m:m["number"])
    return {"zones": ZONES, "ranks": RANKS, "missions": missions,
            "shared": shared, "count": len(missions),
            "source_file": str(TRACKER.relative_to(TRACKER.parents[3])),
            "note": "Topaz historical completion does not establish DSP port or validation."}
