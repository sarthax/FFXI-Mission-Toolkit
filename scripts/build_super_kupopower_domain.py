"""Builds data/super_kupopower/model.json: Mog Tablets + Super Kupowers (ffxiclopedia [W], LSB skeleton [S], zone ids [D] from
ffxi_zone_database.db). Item ids come only from the DSP item_basic.sql by exact name; anything unmatched stays null. No message/csid ids
are invented: they stay null until a capture or DAT pull supplies them."""
from __future__ import annotations

import datetime
import json
import re
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "super_kupopower"
import os
ITEMS = [Path(p) / "sql" / "item_basic.sql" for p in os.environ.get("DSP_ROOTS", os.environ.get("DSP_ROOT", "")).split(os.pathsep) if p]  # DSP checkout(s)
LSB = os.environ.get("LSB_MOG_TABLETS_LUA", "<LSB scripts/globals/mog_tablets.lua>")

POWERS = [
    ("thrifty_transit", "Thrifty Transit", 1, "Outpost teleport and Survival Guide sites operate free of charge; the Explorer Moogle teleport service appears (Mhaura, Selbina, the three nations).", ["outpost teleport", "survival guide", "explorer moogle"], "zone/global"),
    ("martial_master", "Martial Master", 2, "With Signet, combat, magic and automaton skills increase more quickly.", ["skill-up"], "global"),
    ("blood_of_the_vampyr", "Blood of the Vampyr", 3, "Signet grants latent Regen (1 HP/tick) and Refresh (1 MP/tick) when HP/MP is below 51%. Affects Adventuring Fellows as if they always have Signet.", ["signet", "fellow"], "global"),
    ("treasure_hound", "Treasure Hound", 4, "Signet grants Gilfinder +1 and Treasure Hunter +1.", ["signet"], "global"),
    ("artisans_advantage", "Artisan's Advantage", 5, "Chance of losing ingredients on a failed synthesis is drastically reduced while the crafter has Synthesis Image Support from their guild.", ["synthesis image support"], "global"),
    ("myriad_mystery_boxes", "Myriad Mystery Boxes", 6, "Treasure Caskets appear more often (merged from four regional Mystery Boxes powers in Sept 2012).", ["treasure caskets"], "global"),
    ("dilatory_digestion", "Dilatory Digestion", 7, "Food effects last twice as long.", ["food"], "global"),
    ("boundary_buster", "Boundary Buster", 8, "Conquest Points received from defeating enemies are doubled.", ["conquest"], "global"),
    ("bountiful_bazaar", "Bountiful Bazaar", 9, "All Regional Merchants in the three nations simultaneously open for business.", ["regional merchants"], "zone"),
    ("swift_shoes", "Swift Shoes", 10, "Resting grants a quickening effect; resting longer raises potency and duration. Also affects Adventuring Fellows.", ["resting", "fellow"], "global"),
    ("crystal_caboodle", "Crystal Caboodle", 11, "Crystal drop rate is increased, and crystals can also be obtained from beastmen-controlled regions.", ["crystal drops"], "global"),
]
IMPL = {  # DSP implementation status on feature/mog-tablets-super-kupowers (2026-10-12): (status, how)
    "thrifty_transit": ("partial", "conquest.lua OP_TeleFee free; Explorer Moogles gated by MOG_TABLET_GATE_EXPLORER_MOOGLES (teleports already on Valhalla); Survival Guides absent on Valhalla, separate branch"),
    "martial_master": ("done", "skill-up +25% (MOG_TABLET_SKILLUP_RATE) under Signet"),
    "blood_of_the_vampyr": ("done", "mods 871/872 added in TickRegen when HP/MP < 51%; Fellows not covered"),
    "treasure_hound": ("done", "Signet Gilfinder/TH +1"),
    "artisans_advantage": ("done", "mod 873 in doSynthFail, Advanced image support (power>=3) only, default -20% (JP measurements ~-18%)"),
    "myriad_mystery_boxes": ("done", "caskets.lua"),
    "dilatory_digestion": ("done", "mod 874 FOOD_DURATION, +100% on EFFECT_FOOD in AddStatusEffect"),
    "boundary_buster": ("done", "conquest points doubled"),
    "bountiful_bazaar": ("done", "54 city regional vendor scripts"),
    "swift_shoes": ("partial", "Quickening on resting; Alter Egos/Fellows/Automatons and removal conditions missing"),
    "crystal_caboodle": ("done", "mods 869/870: crystal chance 20%->40%, 10% become clusters"),
}
RETIRED_POWERS = [
    ("Mystery Boxes: San d'Oria", "Sept 2012", "Merged into Myriad Mystery Boxes"), ("Mystery Boxes: Bastok", "Sept 2012", "Merged into Myriad Mystery Boxes"),
    ("Mystery Boxes: Windurst", "Sept 2012", "Merged into Myriad Mystery Boxes"), ("Mystery Boxes: Frontier Lands", "Sept 2012", "Merged into Myriad Mystery Boxes"),
    ("Ease of Exploration", "June 2014", "Explorer Moogle teleport service; merged into Thrifty Transit"),
]
# LSB tablet enum: TEMPERANCE=0 ... COURAGE=10. wiki: tablet -> (current reward, [(era, reward)...])
TABLETS = [
    ("temperance", "Temperance", 0, "Nomad Moogle Statue", [("2009-05..2015-08", "Nomad Moogle Statue")]),
    ("fortitude", "Fortitude", 1, "Talaria", [("2009-05..2015-08", "Talaria")]),
    ("piety", "Piety", 2, "Kupon I-Orche", [("2009-05..2013-03", "Bloodwood Log"), ("2013-03..2014-05", "Urunday Log"), ("2014-05..2015-08", "Beetle Blood")]),
    ("justice", "Justice", 3, "Macrocosmic Orb", [("2009-05..2013-03", "Noble's Bed"), ("2013-03..2014-05", "Themis Orb"), ("2014-05..2015-08", "Macrocosmic Orb")]),
    ("hope", "Hope", 4, "Nomad Moogle Rod", [("2009-05..2013-03", "Bookshelf"), ("2013-03..2014-05", "Redeyes"), ("2014-05..2015-08", "Nomad Moogle Rod")]),
    ("wisdom", "Wisdom", 5, "Moogle's Largesse", [("2009-05..2013-03", "Coffee Table"), ("2013-03..2015-08", "Moogle's Largesse")]),
    ("compassion", "Compassion", 6, "Invisible Ring", [("2009-05..2013-03", "Adaman Ingot"), ("2013-03..2014-05", "Damascus Ingot"), ("2014-05..2015-08", "Damascene Cloth")]),
    ("dignity", "Dignity", 7, "Sneak Ring", [("2009-05..2013-03", "Orichalcum Ore"), ("2013-03..2014-05", "Vanadium Ore"), ("2014-05..2015-08", "Malboro Fiber")]),
    ("loyalty", "Loyalty", 8, "Deodorize Ring", [("2009-05..2013-03", "Scintillant Ingot"), ("2013-03..2014-05", "Palladian Brass Ingot"), ("2014-05..2015-08", "Oxblood")]),
    ("charity", "Charity", 9, "Reraise Ring", [("2009-05..2013-03", "Opaline Dress"), ("2013-03..2015-08", "Dragon Meat")]),
    ("courage", "Courage", 10, "Pelican Ring", [("2009-05..2013-03", "Argent Coat (females: Vile Elixir +1)"), ("2013-03..2015-08", "Vile Elixir +1")]),
]
NOTE_TABLET_ENUM = ("LSB enum index 0..10 is the order in mog_tablets.lua [S]; it is NOT claimed to be the retail tablet order. "
                    "Wiki names the reward per tablet; the mapping to LSB indices is by name only and is unverified.")
