"""Experimental POL1 stream encoder and read-only DLL fit assessment.

This module does not write or patch PE files. It exercises an inverse of the
synthetic POL1 LZSS format understood by workbench.client.pol1_unpack.
Successful decoding is NOT evidence that a retail loader accepts repacked code.
"""
from __future__ import annotations

from array import array
import hashlib
import struct

from workbench.client.pol1_unpack import Pol1Error, _section, unpack_pol1

MAX_DISTANCE = 0xFFF
MAX_MATCH = 18
MIN_MATCH = 3
MAX_CANDIDATES = 64
MAX_EXPERIMENTAL_SIZE = 8 * 1024 * 1024


def _key(code: bytes, i: int) -> int:
    return ((code[i] * 251 + code[i + 1]) * 251 + code[i + 2]) & 0xFFFF


def encode_pol1(code: bytes, *, search_depth: int = MAX_CANDIDATES) -> bytes:
    """Encode using MSB-first literal flags and 12-bit backward distances.

    This is a bounded greedy format experiment, not an exact inverse that
    promises matching bytes, compression ratio, or behavior of a retail packer.
    """
    if not isinstance(code, bytes) or not 0 < len(code) <= MAX_EXPERIMENTAL_SIZE:
        raise Pol1Error("decoded input must be nonempty bytes within 8 MiB experiment bound")
    if type(search_depth) is not int or search_depth not in (16, 64, 128):
        raise Pol1Error("search_depth must be 16, 64 or 128")
    # Fixed-size hash heads and 32-bit chains bound memory to O(input bytes),
    # unlike a dictionary of millions of unique three-byte substrings.
    heads = array("i", [-1]) * 65536
    previous = array("i", [-1]) * len(code)
    output = bytearray()
    pos = 0
    while pos < len(code):
        flag_at = len(output)
        output.append(0)
        flags = 0
        for bit in range(7, -1, -1):
            if pos >= len(code):
                break
            match_length = 0
            match_distance = 0
            if pos + MIN_MATCH <= len(code):
                search = heads[_key(code, pos)]
                tries = 0
                limit = min(MAX_MATCH, len(code) - pos)
                while search >= 0 and pos - search <= MAX_DISTANCE and tries < search_depth:
                    if code[search:search+MIN_MATCH] == code[pos:pos+MIN_MATCH]:
                        length = MIN_MATCH
                        while length < limit and code[search + length] == code[pos + length]:
                            length += 1
                        if length > match_length:
                            match_length = length
                            match_distance = pos - search
                            if length == MAX_MATCH:
                                break
                    search = previous[search]
                    tries += 1
            consumed = match_length if match_length >= MIN_MATCH else 1
            if match_length >= MIN_MATCH:
                word = ((match_length - 3) << 12) | match_distance
                output.extend(word.to_bytes(2, "big"))
            else:
                flags |= 1 << bit
                output.append(code[pos])
            for index in range(pos, pos + consumed):
                if index + MIN_MATCH <= len(code):
                    hashed = _key(code, index)
                    previous[index] = heads[hashed]
                    heads[hashed] = index
            pos += consumed
        output[flag_at] = flags
    return bytes(output)




def _verify_raw_section_isolation(image: bytes, section: dict) -> None:
    """Reject overlapping POL1 raw ranges and PE header/section table overlap.

    This is a conservative file-layout preflight, *not* a proof that Windows or
    FFXI can load any modified image.
    """
    pe = struct.unpack_from("<I", image, 0x3C)[0]
    count = struct.unpack_from("<H", image, pe + 6)[0]
    optional = struct.unpack_from("<H", image, pe + 20)[0]
    table = pe + 24 + optional
    if not 1 <= count <= 96 or table + count * 40 > len(image):
        raise Pol1Error("invalid PE section table bounds")
    start, size = section["raw_start"], section["raw_size"]
    if start < table + count * 40 or size <= 0 or start > len(image) or size > len(image) - start:
        raise Pol1Error("POL1 raw section overlaps PE headers or exceeds file")
    end = start + size
    for i in range(count):
        off = table + i * 40
        name = image[off:off + 8].rstrip(b"\x00")
        if name == b"POL1":
            continue
        raw_size, raw_start = struct.unpack_from("<II", image, off + 16)
        if raw_size == 0:
            continue
        if raw_start > len(image) or raw_size > len(image) - raw_start:
            raise Pol1Error("other PE section exceeds file")
        if max(start, raw_start) < min(end, raw_start + raw_size):
            raise Pol1Error("POL1 raw section overlaps another PE section")



def _stream_consumed_bytes(image: bytes, expected_size: int) -> int:
    """Strictly count consumed original LZSS stream bytes without PE-tail spill.

    Unlike the legacy read-only decoder, which tolerates a zero-distance token
    as a group terminator, this safety-critical measurement fails closed:
    ambiguous or malformed streams cannot establish a replaceable prefix.
    """
    section = _section(image, b"POL1")
    start, size = section["raw_start"], section["raw_size"]
    if start > len(image) or size > len(image) - start:
        raise Pol1Error("POL1 section exceeds source file")
    if not 0 < expected_size <= MAX_EXPERIMENTAL_SIZE:
        raise Pol1Error("decoded stream outside experimental bound")
    data = memoryview(image)[start:start + size]
    pos = 0
    expanded = 0
    while expanded < expected_size:
        if pos >= size:
            raise Pol1Error("truncated POL1 control group")
        flags = data[pos]
        pos += 1
        for shift in range(7, -1, -1):
            if expanded == expected_size:
                break
            if (flags >> shift) & 1:
                if pos >= size:
                    raise Pol1Error("truncated POL1 literal")
                pos += 1
                expanded += 1
            else:
                if pos + 2 > size:
                    raise Pol1Error("truncated POL1 back-reference")
                word = (int(data[pos]) << 8) | int(data[pos + 1])
                pos += 2
                distance = word & MAX_DISTANCE
                if distance == 0 or distance > expanded:
                    raise Pol1Error("invalid POL1 back-reference while measuring consumption")
                expanded += min((word >> 12) + MIN_MATCH, expected_size - expanded)
    return pos


