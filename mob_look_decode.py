#!/usr/bin/env python3
"""
mob_look_decode.py -- decodes a Topaz mob_pools.modelid / npc_list look blob into a real model
id (for a plain monster) or race+gear ids (for a humanoid-look entity), using Topaz's own C++
struct/enum as ground truth -- not a guess.

Ground truth, read directly from Topaz source (2026-08-31):
    C:\\topaz\\src\\common\\mmo.h            struct look_t (20 bytes):
        u16 size; union { struct { u8 face, race; }; u16 modelid; };
        u16 head, body, hands, legs, feet, main, sub, ranged;
    C:\\topaz\\src\\map\\packets\\entity_update.h   enum MODELTYPE:
        STANDARD=0, EQUIPED=1, DOOR=2, ELEVATOR=3, SHIP=4, UNK_5=5, AUTOMATON=6, CHOCOBO=7
    C:\\topaz\\src\\map\\packets\\entity_update.cpp  CEntityUpdatePacket ctor:
        STANDARD/UNK_5/AUTOMATON -> only 4 bytes sent (size+union as one u32) -- a single flat
            numeric model id, exactly the file_id space model_schedule_dump.py resolves
            (ENTITY_MODEL_OFFSET 98239 + modelid) -- ONE DAT.
        EQUIPED/CHOCOBO -> the FULL 20-byte look_t is sent -- race + 8 per-slot gear ids. This is
            NOT "one DAT with several models inside it" -- there is no single DAT to find. The
            client renders a live composite of the race's base skeleton DAT plus one DAT per
            equipped slot, the same way xi-model-viewer's own PC character composer works
            (mergeModels in ui/js/dat.js). Answers the standing open question directly: for a
            humanoid-look mob/NPC, "the model DAT" does not exist as a single file.
        DOOR/ELEVATOR/SHIP -> `size` field only (not a model at all, these are npc_list props).

`look_t.size` doubles as the MODELTYPE discriminator (first field in the struct) -- read it
before touching the rest.

CONFIRMED 2026-09-21: the raw per-slot value stored/sent for MODEL_EQUIPED/CHOCOBO encodes as
    raw = slot_index * 4096 + model_id
(slot_index: head=1, body=2, hands=3, legs=4, feet=5, main=6, sub=7, ranged=8; raw==0 means
unequipped). `model_id` is NOT a file_id itself -- it's the cumulative per-slot index that
xi-model-viewer's GEAR_TABLES (ported to gear_tables.py) uses to look up the real file_id via
its group tables. Verified end-to-end against a live Topaz-DSP DB row (Laiteconce, npcid
16781339, ElvaanFemale): head=4116 -> model_id=20 -> file_id=16660 -> dat-extractor resolves a
real ROM/42/41.DAT on disk; main=24576 -> model_id=0 -> file_id=17920 -> ROM/43/65.DAT, also
real. See gear_tables.py for the full table + resolver. entity_update.cpp's packet-send code
applies no transform (straight memcpy of look_t), so this raw encoding is exactly what a real
client receives and must already know how to interpret -- confirming it's the genuine scheme,
not a Topaz-specific quirk.

Usage:
    python mob_look_decode.py --hex 0x0000640100000000000000000000000000000000
    python mob_look_decode.py --poolid 649          # looks up sql/mob_pools.sql directly
"""
import argparse
import re
import struct
from pathlib import Path

import gear_tables
import mob_model_tables
import settings

TOPAZ_ROOT = settings.get_topaz_root()
# DISPROVEN 2026-09-22 as a universal monster-model offset (it's a fileId classification
# threshold in xi-model-viewer's own source, dattypes.js:138 -- never an additive offset). Kept
# only as an explicitly-marked-unverified LAST RESORT below for families with no real table entry
# yet in mob_model_tables.py -- never trust a "flat" result with unverified=True.
ENTITY_MODEL_OFFSET = 98239

MODEL_TYPES = {
    0: "MODEL_STANDARD", 1: "MODEL_EQUIPED", 2: "MODEL_DOOR", 3: "MODEL_ELEVATOR",
    4: "MODEL_SHIP", 5: "MODEL_UNK_5", 6: "MODEL_AUTOMATON", 7: "MODEL_CHOCOBO",
}
FLAT_MODEL_TYPES = {0, 5, 6}   # STANDARD, UNK_5, AUTOMATON -> single flat modelid, one DAT
GEAR_MODEL_TYPES = {1, 7}      # EQUIPED, CHOCOBO -> full look_t, race + per-slot gear, multi-DAT

RACE_NAMES = {
    1: "HumeMale", 2: "HumeFemale", 3: "ElvaanMale", 4: "ElvaanFemale",
    5: "TaruMale", 6: "TaruFemale", 7: "Mithra", 8: "Galka",
}


