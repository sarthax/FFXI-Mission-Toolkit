#!/usr/bin/env python3
"""
Walks FFXI event byte code (as exported by xi-tinkerer's `export-dat` to YAML)
opcode-by-opcode using the fixed per-opcode sizes documented in this repo's
OpCodes/*.md files, and prints a human-readable disassembly.

Usage:
    python disassemble.py <events.yml> <entity_id> <event_id>
    python disassemble.py --hex <raw_hex_bytecode>
"""
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).parent
OPCODE_TABLE = json.loads((HERE / "opcode_table.json").read_text())
SIZES = {int(k): v for k, v in OPCODE_TABLE["sizes"].items()}
NAMES = {int(k): v for k, v in OPCODE_TABLE["names"].items()}

# Opcodes worth flagging for the fade-transition investigation.
FLAGGED = {
    0x46: "CodeDEFCAMERA -- enables/disables player camera control, hides menus for cutscenes",
    0x6C: "CodeTRANSPAR -- fades an entity's color/alpha in and out over time",
}


def disassemble(byte_code: bytes, label: str = ""):
    print(f"--- {label} ({len(byte_code)} bytes) ---")
    i = 0
    while i < len(byte_code):
        opcode = byte_code[i]
        size = SIZES.get(opcode)
        name = NAMES.get(opcode)
        flag = FLAGGED.get(opcode)

        if size is None:
            print(f"  [{i:4d}] {opcode:02X} ?? -- UNKNOWN OPCODE, unable to determine size, stopping.")
            print("  Remaining bytes:", byte_code[i:].hex().upper())
            return

        operand = byte_code[i + 1 : i + size]
        label_str = f" ({name})" if name else ""
        flag_str = f"   <<< {flag}" if flag else ""
        print(
            f"  [{i:4d}] {opcode:02X}{label_str:30s} operand={operand.hex().upper()}{flag_str}"
        )

        if flag:
            print(f"         ^ FULL: {byte_code[i:i+size].hex().upper()}")

        i += size


def extract_event_bytecode(yml_path: str, entity_id: str, event_id: str) -> bytes:
    text = Path(yml_path).read_text(encoding="utf-8")
    # Find the entity_id block, then the event id within it, then its byte_code line.
    entity_pat = re.compile(rf"- entity_id: {re.escape(entity_id)}\n(.*?)(?=\n- entity_id:|\Z)", re.S)
    m = entity_pat.search(text)
    if not m:
        raise SystemExit(f"entity_id {entity_id} not found in {yml_path}")
    block = m.group(1)

    event_pat = re.compile(
        rf"- id: {re.escape(event_id)}\n\s*byte_code: '?0x([0-9A-Fa-f]+)'?"
    )
    em = event_pat.search(block)
    if not em:
        raise SystemExit(f"event id {event_id} not found under entity_id {entity_id}")
    return bytes.fromhex(em.group(1))


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--hex":
        disassemble(bytes.fromhex(sys.argv[2]), label="raw hex")
    elif len(sys.argv) == 4:
        yml_path, entity_id, event_id = sys.argv[1:4]
        bc = extract_event_bytecode(yml_path, entity_id, event_id)
        disassemble(bc, label=f"entity {entity_id} event {event_id}")
    else:
        print(__doc__)
        sys.exit(1)
