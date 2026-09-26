"""Canonical packet opcode identity helpers.

All-digit strings are decimal. 0x-prefixed strings are hexadecimal. Bare
hexadecimal strings are accepted only when they contain A-F, preventing "042"
from silently changing meaning between tools.
"""
from __future__ import annotations
import re

_HEX=re.compile(r"^[0-9a-fA-F]+$")

def parse_opcode(value):
    if isinstance(value,bool):
        return None
    if isinstance(value,int):
        return value if value>=0 else None
    raw=str(value).strip()
    if not raw:
        return None
    try:
        if raw.lower().startswith("0x"):
            return int(raw,16)
        if raw.isdigit():
            return int(raw,10)
        if _HEX.fullmatch(raw) and any(ch in "abcdefABCDEF" for ch in raw):
            return int(raw,16)
    except ValueError:
        return None
    return None

def canonical_opcode(value):
    parsed=parse_opcode(value)
    return None if parsed is None else f"0x{parsed:03x}"

def packet_node_id(value):
    canonical=canonical_opcode(value)
    return None if canonical is None else f"packet:{canonical}"

def opcode_aliases(value):
    raw=str(value).strip()
    canonical=canonical_opcode(value)
    if canonical is None:
        return [raw.lower()] if raw else []
    aliases=[canonical]
    normalized=raw.lower()
    if normalized and normalized not in aliases:
        aliases.append(normalized)
    return aliases
