"""Bounded, conservative data-address references in unpacked FFXiMain code.

A raw four-byte match can occur within data or an instruction immediate. It is
not proof of a reference or executable reachability. No bytes are modified.
"""
from __future__ import annotations
import struct
from pathlib import Path
from workbench.client.pol1_unpack import unpack_pol1

def address_candidates(path: str | Path, target_rva: int, *, image_base: int = 0x10000000,
                       limit: int = 100) -> dict:
    if isinstance(target_rva, bool) or not isinstance(target_rva, int) or not 0 <= target_rva <= 0xffffffff:
        raise ValueError("target_rva must be a uint32")
    if not 1 <= limit <= 200:
        raise ValueError("limit must be 1..200")
    if not 0 <= image_base <= 0xffffffff or target_rva + image_base > 0xffffffff:
        raise ValueError("image base / RVA overflow")
    unpacked = unpack_pol1(Path(path).read_bytes())
    code = unpacked["bytes"]
    needles = [("rva32", struct.pack("<I", target_rva)),
               ("va32", struct.pack("<I", image_base + target_rva))]
    results = []
    for kind, needle in needles:
        at = 0
        while len(results) < limit:
            at = code.find(needle, at)
            if at < 0:
                break
            a, b = max(0, at - 8), min(len(code), at + 12)
            results.append({"kind": kind, "match_rva": unpacked["base_rva"] + at,
                            "match_rva_hex": f"0x{unpacked['base_rva'] + at:X}",
                            "context_rva": unpacked["base_rva"] + a,
                            "context_hex": code[a:b].hex(" ")})
            at += 1
    return {"status": "CANDIDATES" if results else "UNKNOWN",
            "target_rva": target_rva, "image_base": image_base,
            "unpacked_sha256": unpacked["sha256"],
            "matches": results[:limit], "truncated": len(results) >= limit,
            "warning": "Raw 32-bit value occurrences are heuristic. Verify instruction alignment and relocation before claiming a code reference."}
