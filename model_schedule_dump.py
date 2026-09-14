#!/usr/bin/env python3
"""
model_schedule_dump.py -- resolves an entity/gear model id to its real DAT (via dat-extractor's
FTABLE/VTABLE lookup, same as mission_toolkit.py) and dumps its 0x07 EffectRoutine schedules:
which animation clips they play, in what order, and at what (relative) delay.

Ported from xi-model-viewer's ui/js/dat.js (walkSections/parseRoutine/parseAnimation/matchAnimRef)
-- see ffxi_animation_schedule_ground_truth memory for how that parser was found and why it
matters: `loadExtSchedulerMain`/similar event calls pass numeric animation-tag arguments that are
otherwise opaque without resolving them against the SPECIFIC entity's own model DAT (there is no
global animation-id table -- tags are per-model wildcard clip refs like `at0?`).

Usage:
    python model_schedule_dump.py --file-id 98450                 # raw FTABLE file id
    python model_schedule_dump.py --model-id 211                  # monster/NPC model id
                                                                    # (file_id = 98239 + model_id)
    python model_schedule_dump.py --dat "ROM/2/45.DAT"             # already-known ROM-relative path

NOTE on finding a model id for a specific Topaz mob/NPC: mob_pools.modelid / npc_list look-string
fields are PACKED per-slot blobs (race + up to 9 gear-slot ids for humanoid-look entities), not a
single flat number -- decoding that packing is NOT done by this script (would need real capture
verification before trusting an offset guess, same standing rule as everywhere else in this
project). This script's real, verified entry point is a single numeric model id or file id, same
as what xi-model-viewer itself takes -- use its `dat/modelids.js` ENTITY_MODEL_OFFSET (98239) by
hand for a pure single-model monster, or open xi-model-viewer itself to find the id visually via
its NPC/monster browser, until a dedicated look-string decoder is built and verified.
"""
import argparse
import re
import subprocess
import struct
from pathlib import Path

TOOLS_ROOT = Path(__file__).parent
DAT_EXTRACTOR_DLL = TOOLS_ROOT / "vendor/dat-extractor/bin/Debug/net9.0/dat-extractor.dll"
DEFAULT_FFXI_PATH = "C:/ValhallaXI/SquareEnix/FINAL FANTASY XI"
ENTITY_MODEL_OFFSET = 98239  # xi-model-viewer dat/modelids.js -- monster/NPC flat model range


def resolve_rom_path(ffxi_path: str, dat_id: int) -> str | None:
    result = subprocess.run(
        ["dotnet", "exec", str(DAT_EXTRACTOR_DLL), "--resolve", ffxi_path, str(dat_id)],
        capture_output=True, text=True,
    )
    for line in result.stdout.splitlines():
        parts = line.split("\t")
        if len(parts) >= 2 and parts[0] == str(dat_id):
            return None if parts[1] == "(not found)" else parts[1]
    return None


# ---------------------------------------------------------------------------
# Section walker -- port of xi-model-viewer ui/js/dat.js walkSections()
# 16-byte headers: 4-char id, u32 meta (bits 0-6 type, bits 7-26 size in
# 16-byte units, includes header). Data starts at start+0x10.
# ---------------------------------------------------------------------------
SEC_EFFECT_ROUTINE = 0x07
SEC_SKELETON_ANIMATION = 0x2B


def walk_sections(data: bytes):
    sections = []
    pos = 0
    n = len(data)
    while pos + 16 <= n:
        start = pos
        raw_id = data[start:start + 4]
        if any(b != 0 and (b < 0x20 or b > 0x7e) for b in raw_id):
            break
        sec_id = raw_id.split(b"\x00", 1)[0].decode("ascii", "replace")
        meta = struct.unpack_from("<I", data, start + 4)[0]
        type_code = meta & 0x7F
        size = ((meta >> 7) & 0xFFFFF) * 0x10
        if size < 0x10:
            size = 0x10
        if start + size > n:
            break
        sections.append({
            "id": sec_id, "type": type_code, "start": start,
            "size": size, "data_start": start + 0x10, "end": start + size,
        })
        pos = start + size
    return sections


def u16(data: bytes, o: int) -> int:
    return data[o] | (data[o + 1] << 8)


