#!/usr/bin/env python3
"""
Real semantic disassembler for FFXI event bytecode, built on this repo's own reverse-engineered
opcode documentation (opcode_docs.json, see decode_opcode_docs.py) instead of just a raw hex dump
(that's all disassemble.py in this same repo does today).

Replaces guessing at what an opcode "probably" does (a real, repeated mistake this session -- e.g.
assuming 0x32 was a menu/selection opcode by pattern-matching hex, when its real documented
behavior is "sets ExtData[1]->MainSpeed", nothing to do with menus at all) with the actual
retail-reverse-engineered description for every opcode in the byte stream.

Usage:
    python smart_disassemble.py <events.yml> <entity_id> <event_id>
    python smart_disassemble.py --hex <raw_hex_bytecode>
"""
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).parent
DOCS = json.loads((HERE / "opcode_docs.json").read_text())
OPCODE_TABLE = json.loads((HERE / "opcode_table.json").read_text())
FALLBACK_SIZES = {int(k): v for k, v in OPCODE_TABLE["sizes"].items()}
FALLBACK_NAMES = {int(k): v for k, v in OPCODE_TABLE["names"].items()}

# 2026-08-31: confirmed against this repo's own "Event VM Functions.md" (XiEvent::eventgetcode /
# XiEvent::getworkofs real pseudo-code) and cross-checked empirically against real bytecode this
# session (Nafiwaa's event 661 -- operand bytes for 5 consecutive `1D` message opcodes were
# 02 80 / 03 80 / 04 80 / 05 80, resolving to data[2..5] = 6328..6331, matching the 5 real dialog
# lines that event is confirmed to show in-game).
#
# eventgetcode(this, N) reads a little-endian 2-byte value at BYTE OFFSET N from the opcode's own
# start (offset 0 = the opcode byte itself, so N=1 is the first operand byte). getworkofs then
# resolves that raw uint16 `val`:
#   - val & 0x8000 set  -> real index = val & 0x7FFF, resolved via this entity's own data[] array
#     (the "References" array in the real VM -- xi-tinkerer's own YAML export already flattens
#     this to a plain per-entity list, confirmed empirically, no further x4 stride needed on our
#     side despite the raw C++ doing `References[4 * index]` -- that's an implementation detail of
#     the raw memory layout the YAML export already resolved for us).
#   - val < 2048        -> WorkLocal[val] (local scratch var, nothing we can resolve statically)
#   - val < 4352         -> Work_Zone[val-4096] (shared zone scratch, same -- can't resolve statically)
#   - val < 4608         -> Work_Zone_Memorize[val-4352]
#   - val < 6144         -> Work_Zone_1700[val-5888]
#   - val < 32640 (and >= 0x7F00) -> a fixed set of real entity-position/job/race fields (position,
#     direction, job id, race, etc -- see the VM Functions doc for the full table)
#   - otherwise         -> invalid, resolves to 0
#
# MESSAGE_REF_OPCODES maps an opcode -> the byte offset (from the opcode's own start) where its
# real getworkofs_(this, N) call reads the message-reference value, taken directly from each
# opcode's own documented pseudo code. Only opcodes confirmed this way are listed -- extend this
# table as more opcodes are checked against their own .md pseudo code.
MESSAGE_REF_OPCODES = {
    0x1D: 1,  # "Loads and prints an event message... using EntityTargetIndex[1] as the speaker"
    0x2B: 5,  # "Loads and prints an event message with the given entity as the speaker"
    # 2026-08-31, real menu/selection family (see this file's own header note for the full
    # 0x24/0x25/0x02 mechanism). 0x24's real message ref is its PROMPT text -- confirmed via its
    # own pseudo code (`getworkofs_(this, 1)` then `FUNC_GetEventMessage`), same offset convention
    # as 0x1D. The choices themselves are NOT separate data[] refs -- they're embedded as
    # `${selection-lines}` markup within that SAME resolved prompt string (confirmed against real
    # dialog table entry 6643, "What is a mercenary's duty?\n${selection-lines}\nUm...\nHelping...
    # \nCompleting...\n${prompt}" -- the exact real LC-quest ending question), so resolving 0x24
    # here already gives the full question + all real choice text in one shot.
    0x24: 1,
}

# 2026-08-31, real menu-result mechanism: 0x24 shows the menu, 0x25 (bare opcode, no operand)
# blocks until the player picks, then stores `selectedIndex - 1` (0-based; or 254 if the player
# cancelled/escaped, per this opcode's own real documented pseudo code) into `Work_Zone[0]`. Later
# opcodes that getworkofs-resolve val==4096 (Work_Zone[0], since Work_Zone starts at raw val 4096
# per the real branch table) are reading back that exact choice -- this is the real mechanism
# behind every menu-driven branch in this codebase's Assault/quest work this session (the LC
# quest's mixing-minigame accept/discard decision AND its final 3-way ending choice both work this
# way). No operand to decode for 0x25 itself; NOTEWORTHY_OPCODES just flags what it does inline.
NOTEWORTHY_OPCODES = {
    0x25: "menu result: stores the player's 0-based selection (or 254 if cancelled) into Work_Zone[0] -- see this file's own MESSAGE_REF_OPCODES[0x24] comment",
}