def _entrypoint_section_offset(image: bytes, section: dict) -> int | None:
    """Map a structurally checked PE entry point into POL1's raw bytes."""
    if len(image) < 0x40 or image[:2] != b"MZ":
        raise Pol1Error("missing DOS signature")
    pe = struct.unpack_from("<I", image, 0x3C)[0]
    if pe < 0x40 or pe + 24 > len(image) or image[pe:pe + 4] != bytes((80, 69, 0, 0)):
        raise Pol1Error("invalid PE signature/header")
    optional_size = struct.unpack_from("<H", image, pe + 20)[0]
    optional = pe + 24
    if optional_size < 20 or optional + optional_size > len(image):
        raise Pol1Error("missing or truncated PE optional header")
    magic = struct.unpack_from("<H", image, optional)[0]
    if magic not in (0x10B, 0x20B):
        raise Pol1Error("unsupported PE optional-header magic")
    entry_rva = struct.unpack_from("<I", image, optional + 16)[0]
    relative = entry_rva - section["rva"]
    if 0 <= relative < section["raw_size"]:
        return relative
    return None


def assess_pol1_repack_fit(
    image: bytes, candidate_code: bytes | None = None, *, search_depth: int = MAX_CANDIDATES
) -> dict:
    """Report whether greedy encoding fits existing POL1 raw bytes; never write.

    'fits' means byte capacity only; neither a patch nor retail boot acceptance.
    """
    if not isinstance(image, bytes):
        raise Pol1Error("image must be bytes")
    section = _section(image, b"POL1")
    _entrypoint_section_offset(image, section)  # Validate DOS/PE metadata before decoding.
    _verify_raw_section_isolation(image, section)
    original = unpack_pol1(image)
    code = original["bytes"] if candidate_code is None else candidate_code
    if not isinstance(code, bytes) or len(code) != original["size"]:
        raise Pol1Error("candidate decoded code must match original decoded length")
    candidate = encode_pol1(code, search_depth=search_depth)
    start, available = section["raw_start"], section["raw_size"]
    original_used = _stream_consumed_bytes(image, original["size"])
    entrypoint_offset = _entrypoint_section_offset(image, section)
    boundary_valid = entrypoint_offset is None or original_used <= entrypoint_offset
    # Never use the tail of the raw section for growth: it may contain startup
    # instructions, loader metadata, or resources unrelated to compressed data.
    budget = min(original_used, entrypoint_offset) if entrypoint_offset is not None else original_used
    fits = boundary_valid and len(candidate) <= budget
    result = {
        "status": ("UNSAFE_ORIGINAL_STREAM_BOUNDARY" if not boundary_valid else
                   "FITS_ORIGINAL_STREAM_BUDGET" if fits else "EXCEEDS_ORIGINAL_STREAM_BUDGET"),
        "source_sha256": hashlib.sha256(image).hexdigest(),
        "decoded_sha256": original["sha256"],
        "candidate_decoded_sha256": hashlib.sha256(code).hexdigest(),
        "decoded_size": original["size"],
        "pol1_raw_section_size": available,
        "original_stream_consumed_bytes": original_used,
        "protected_suffix_bytes": available - original_used,
        "entrypoint_section_offset": entrypoint_offset,
        "pol1_raw_section_isolated": True,
        "entrypoint_in_pol1": entrypoint_offset is not None,
        "entrypoint_boundary_safe": boundary_valid,
        "safe_stream_budget_bytes": budget,
        "candidate_encoded_size": len(candidate),
        "encoder_search_depth": search_depth,
        "headroom_bytes": budget - len(candidate),
        "candidate_sha256": hashlib.sha256(candidate).hexdigest(),
        "caution": ("In-memory capacity estimate only; full POL1 section is NOT writable "
                    "slack. No retail DLL is modified or launched."),
    }
    if fits:
        # Only the decoded stream's existing prefix is substituted in memory;
        # do not clear or replace the protected suffix (which can contain the
        # original POL1 bootstrap entry point).
        candidate_image = bytearray(image)
        candidate_image[start:start + len(candidate)] = candidate
        check = unpack_pol1(bytes(candidate_image))
        if check["bytes"] != code:
            raise Pol1Error("in-memory candidate failed decoded-byte verification")
        if candidate_image[start + original_used:start + available] != image[start + original_used:start + available]:
            raise Pol1Error("protected POL1 suffix was altered")
        result["in_memory_decoded_roundtrip"] = "PASS"
        result["protected_suffix_unchanged"] = True
    else:
        result["in_memory_decoded_roundtrip"] = "NOT_ATTEMPTED"
        result["protected_suffix_unchanged"] = None
    return result