NPCS = [
    {"id": "kupofried", "name": "King Kupofried", "role": "Quest giver / announces the Kupowers. Placed in Walk of Echoes.", "zone": None, "dsp_npcid": 17339258, "status": "partial",
     "note": "DSP npc_list row 17339258 is the candidate from the earlier audit; its zone and name text are NOT yet verified. Check zone_id encoding (bits 12-23) before relying on it."},
    {"id": "explorer_moogle", "name": "Explorer Moogle", "role": "Ru'Lude Gardens. Hands out Kupofried's Ring + the tablet's second reward; also the Thrifty Transit teleport service (Mhaura/Selbina/3 nations).", "zone": 243, "dsp_npcid": None, "status": "not built",
     "note": "LSB has scripts/zones/RuLude_Gardens/npcs/Explorer_Moogle.lua [S] (stub). Zone 243 is the retail Ru'Lude Gardens id, confirm in zones table."},
    {"id": "mog_tablet", "name": "Mog Tablet (prop)", "role": "Hidden prop. Spawns when a player is within ~87 yalms; targetable 2-3 s after; widescan after first spawn. 11 per cycle, one per tablet type.", "zone": None, "dsp_npcid": None, "status": "not built",
     "note": "Needs one npc_list row per tablet per zone. Ids must be allocated with the zone-id encoding (targid < 0x400) - do not invent."},
    {"id": "regional_merchants", "name": "Regional Merchants (3 nations)", "role": "Bountiful Bazaar: all open for business simultaneously.", "zone": None, "dsp_npcid": None, "status": "not built", "note": "Hook into the regional vendor scripts; scope not yet audited."},
    {"id": "outpost_survival", "name": "Outpost teleporters / Survival Guides", "role": "Thrifty Transit: free of charge.", "zone": None, "dsp_npcid": None, "status": "not built", "note": "Gil cost check in outpost teleport + survival guide scripts."},
]
KUPOFRIED_RING = {"id": "kupofrieds_ring", "name": "Kupofried's Ring", "role": "Primary reward for each tablet found; given with the secondary reward by the Explorer Moogle.", "item_id": None}
GLOBALS = [
    ("cycle", "Cycle", "All 11 tablets must be discovered; then the 3 random powers last 1 week (all 11 during Adventurer Appreciation Campaigns). After that, the tablets scatter again and become findable after a random 8-24 h. Each World has its own start time.", "global state"),
    ("announce", "Discovery announce", "A message is shown to every player in affected areas when a tablet is found; another when the Kupowers fade and the tablets spread. Entering an affected zone shows a chat message listing active powers.", "zone-in + broadcast"),
    ("claim", "Reward claim", "Reward claim persists until the Kupowers wear off (1 week). Delay between discovery and being able to claim. If a reward item is NoTrade/rare and already held, the Moogle blocks both until it is discarded.", "explorer moogle"),
    ("zones", "Affected areas", "Original FFXI, Rise of the Zilart and Chains of Promathia areas. Excluded: Dynamis, Tu'Lia, Lumoria, Promyvion, Abdhaljs, Halls of Transference, airship and ferry routes.", "zone filter"),
    ("tablet_zones", "Tablet zones", "29 field zones (list below). Locations per zone below are wiki-reported spots (grid squares), not coordinates.", "per zone"),
]


