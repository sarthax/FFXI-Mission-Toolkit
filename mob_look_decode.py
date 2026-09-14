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

CONFIRMED, NOT YET VERIFIED: the per-slot ids sent for MODEL_EQUIPED (head/body/hands/legs/
feet/main/sub/ranged) do NOT fall inside xi-model-viewer's own GEAR_TABLES ranges for the
matching race+slot (checked by hand against a real Topaz row, see below) -- so whatever
numbering scheme Topaz/retail actually uses here is NOT simply "the same file id as
GEAR_TABLES". Do not treat this script's slot output as a direct file id or feed it into
model_schedule_dump.py until that numbering is verified against a real capture that also shows
the resulting visual appearance -- flagging this honestly rather than guessing an offset.

Usage:
    python mob_look_decode.py --hex 0x0000640100000000000000000000000000000000
    python mob_look_decode.py --poolid 649          # looks up sql/mob_pools.sql directly
"""
import argparse
import re
import struct
from pathlib import Path

import settings

TOPAZ_ROOT = settings.get_topaz_root()
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


def decode_look_data(blob: bytes) -> dict:
    """Same real decode as decode_look() below, returning structured data instead of printing --
    for programmatic use (entity_profile.py) rather than CLI output. Kept as a separate function
    rather than refactoring decode_look() itself, to avoid any risk of changing that function's
    already-correct, already-used CLI print behavior."""
    if len(blob) != 20:
        return {"error": f"expected a 20-byte look_t blob, got {len(blob)} bytes"}
    size = struct.unpack_from("<H", blob, 0)[0]
    model_type = MODEL_TYPES.get(size, f"UNKNOWN({size})")
    result = {"model_type": model_type, "size": size}
    if size in FLAT_MODEL_TYPES:
        modelid = struct.unpack_from("<H", blob, 2)[0]
        result.update({
            "kind": "flat", "modelid": modelid,
            "file_id": ENTITY_MODEL_OFFSET + modelid,
        })
    elif size in GEAR_MODEL_TYPES:
        face, race = blob[2], blob[3]
        head, body, hands, legs, feet, main, sub, ranged = struct.unpack_from("<8H", blob, 4)
        result.update({
            "kind": "gear", "face": face, "race": race,
            "race_name": RACE_NAMES.get(race, f"unknown race id {race}"),
            "gear": {"head": head, "body": body, "hands": hands, "legs": legs,
                     "feet": feet, "main": main, "sub": sub, "ranged": ranged},
            "note": "NOT verified against a live capture -- see module docstring",
        })
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
