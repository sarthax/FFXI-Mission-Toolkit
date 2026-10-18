"""Read-only POL1 LZSS unpacker for FFXiMain.dll research.

Algorithm independently expressed from Kuluu's GPL-3.0-or-later
ffxi-dat/src/pol1.rs (jondwillis/kuluu-ffxi), which credits xi-tools.
The unpacked image is evidence only; no binaries are patched or executed.
"""
from __future__ import annotations

import hashlib
import struct
from pathlib import Path

MAX_UNPACKED_SIZE = 64 * 1024 * 1024


class Pol1Error(ValueError):
    pass


def _section(image: bytes, name: bytes):
    if len(image) < 0x40:
        raise Pol1Error("truncated DOS header")
    pe = struct.unpack_from("<I", image, 0x3c)[0]
    if pe + 24 > len(image) or image[pe:pe + 4] != b"PE\0\0":
        raise Pol1Error("not a PE image")
    count = struct.unpack_from("<H", image, pe + 6)[0]
    optional = struct.unpack_from("<H", image, pe + 20)[0]
    table = pe + 24 + optional
    for i in range(count):
        pos = table + i * 40
        if pos + 40 > len(image):
            raise Pol1Error("truncated section table")
        if image[pos:pos + 8].rstrip(b"\0") == name:
            vsize, rva, raw_size, raw_start = struct.unpack_from("<IIII", image, pos + 8)
            return {"virtual_size": vsize, "rva": rva, "raw_size": raw_size, "raw_start": raw_start}
    raise Pol1Error(f"missing section {name!r}")


def unpack_pol1(image: bytes) -> dict:
    """Recover .text without modifying the input; return bytes plus verifiable metadata."""
    text = _section(image, b".text")
    pol1 = _section(image, b"POL1")
    expected = text["virtual_size"]
    if expected <= 0 or expected > MAX_UNPACKED_SIZE:
        raise Pol1Error("unpacked size outside safety bounds")
    start, size = pol1["raw_start"], pol1["raw_size"]
    if start > len(image) or size > len(image) - start:
        raise Pol1Error("POL1 bytes outside file")
    packed = memoryview(image)[start:start + size]
    at = 0
    output = bytearray()
    while at < len(packed) and len(output) < expected:
        control = packed[at]
        at += 1
        for _ in range(8):
            if len(output) == expected:
                break
            literal = bool(control & 0x80)
            control = (control << 1) & 0xff
            if literal:
                if at >= len(packed):
                    break
                output.append(packed[at])
                at += 1
            else:
                if at + 2 > len(packed):
                    break
                word = (int(packed[at]) << 8) | int(packed[at + 1])
                at += 2
                distance = word & 0xfff
                if distance == 0:
                    break
                if distance > len(output):
                    raise Pol1Error("invalid back-reference")
                count = min((word >> 12) + 3, expected - len(output))
                for _ in range(count):
                    output.append(output[-distance])
    if len(output) != expected:
        raise Pol1Error(f"truncated stream ({len(output)} of {expected} bytes)")
    recovered = bytes(output)
    return {"base_rva": text["rva"], "bytes": recovered,
            "sha256": hashlib.sha256(recovered).hexdigest(),
            "size": len(recovered), "packed_size": len(packed)}


def inspect_pol1(path: str | Path) -> dict:
    """Metadata-only API for the Binary Inspector; never returns code to a template."""
    result = unpack_pol1(Path(path).read_bytes())
    return {key: value for key, value in result.items() if key != "bytes"}


def search_unpacked(path: str | Path, pattern: str, max_hits: int = 100) -> dict:
    """Find exact byte patterns in decoded .text, returning bounded RVA evidence.

    Patterns are two-digit hexadecimal bytes separated by spaces. The .text
    base is an RVA, not an offset into the packed DLL or a live address.
    """
    import re
    pieces = pattern.strip().split()
    if not 1 <= len(pieces) <= 64 or any(not re.fullmatch(r"[0-9a-fA-F]{2}", x) for x in pieces):
        raise ValueError("pattern requires 1-64 full hexadecimal bytes")
    needle = bytes.fromhex("".join(pieces))
    max_hits = max(1, min(int(max_hits), 200))
    decoded = unpack_pol1(Path(path).read_bytes())
    code = decoded["bytes"]
    hits = []
    offset = 0
    while len(hits) < max_hits:
        offset = code.find(needle, offset)
        if offset < 0:
            break
        start = max(0, offset - 12)
        end = min(len(code), offset + len(needle) + 12)
        hits.append({"rva": decoded["base_rva"] + offset,
                     "rva_hex": f"0x{decoded['base_rva'] + offset:X}",
                     "section_offset": offset,
                     "context_rva": decoded["base_rva"] + start,
                     "context_hex": code[start:end].hex(" ")})
        offset += 1
    return {"status": "VERIFIED_BYTES" if hits else "UNKNOWN",
            "pattern": pattern, "hits": hits, "limit_reached": len(hits) == max_hits,
            "unpacked_sha256": decoded["sha256"], "text_base_rva": decoded["base_rva"],
            "caution": "Byte matches do not establish instruction boundaries, execution, or semantic feature support."}