def item_ids(names):
    found = {}
    for p in ITEMS:
        if not p.exists():
            continue
        txt = p.read_text(encoding="utf-8", errors="replace")
        for n in names:
            if n in found:
                continue
            slug = re.sub(r"[^a-z0-9+-]+", "_", n.lower().replace("'", "")).strip("_")
            m = re.search(r"\((\d+),\s*\d+,\s*'%s'" % re.escape(slug), txt)
            if m:
                found[n] = {"id": int(m.group(1)), "src": p.name}
    return found


def spots():
    zones = {}
    cur = None
    for ln in (OUT / "wiki_spots.txt").read_text(encoding="utf-8").splitlines():
        if ln.startswith("#") and not ln.startswith("##"):
            continue
        if ln.startswith("##"):
            cur = int(ln[2:].strip())
            zones[cur] = []
        elif ln.strip() and cur is not None:
            g, _, n = ln.partition("|")
            zones[cur].append({"grid": g.strip(), "wiki": n.strip()})
    return zones


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    sp = spots()
    con = sqlite3.connect(str(ROOT / "ffxi_zone_database.db"))
    names = dict(con.execute("select zoneid,name from zones where zoneid in (%s)" % ",".join(str(z) for z in sp)).fetchall())
    ru = con.execute("select zoneid,name from zones where name like 'RULUDE%'").fetchall()
    con.close()
    zones = []
    for zid, rows in sp.items():
        for i, r in enumerate(rows, 1):
            r["id"] = "%d-%d" % (zid, i)
        zones.append({"zoneid": zid, "name": names.get(zid, "?"), "wiki_spots": rows})
    allnames = sorted({t[3] for t in TABLETS} | {x[1] for t in TABLETS for x in t[4]} | {"Kupofried's Ring"})
    ids = item_ids(allnames)
    for n in NPCS:
        if n["id"] == "explorer_moogle" and ru:
            n["zone_candidates"] = ru
    d = {
        "generated": datetime.date.today().isoformat(),
        "sources": {"W": "https://ffxiclopedia.fandom.com/wiki/Mog-Tablet and /wiki/Category:Super_Kupowers (read 2026-10-12)", "S": LSB, "D": "ffxi_zone_database.db (zone ids)", "items": [p.name for p in ITEMS if p.exists()]},
        "powers": [{"id": a, "name": b, "lsb_power": c, "effect": e, "touches": f, "scope": g, "impl": IMPL.get(a, ("not built", ""))[0], "impl_note": IMPL.get(a, ("", ""))[1]} for a, b, c, e, f, g in POWERS],
        "retired_powers": [{"name": a, "when": b, "fate": c} for a, b, c in RETIRED_POWERS],
        "tablets": [{"id": a, "name": "Tablet of " + b, "lsb_index": c, "reward": d_, "reward_item": ids.get(d_), "history": [{"era": e, "reward": r, "item": ids.get(r)} for e, r in h]} for a, b, c, d_, h in TABLETS],
        "tablet_note": NOTE_TABLET_ENUM,
        "kupofried_ring": dict(KUPOFRIED_RING, item=ids.get("Kupofried's Ring")),
        "npcs": NPCS,
        "globals": [{"id": a, "label": b, "detail": c, "hook": e} for a, b, c, e in GLOBALS],
        "zones": zones,
        "missing_items": [n for n in allnames if n not in ids],
    }
    (OUT / "model.json").write_text(json.dumps(d, indent=1, ensure_ascii=False), encoding="utf-8")
    print("zones", len(zones), "spots", sum(len(z["wiki_spots"]) for z in zones), "items found", len(ids), "missing", d["missing_items"])


if __name__ == "__main__":
    main()