def decode_look_data(blob: bytes, familyid: int | None = None) -> dict:
    """Same real decode as decode_look() below, returning structured data instead of printing --
    for programmatic use (entity_profile.py) rather than CLI output. Kept as a separate function
    rather than refactoring decode_look() itself, to avoid any risk of changing that function's
    already-correct, already-used CLI print behavior.

    familyid (mob_pools.familyid, when known -- NPCs don't have one) is used to look up a real,
    per-family-verified modelid->file_id table (mob_model_tables.py) instead of the disproven
    universal ENTITY_MODEL_OFFSET formula. If the family has no verified table entry yet (or
    familyid wasn't supplied, e.g. for an NPC), the old offset is still computed as a fallback but
    explicitly flagged "unverified" -- callers must not treat it as trustworthy for anything
    beyond a rough guess pending real verification (see mob_model_tables.py docstring)."""
    if len(blob) != 20:
        return {"error": f"expected a 20-byte look_t blob, got {len(blob)} bytes"}
    size = struct.unpack_from("<H", blob, 0)[0]
    model_type = MODEL_TYPES.get(size, f"UNKNOWN({size})")
    result = {"model_type": model_type, "size": size}
    if size in FLAT_MODEL_TYPES:
        modelid = struct.unpack_from("<H", blob, 2)[0]
        result.update({"kind": "flat", "modelid": modelid})
        verified_file_id = (
            mob_model_tables.resolve_family_file_id(familyid, modelid)
            if familyid is not None else None
        )
        if verified_file_id is not None:
            result.update({
                "file_id": verified_file_id,
                "file_id_source": "mob_model_tables (verified per-family table)",
                "unverified": False,
            })
        else:
            result.update({
                "file_id": ENTITY_MODEL_OFFSET + modelid,
                "file_id_source": "ENTITY_MODEL_OFFSET fallback -- NOT VERIFIED, do not trust",
                "unverified": True,
            })
    elif size in GEAR_MODEL_TYPES:
        face, race = blob[2], blob[3]
        head, body, hands, legs, feet, main, sub, ranged = struct.unpack_from("<8H", blob, 4)
        race_name = RACE_NAMES.get(race, f"unknown race id {race}")
        gear = {"head": head, "body": body, "hands": hands, "legs": legs,
                "feet": feet, "main": main, "sub": sub, "ranged": ranged}
        composer_race = gear_tables.GEAR_TABLE_RACE_TO_COMPOSER.get(race_name)
        result.update({
            "kind": "gear", "face": face, "race": race,
            "race_name": race_name,
            "gear": gear,
            "skeleton_path": gear_tables.RACE_SKELETON_RELS.get(composer_race) if composer_race else None,
        })
        if race_name in gear_tables.GEAR_TABLES:
            result["gear_resolved"] = gear_tables.resolve_gear_file_ids(race_name, gear)
        else:
            result["gear_resolved"] = {}
            result["error"] = f"no GEAR_TABLES entry for race {race_name!r}"
    else:
        result["kind"] = "prop"
    return result


def decode_look(blob: bytes):
    if len(blob) != 20:
        raise SystemExit(f"expected a 20-byte look_t blob, got {len(blob)} bytes")

    size = struct.unpack_from("<H", blob, 0)[0]
    model_type = MODEL_TYPES.get(size, f"UNKNOWN({size})")
    print(f"look_t.size = {size}  ({model_type})")

    if size in FLAT_MODEL_TYPES:
        modelid = struct.unpack_from("<H", blob, 2)[0]
        file_id = ENTITY_MODEL_OFFSET + modelid
        print(f"  flat modelid = {modelid}")
        print(f"  -> single DAT, file_id = {ENTITY_MODEL_OFFSET} + {modelid} = {file_id}")
        print(f"  -> python model_schedule_dump.py --file-id {file_id}")
    elif size in GEAR_MODEL_TYPES:
        face, race = blob[2], blob[3]
        head, body, hands, legs, feet, main, sub, ranged = struct.unpack_from("<8H", blob, 4)
        race_name = RACE_NAMES.get(race, f"unknown race id {race}")
        print(f"  race = {race} ({race_name}), face = {face}")
        print(f"  gear slot ids (NOT verified against a live capture -- see module docstring):")
        for label, val in [("head", head), ("body", body), ("hands", hands), ("legs", legs),
                            ("feet", feet), ("main", main), ("sub", sub), ("ranged", ranged)]:
            print(f"    {label:8} = {val}")
        print(f"  -> NO single DAT for this entity: base skeleton DAT for {race_name} + one DAT "
              f"per non-zero slot above, merged client-side. See model_schedule_dump.py --dat "
              f"on the race's own base skeleton (xi-model-viewer dat/modelids.js "
              f"RACE_SKELETON_RELS) for its animation schedules independent of gear.")
    else:
        print(f"  {model_type}: not a model at all (door/elevator/ship prop) -- no DAT to resolve.")


def load_poolid_blob(poolid: int) -> bytes:
    path = TOPAZ_ROOT / "sql/mob_pools.sql"
    text = path.read_text(encoding="utf-8", errors="ignore")
    m = re.search(rf"INSERT INTO `mob_pools` VALUES \({poolid},'[^']*','[^']*',\d+,0x([0-9A-Fa-f]{{40}})", text)
    if not m:
        raise SystemExit(f"poolid {poolid} not found in mob_pools.sql")
    return bytes.fromhex(m.group(1))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--hex", help="raw 20-byte look_t blob, e.g. 0x0000640100...")
    g.add_argument("--poolid", type=int, help="mob_pools.poolid to look up directly")
    args = ap.parse_args()

    if args.poolid is not None:
        blob = load_poolid_blob(args.poolid)
    else:
        h = args.hex[2:] if args.hex.lower().startswith("0x") else args.hex
        blob = bytes.fromhex(h)

    decode_look(blob)


if __name__ == "__main__":
    main()
