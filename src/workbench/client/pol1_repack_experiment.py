"""Experimental POL1 stream encoder and read-only DLL fit assessment.

This module does not write or patch PE files. It exercises an inverse of the
synthetic POL1 LZSS format understood by workbench.client.pol1_unpack.
Successful decoding is NOT evidence that a retail loader accepts repacked code.
"""
from __future__ import annotations

from array import array
import hashlib

from workbench.client.pol1_unpack import Pol1Error, _section, unpack_pol1

MAX_DISTANCE = 0xFFF
MAX_MATCH = 18
MIN_MATCH = 3
MAX_CANDIDATES = 64
MAX_EXPERIMENTAL_SIZE = 8 * 1024 * 1024


def _key(code: bytes, i: int) -> int:
    return ((code[i] * 251 + code[i + 1]) * 251 + code[i + 2]) & 0xFFFF


def encode_pol1(code: bytes) -> bytes:
    """Encode using MSB-first literal flags and 12-bit backward distances.

    This is a bounded greedy format experiment, not an exact inverse that
    promises matching bytes, compression ratio, or behavior of a retail packer.
    """
    if not isinstance(code, bytes) or not 0 < len(code) <= MAX_EXPERIMENTAL_SIZE:
        raise Pol1Error("decoded input must be nonempty bytes within 8 MiB experiment bound")
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
                while search >= 0 and pos - search <= MAX_DISTANCE and tries < MAX_CANDIDATES:
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


def assess_pol1_repack_fit(image: bytes, candidate_code: bytes | None = None) -> dict:
    """Report whether greedy encoding fits existing POL1 raw bytes; never write.

    'fits' means byte capacity only; neither a patch nor retail boot acceptance.
    """
    if not isinstance(image, bytes):
        raise Pol1Error("image must be bytes")
    section = _section(image, b"POL1")
    original = unpack_pol1(image)
    code = original["bytes"] if candidate_code is None else candidate_code
    if not isinstance(code, bytes) or len(code) != original["size"]:
        raise Pol1Error("candidate decoded code must match original decoded length")
    candidate = encode_pol1(code)
    # Re-run the existing decoder against a temporary in-memory candidate
    # using unchanged PE sections. The original byte string is untouched.
    start, available = section["raw_start"], section["raw_size"]
    fits = len(candidate) <= available
    result = {
        "status": "FITS_RAW_SECTION" if fits else "EXCEEDS_RAW_SECTION",
        "source_sha256": hashlib.sha256(image).hexdigest(),
        "decoded_sha256": original["sha256"],
        "candidate_decoded_sha256": hashlib.sha256(code).hexdigest(),
        "decoded_size": original["size"],
        "pol1_raw_section_capacity": available,
        "candidate_encoded_size": len(candidate),
        "headroom_bytes": available - len(candidate),
        "candidate_sha256": hashlib.sha256(candidate).hexdigest(),
        "caution": "Capacity-only read-only estimate; no DLL written, no loader/signature or Windows execution verification.",
    }
    if fits:
        patched = bytearray(image)
        patched[start:start + available] = candidate + bytes(available - len(candidate))
        check = unpack_pol1(bytes(patched))
        if check["bytes"] != code:
            raise Pol1Error("in-memory candidate failed decoded-byte verification")
        result["in_memory_decoded_roundtrip"] = "PASS"
    else:
        result["in_memory_decoded_roundtrip"] = "NOT_ATTEMPTED"
    return result
