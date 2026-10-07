#!/usr/bin/env python3
"""Read-only decoder for server/client look_t model data."""
import argparse
import re
import struct

from workbench.client.models import gear_tables
from workbench.client.models import resolver as client_model_resolver
from workbench.runtime import legacy_settings as settings

TOPAZ_ROOT = settings.get_active_server_root()
MODEL_TYPES = {
    0: "MODEL_STANDARD", 1: "MODEL_EQUIPED", 2: "MODEL_DOOR", 3: "MODEL_ELEVATOR",
    4: "MODEL_SHIP", 5: "MODEL_UNK_5", 6: "MODEL_AUTOMATON", 7: "MODEL_CHOCOBO",
}
FLAT_MODEL_TYPES = {0, 5, 6}
GEAR_MODEL_TYPES = {1, 7}

RACE_NAMES = {
    1: "HumeMale", 2: "HumeFemale", 3: "ElvaanMale", 4: "ElvaanFemale",
    5: "TaruMale", 6: "TaruFemale", 7: "Mithra", 8: "Galka",
}


def decode_look_data(blob: bytes, familyid: int | None = None) -> dict:
    if len(blob) != 20:
        return {"error": f"expected a 20-byte look_t blob, got {len(blob)} bytes"}
    size = struct.unpack_from("<H", blob, 0)[0]
    model_type = MODEL_TYPES.get(size, f"UNKNOWN({size})")
    result = {"model_type": model_type, "size": size}
    if size in FLAT_MODEL_TYPES:
        modelid = struct.unpack_from("<H", blob, 2)[0]
        result.update({"kind": "flat", "modelid": modelid})
        file_id, rule = client_model_resolver.model_id_to_file_id(modelid)
        result.update({
            "file_id": file_id,
            "file_id_source": f"FFXiMain NpcTable piecewise mapping ({rule})",
            "unverified": False,
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
            resolved = gear_tables.resolve_gear_file_ids(race_name, gear)
            face_fid = gear_tables.model_id_to_file_id(race_name, "face", face)
            resolved = {
                "face": {
                    "model_id": int(face),
                    "file_id": face_fid,
                    "source": "look_t.face byte -> race face GEAR_TABLES",
                    **({"error": f"face model_id {face} is outside the known {race_name} face table"}
                       if face_fid is None else {}),
                },
                **resolved,
            }
            result["gear_resolved"] = resolved
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
        file_id, rule = client_model_resolver.model_id_to_file_id(modelid)
        print(f"  flat modelid = {modelid}")
        print(f"  -> FFXiMain lookup: {rule} -> file_id {file_id}")
        print(f"  -> this file_id identifies the client monster resource/skeleton entry; visible mesh resources may be linked separately")
        print(f"  -> python -m workbench.client.models.schedule_dump --file-id {file_id}")
    elif size in GEAR_MODEL_TYPES:
        face, race = blob[2], blob[3]
        head, body, hands, legs, feet, main, sub, ranged = struct.unpack_from("<8H", blob, 4)
        race_name = RACE_NAMES.get(race, f"unknown race id {race}")
        print(f"  race = {race} ({race_name}), face = {face}")
        print("  gear slot ids (NOT verified against a live capture -- see module documentation):")
        for label, val in [("head", head), ("body", body), ("hands", hands), ("legs", legs),
                            ("feet", feet), ("main", main), ("sub", sub), ("ranged", ranged)]:
            print(f"    {label:8} = {val}")
        print(f"  -> NO single DAT for this entity: base skeleton DAT for {race_name} + one DAT per non-zero slot above, merged client-side.")
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