# 2026-08-31, real generic `if`/branch opcode (0x02) -- confirmed via its own full pseudo code:
# reads two getworkofs-resolved values (val1 @ offset1, val2 @ offset3), a 1-byte comparison-type
# selector (offset5, `& 0x0F`), and a raw jump-target offset (offset6, 2 bytes, added to
# ExecPointer via eventgetcode -- NOT getworkofs, this one's a literal displacement, not a data[]
# reference). This is the real branch mechanism a menu result (Work_Zone[0], val=4096) gets tested
# against -- e.g. "if Work_Zone[0] == 1, jump forward N bytes to the Slapstick-crab path". Case
# numbers/comparisons taken directly from the opcode's own documented pseudo code.
CONDITION_TYPES = {
    0: "val1 == val2  (INVERTED: +val3 on MISMATCH, +8 on match)",
    1: "val1 == val2  (+val3 on match, +8 otherwise)",
    2: "val1 <= val2  (+val3 on match, +8 otherwise)",
    3: "val1 >= val2  (+val3 on match, +8 otherwise)",
    4: "val1 <  val2  (+val3 on match, +8 otherwise)",
    5: "val1 >  val2  (+val3 on match, +8 otherwise)",
    6: "(val2 & val1) == 0  (+val3 on match, +8 otherwise) -- same as case 9",
    7: "val1 == val2  (+val3 on match, +8 otherwise) -- same as case 1",
    8: "(val1 | val2) == 0  (+val3 on match, +8 otherwise)",
    9: "(val2 & val1) == 0  (+val3 on match, +8 otherwise) -- same as case 6",
    10: "(~val1 & val2) == 0  (+val3 on match, +8 otherwise)",
}

WORK_FIELD_NAMES = {
    0x7F00: "EventPos.X", 0x7F01: "EventPos.Y", 0x7F02: "EventPos.Z", 0x7F03: "EventDir",
    0x7F06: "player job id", 0x7F07: "entity race", 0x7F08: "player job level",
    0x7F0A: "entity server id", 0x7F0B: "render flag bit",
    0x7F80: "local player X", 0x7F81: "local player Z", 0x7F82: "local player Y",
    0x7F83: "local player dir", 0x7F86: "player job id", 0x7F87: "player race",
    0x7F88: "player job level", 0x7F8A: "player server id", 0x7F8B: "render flag bit",
}


def resolve_workofs(val: int, data_array):
    """Real getworkofs resolution -- see MESSAGE_REF_OPCODES's own header comment."""
    if val & 0x8000:
        idx = val & 0x7FFF
        if data_array is not None and 0 <= idx < len(data_array):
            return f"data[{idx}]={data_array[idx]}", data_array[idx]
        return f"data[{idx}]=<data[] not loaded or index out of range>", None
    if val < 2048:
        return f"WorkLocal[{val}] (local scratch, not statically resolvable)", None
    if val < 4352:
        idx = val - 4096
        note = " -- the real menu-result slot, see MESSAGE_REF_OPCODES[0x24]'s comment" if idx == 0 else ""
        return f"Work_Zone[{idx}] (shared zone scratch, not statically resolvable{note})", None
    if val < 4608:
        return f"Work_Zone_Memorize[{val - 4352}] (not statically resolvable)", None
    if val < 6144:
        return f"Work_Zone_1700[{val - 5888}] (not statically resolvable)", None
    if val in WORK_FIELD_NAMES:
        return f"entity field: {WORK_FIELD_NAMES[val]}", None
    return f"<invalid/unrecognized val={val:#06x}>", None


def load_dialog_table(dialog_yml_path):
    if not dialog_yml_path:
        return None
    import yaml
    with open(dialog_yml_path, encoding="utf-8") as f:
        d = yaml.safe_load(f)
    return d.get("entries", d)


