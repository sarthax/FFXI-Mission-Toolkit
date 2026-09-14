#!/usr/bin/env python3
"""
Parses every OpCodes/*.md file in this repo into one structured JSON reference
(opcode -> {name, size, description, sets_ret_flag, sets_exec_pointer}).

This is the real, reverse-engineered-from-retail documentation this repo already ships --
opcode_table.json (used by disassemble.py) only has names/sizes, not the actual semantics.
Building this once means every future disassembly pass can show a real one-line description
per opcode instead of a bare hex dump, and downstream tooling can grep/filter by real behavior
(e.g. "which opcodes touch EventPos" or "which opcodes print a message").

Usage:
    python decode_opcode_docs.py [output.json]
"""
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).parent
OPCODES_DIR = HERE / "OpCodes"

TABLE_ROW_RE = re.compile(r"\|\s*\*\*(.+?)\*\*\s*\|\s*(.+?)\s*\|")
DESC_RE = re.compile(r"## Description\s*\n(.*?)(?=\n## |\Z)", re.S)


def parse_one(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")

    opcode_hex = path.stem  # e.g. "0x001D"
    opcode = int(opcode_hex, 16)

    fields = {}
    for m in TABLE_ROW_RE.finditer(text):
        key, val = m.group(1).strip(), m.group(2).strip()
        fields[key] = val

    desc_m = DESC_RE.search(text)
    description = desc_m.group(1).strip() if desc_m else ""
    # Collapse to a single line for compact downstream use; keep full text separately.
    description_oneline = " ".join(description.split())

    size_str = fields.get("OpCode Size", "").strip("`").strip()
    try:
        size = int(size_str)
    except ValueError:
        size = None

    return {
        "opcode": opcode,
        "hex": opcode_hex,
        "size": size,
        "sets_ret_flag": fields.get("Sets `RetFlag`?", "").strip("`").strip() or None,
        "sets_exec_pointer": fields.get("Sets `ExecPointer`?", "").strip("`").strip() or None,
        "description": description_oneline,
        "description_full": description,
    }


def main():
    out_path = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "opcode_docs.json"

    entries = {}
    for path in sorted(OPCODES_DIR.glob("0x*.md")):
        try:
            entry = parse_one(path)
        except Exception as e:
            print(f"WARNING: failed to parse {path.name}: {e}", file=sys.stderr)
            continue
        entries[str(entry["opcode"])] = entry

    out_path.write_text(json.dumps(entries, indent=1), encoding="utf-8")
    print(f"Parsed {len(entries)} documented opcodes -> {out_path}")


if __name__ == "__main__":
    main()
