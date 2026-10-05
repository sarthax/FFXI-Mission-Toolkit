"""Source-backed framing observations for FFXI search/cache TCP streams.

LandSandBoat's search server leaves the packet length at offset 0 and the IXFF marker at offsets
4..7 clear on writes, then encrypts the payload beginning at offset 8. Incoming packets are rejected
when the observed TCP read length differs from the little-endian uint16 at offset 0 or is shorter
than 28 bytes before decryption/validation.

This module therefore recognizes *frame candidates* only. It does not decrypt or assign packet-type/
gameplay semantics. Search-family attribution belongs to the higher-level classifier and must be
backed by independent endpoint evidence. For accepted candidates, source-backed crypto-envelope
metadata is attached without exposing a packet type before decryption and hash validation.
"""
from __future__ import annotations

import struct

from workbench.captures import search_crypto_envelope

SEARCH_MIN_FRAME_SIZE = 28
SEARCH_MARKER = b"IXFF"
SEARCH_MAX_FRAME_SIZE = 0xFFFF


def scan_range(payload: bytes, seq_start: int = 0) -> dict:
    """Recover source-backed search frame candidates from one contiguous TCP byte range.

    The scanner may resynchronize after opaque bytes, but every accepted candidate requires:
    - little-endian uint16 declared size at offset 0;
    - declared size >= 28;
    - literal IXFF at offsets 4..7;
    - the complete declared frame to be present in this observed contiguous range.

    Returned payload bytes remain opaque/encrypted from offset 8 onward.
    """
    frames: list[dict] = []
    diagnostics: list[dict] = []
    pos = 0
    skipped_start: int | None = None

    while pos < len(payload):
        remaining = len(payload) - pos
        if remaining < 8:
            if remaining:
                diagnostics.append({
                    "kind": "opaque_trailing_bytes",
                    "range_offset": pos,
                    "seq_start": seq_start + pos,
                    "length": remaining,
                    "raw_slice_hex": payload[pos:].hex().upper(),
                    "certainty": "verified_observation",
                })
            break

        declared = struct.unpack_from("<H", payload, pos)[0]
        marker = payload[pos + 4:pos + 8]
        plausible = SEARCH_MIN_FRAME_SIZE <= declared <= SEARCH_MAX_FRAME_SIZE and marker == SEARCH_MARKER
        if not plausible:
            if skipped_start is None:
                skipped_start = pos
            pos += 1
            continue

        if skipped_start is not None:
            diagnostics.append({
                "kind": "framing_resynchronization",
                "range_offset": skipped_start,
                "seq_start": seq_start + skipped_start,
                "skipped_length": pos - skipped_start,
                "raw_slice_hex": payload[skipped_start:pos].hex().upper(),
                "certainty": "structurally_inferred",
            })
            skipped_start = None

        end = pos + declared
        if end > len(payload):
            diagnostics.append({
                "kind": "truncated_frame_candidate",
                "range_offset": pos,
                "seq_start": seq_start + pos,
                "declared_size": declared,
                "observed_size": len(payload) - pos,
                "raw_slice_hex": payload[pos:].hex().upper(),
                "certainty": "structurally_inferred",
            })
            break

        raw = payload[pos:end]
        frames.append({
            "range_offset": pos,
            "seq_start": seq_start + pos,
            "seq_end": seq_start + end,
            "declared_size": declared,
            "marker": "IXFF",
            "raw_hex": raw.hex().upper(),
            "clear_header_hex": raw[:8].hex().upper(),
            "opaque_payload_hex": raw[8:].hex().upper(),
            "framing_certainty": "structurally_inferred",
            "framing_provenance": "LandSandBoat SearchHandler read_func/encrypt clear length+IXFF",
            "decoder_status": "encrypted_or_opaque",
            "crypto_envelope": search_crypto_envelope.inspect_frame(raw),
        })
        pos = end

    return {"frames": frames, "diagnostics": diagnostics}


def scan_directions(directions: dict[str, dict]) -> dict:
    """Scan reconstructed ranges in both directions without assigning endpoint roles."""
    frames: list[dict] = []
    diagnostics: list[dict] = []
    for direction in ("a_to_b", "b_to_a"):
        for range_index, rr in enumerate((directions.get(direction) or {}).get("ranges") or []):
            payload_hex = rr.get("payload_hex") or ""
            payload = bytes.fromhex(payload_hex) if payload_hex else b""
            scanned = scan_range(payload, int(rr.get("seq_start") or 0))
            for frame_index, frame in enumerate(scanned["frames"]):
                frames.append({
                    "direction": direction,
                    "range_index": range_index,
                    "frame_index": frame_index,
                    **frame,
                })
            for diagnostic in scanned["diagnostics"]:
                diagnostics.append({
                    "direction": direction,
                    "range_index": range_index,
                    **diagnostic,
                })
    return {"frames": frames, "diagnostics": diagnostics}