def parse_routine(data: bytes, sec: dict):
    """Port of parseRoutine (dat.js:148). Returns None if the section is too small
    (< 0x30 bytes) to hold a routine header."""
    base = sec["data_start"]
    if sec["size"] < 0x30:
        return None

    sec2 = struct.unpack_from("<i", data, base + 0x14)[0]
    end = sec["end"]
    p = base + (sec2 - 16)

    commands = []
    clock = 0
    guard = 0
    while guard < 128 and p + 8 <= end:
        guard += 1
        op = data[p]
        n = (data[p + 1] | (data[p + 2] << 8)) & 0x1F
        entry_len = max(1, n) * 4
        at = clock
        if op != 0x00:
            clock += u16(data, p + 4)
        if op == 0x05 and p + 32 <= end:
            ref_bytes = data[p + 8:p + 12]
            if all(0x20 <= b <= 0x7E for b in ref_bytes):
                ref = ref_bytes.decode("ascii").rstrip()
                commands.append({
                    "ref": ref,
                    "delay": at,                     # ABSOLUTE start time (already summed)
                    "duration": u16(data, p + 6),
                    "trans_in": u16(data, p + 24),
                    "trans_out": u16(data, p + 28),
                    "max_loops": u16(data, p + 30),
                })
        if op == 0x00:
            break
        p += entry_len

    return {"id": sec["id"], "commands": commands}


def parse_animation_id(data: bytes, sec: dict) -> str:
    return sec["id"]


def match_anim_ref(ref: str, ids: list[str]) -> list[str]:
    """Port of matchAnimRef (dat.js:232). `?` is the client's wildcard for the
    body-slot digit (e.g. `at0?` matches `at00`, `at01`, ...)."""
    q = ref.find("?")
    if q >= 0:
        prefix = ref[:q]
        return [i for i in ids if i.startswith(prefix)]
    if ref in ids:
        return [ref]
    return [i for i in ids if i.startswith(ref)]


def dump_model(data: bytes, source_label: str):
    sections = walk_sections(data)
    routines = []
    anim_ids = []
    for sec in sections:
        if sec["type"] == SEC_EFFECT_ROUTINE:
            r = parse_routine(data, sec)
            if r:
                routines.append(r)
        elif sec["type"] == SEC_SKELETON_ANIMATION:
            anim_ids.append(parse_animation_id(data, sec))

    print(f"\n{source_label}")
    print(f"  {len(sections)} sections, {len(anim_ids)} animation clips, {len(routines)} schedules")
    if anim_ids:
        print(f"  animation clip ids: {', '.join(sorted(anim_ids))}")

    if not routines:
        print("  (no 0x07 EffectRoutine schedules found in this DAT)")
        return

    for r in routines:
        print(f"\n  schedule '{r['id']}':")
        if not r["commands"]:
            print("    (no 0x05 SkeletonAnimation commands -- SFX/VFX-only or unrecognized layout)")
            continue
        for c in r["commands"]:
            resolved = match_anim_ref(c["ref"], anim_ids)
            resolved_str = ", ".join(resolved) if resolved else "NO MATCH in this DAT's own clips"
            print(f"    t={c['delay']:>4}  ref={c['ref']!r:8} dur={c['duration']:<5} "
                  f"transIn={c['trans_in']:<4} transOut={c['trans_out']:<4} "
                  f"maxLoops={c['max_loops']:<3} -> {resolved_str}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--file-id", type=int, help="raw FTABLE file id to resolve and dump")
    g.add_argument("--model-id", type=int, help="monster/NPC flat model id (file_id = 98239 + this)")
    g.add_argument("--dat", help="already-known ROM-relative DAT path, read directly")
    ap.add_argument("--ffxi-path", default=DEFAULT_FFXI_PATH)
    args = ap.parse_args()

    if args.dat:
        full_path = Path(args.ffxi_path) / args.dat.replace("/", "\\")
        label = args.dat
    else:
        file_id = args.file_id if args.file_id is not None else ENTITY_MODEL_OFFSET + args.model_id
        rom_path = resolve_rom_path(args.ffxi_path, file_id)
        if not rom_path:
            raise SystemExit(f"dat-extractor could not resolve file id {file_id} to a ROM path.")
        full_path = Path(rom_path)
        label = f"file_id {file_id} -> {rom_path}"

    if not full_path.exists():
        raise SystemExit(f"Resolved path does not exist on disk: {full_path}")

    data = full_path.read_bytes()
    dump_model(data, label)


if __name__ == "__main__":
    main()