def disassemble(byte_code: bytes, label: str = "", data_array=None, dialog_table=None):
    print(f"--- {label} ({len(byte_code)} bytes) ---")
    i = 0
    while i < len(byte_code):
        opcode = byte_code[i]
        doc = DOCS.get(str(opcode))

        size = doc["size"] if doc and doc["size"] else FALLBACK_SIZES.get(opcode)
        name = FALLBACK_NAMES.get(opcode) or ""
        desc = doc["description"] if doc else "(undocumented opcode -- not in this repo's OpCodes/*.md set)"

        if size is None:
            print(f"  [{i:4d}] {opcode:02X} ?? -- size unknown (undocumented + not in opcode_table.json), stopping.")
            print("  Remaining bytes:", byte_code[i:].hex().upper())
            return

        operand = byte_code[i + 1 : i + size]
        ret_flag = f" RetFlag={doc['sets_ret_flag']}" if doc and doc["sets_ret_flag"] else ""

        print(f"  [{i:4d}] {opcode:02X} {name:14s} operand={operand.hex().upper() or '(none)':10s}{ret_flag}")

        # Real getworkofs resolution for opcodes confirmed to read a message/data reference --
        # see MESSAGE_REF_OPCODES's own header comment for how the offset was derived.
        if opcode in MESSAGE_REF_OPCODES:
            offset = MESSAGE_REF_OPCODES[opcode]
            val_bytes = byte_code[i + offset : i + offset + 2]
            if len(val_bytes) == 2:
                val = val_bytes[0] | (val_bytes[1] << 8)
                resolved_str, resolved_int = resolve_workofs(val, data_array)
                print(f"         >>> message ref (val={val:#06x}): {resolved_str}")
                if resolved_int is not None and dialog_table is not None:
                    text = dialog_table.get(resolved_int)
                    if text is not None:
                        print(f"         >>> real dialog text #{resolved_int}: {text!r}")

        if opcode in NOTEWORTHY_OPCODES:
            print(f"         >>> {NOTEWORTHY_OPCODES[opcode]}")

        # Real 0x02 if/branch decode -- see this file's own CONDITION_TYPES header comment.
        # Per the opcode's own pseudo code, the "match" outcome does `this->ExecPointer =
        # eventgetcode(this, 6)` -- a direct SET, not a relative add -- so val3 is an ABSOLUTE
        # bytecode position to jump to, not an offset from the current opcode (unlike the "no
        # match" fallthrough, which is always a fixed literal `+= 8`, i.e. just past this opcode).
        if opcode == 0x02 and len(operand) == 7:
            val1_raw = operand[0] | (operand[1] << 8)
            val2_raw = operand[2] | (operand[3] << 8)
            cond_type = operand[4] & 0x0F
            jump_target = operand[5] | (operand[6] << 8)
            val1_str, _ = resolve_workofs(val1_raw, data_array)
            val2_str, _ = resolve_workofs(val2_raw, data_array)
            cond_str = CONDITION_TYPES.get(cond_type, f"<unknown condition type {cond_type}>")
            print(f"         >>> if: val1={val1_str}  val2={val2_str}")
            print(f"         >>> condition type {cond_type}: {cond_str}")
            print(f"         >>> on match: jump to absolute bytecode position {jump_target}; otherwise falls through to {i + 8}")

        # Wrap the description to keep lines scannable.
        for line_start in range(0, len(desc), 100):
            print(f"         | {desc[line_start:line_start+100]}")

        i += size
    print()


def extract_event(yml_path: str, entity_id: str, event_id: str):
    """2026-08-31: switched from regex-on-raw-text to real yaml.safe_load() + dict traversal --
    the old regex assumed a specific field order/indentation (`- id: N\\n    byte_code: ...`) that
    the CLI-based YAML export happened to produce, but mission_toolkit.py's own native
    xi-tinkerer-py writer emits equally valid YAML with a different field order (`byte_code` before
    `id`) and indentation, which silently broke the old regex (matched nothing, no error). Loading
    the YAML for real is immune to any such future formatting differences."""
    import yaml as _yaml

    with open(yml_path, encoding="utf-8") as f:
        doc = _yaml.safe_load(f)

    entity_id_int, event_id_int = int(entity_id), int(event_id)
    block = next((b for b in doc.get("blocks", []) if b.get("entity_id") == entity_id_int), None)
    if block is None:
        raise SystemExit(f"entity_id {entity_id} not found in {yml_path}")

    ev = next((e for e in block.get("events", []) if e.get("id") == event_id_int), None)
    if ev is None:
        raise SystemExit(f"event id {event_id} not found under entity_id {entity_id}")

    raw = ev.get("byte_code", "")
    hexstr = raw[2:] if isinstance(raw, str) and raw.startswith("0x") else format(raw, "x")
    if len(hexstr) % 2:
        hexstr = "0" + hexstr
    if hexstr in ("00", "0"):
        raise SystemExit(f"event id {event_id} under entity_id {entity_id} is a bare '0x00' stub -- no real bytecode to disassemble.")
    byte_code = bytes.fromhex(hexstr)

    data_array = block.get("data")
    return byte_code, data_array


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--hex":
        disassemble(bytes.fromhex(sys.argv[2]), label="raw hex")
    elif len(sys.argv) in (4, 5):
        yml_path, entity_id, event_id = sys.argv[1:4]
        dialog_yml_path = sys.argv[4] if len(sys.argv) == 5 else None
        dialog_table = load_dialog_table(dialog_yml_path)
        bc, data_array = extract_event(yml_path, entity_id, event_id)
        disassemble(bc, label=f"entity {entity_id} event {event_id}", data_array=data_array, dialog_table=dialog_table)
        if data_array:
            print(f"entity's own data[] array ({len(data_array)} entries):")
            print(data_array)
    else:
        print(__doc__)
        print("\n(optional 5th arg: path to the zone's dialog.yml, to resolve real text alongside data[] indices)")
        sys.exit(1)
