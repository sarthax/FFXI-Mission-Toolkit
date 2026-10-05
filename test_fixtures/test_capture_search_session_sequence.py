#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import struct

from workbench.captures import (
    ffxi_blowfish,
    search_crypto_envelope,
    search_framing,
    search_session_sequence,
)


def _finalize_plain(packet: bytearray, seed: bytes) -> bytes:
    struct.pack_into("<H", packet, 0, len(packet))
    packet[4:8] = b"IXFF"
    packet[-4:] = seed
    hash_offset = len(packet) - search_crypto_envelope.SEARCH_TRAILER_SIZE
    packet[hash_offset:-4] = hashlib.md5(packet[8:hash_offset]).digest()
    return bytes(packet)


def _encrypt_inbound(decrypted: bytes) -> bytes:
    envelope = search_crypto_envelope.inspect_frame(decrypted)
    start = envelope["encrypted_region"]["offset_start"]
    end = envelope["encrypted_region"]["offset_end"]
    key = bytes.fromhex(envelope["key_derivation"]["derived_blowfish_key_hex"])
    wire = bytearray(decrypted)
    wire[start:end] = ffxi_blowfish.encrypt_blocks(decrypted[start:end], key)
    return bytes(wire)


def _encrypt_outbound(decrypted: bytes, state: bytes) -> bytes:
    envelope = search_crypto_envelope.inspect_frame(decrypted)
    start = envelope["encrypted_region"]["offset_start"]
    end = envelope["encrypted_region"]["offset_end"]
    wire = bytearray(decrypted)
    wire[start:end] = ffxi_blowfish.encrypt_blocks(decrypted[start:end], hashlib.md5(state).digest())
    return bytes(wire)


def _inbound_comment(player_id: int = 0x11223344) -> tuple[bytes, bytes]:
    packet = bytearray(40)
    packet[0x0B] = 0x08
    struct.pack_into("<I", packet, 0x10, player_id)
    plain = _finalize_plain(packet, bytes.fromhex("01020304"))
    return _encrypt_inbound(plain), plain


def _outbound_comment(state: bytes, player_id: int = 0x11223344) -> bytes:
    packet = bytearray(204)
    packet[0x08] = 154
    packet[0x0A] = 0x80
    packet[0x0B] = 0x88
    packet[0x0E] = 1
    struct.pack_into("<I", packet, 0x18, player_id)
    struct.pack_into("<H", packet, 0x1C, 124)
    comment = b"Session sequencing"
    packet[0x1E:0x1E + len(comment)] = comment
    packet[0x1E + len(comment):0x1E + 123] = b" " * (123 - len(comment))
    packet[0x9A] = 0
    plain = _finalize_plain(packet, state[16:20])
    return _encrypt_outbound(plain, state)


def _range(payload: bytes, seq_start: int, frames: list[int], *, gap_before: bool = False) -> dict:
    return {
        "seq_start": seq_start,
        "seq_end": seq_start + len(payload),
        "length": len(payload),
        "payload_hex": payload.hex().upper(),
        "frame_numbers": frames,
        "first_timestamp_seconds": float(frames[0]) if frames else None,
        "last_timestamp_seconds": float(frames[-1]) if frames else None,
        "gap_before": gap_before,
        "anomalies": {
            "retransmissions": [],
            "overlaps": [],
            "conflicting_overlaps": [],
            "missing_bytes_fabricated": False,
        },
    }


def _directions(inbound_ranges: list[dict], outbound_ranges: list[dict], *, gaps=None, conflicts=None) -> dict:
    return {
        "a_to_b": {
            "ranges": inbound_ranges,
            "gaps": list(gaps or []),
            "conflicting_overlaps": list(conflicts or []),
        },
        "b_to_a": {
            "ranges": outbound_ranges,
            "gaps": [],
            "conflicting_overlaps": [],
        },
    }


def _resolved_scan(directions: dict) -> dict:
    scanned = search_framing.scan_directions(directions)
    # endpoint b is the proven search server, therefore a_to_b is client -> server.
    return search_framing.resolve_crypto_direction(scanned, "b")


def main():
    inbound_wire, inbound_plain = _inbound_comment()
    inbound_validation = search_crypto_envelope.decrypt_inbound_frame(inbound_wire)
    assert inbound_validation["validated"] is True, inbound_validation
    state_evidence = search_crypto_envelope.derive_outbound_state(inbound_wire, inbound_plain)
    assert state_evidence["validated"] is True, state_evidence
    state = bytes.fromhex(state_evidence["state_hex"])
    outbound_wire = _outbound_comment(state)

    # Strictly separated capture-frame intervals prove cross-direction order without timestamps.
    directions = _directions(
        [_range(inbound_wire, 1000, [10])],
        [_range(outbound_wire, 5000, [11])],
    )
    sequenced = search_session_sequence.sequence_validated_session(_resolved_scan(directions), directions, "b")
    meta = sequenced["session_sequence"]
    assert meta["automatic_pairing_performed"] is True, meta
    assert meta["timestamps_used_for_pairing"] is False, meta
    assert meta["tcp_sequence_compared_across_directions"] is False, meta
    assert meta["status"] == "sequenced_with_strict_capture_order", meta
    pair = meta["pairs"][0]
    assert pair["paired"] is True, pair
    assert pair["certainty"] == "verified_capture_frame_interval_predecessor", pair
    assert pair["predecessor_capture_interval"] == [10, 10], pair
    assert pair["outbound_capture_interval"] == [11, 11], pair
    assert pair["predecessor_request_type_name"] == "SEARCH_COMMENT", pair
    assert pair["outbound_crypto"]["validated"] is True, pair
    assert pair["response"]["semantics_promoted"] is True, pair
    assert pair["response"]["response_type_name"] == "search_comment", pair
    assert pair["response"]["fields"]["player_id"] == 0x11223344, pair

    # Overlapping range provenance cannot prove whether the inbound bytes preceded the response.
    overlap_directions = _directions(
        [_range(inbound_wire, 1000, [10, 11])],
        [_range(outbound_wire, 5000, [11])],
    )
    overlap = search_session_sequence.sequence_validated_session(
        _resolved_scan(overlap_directions), overlap_directions, "b"
    )
    overlap_pair = overlap["session_sequence"]["pairs"][0]
    assert overlap_pair["paired"] is False, overlap_pair
    assert any(d["kind"] == "cross_direction_order_unresolved" for d in overlap_pair["diagnostics"]), overlap_pair

    # A client-stream gap could hide another request that changed the rolling server state.
    gap_directions = _directions(
        [_range(inbound_wire, 1000, [10], gap_before=True)],
        [_range(outbound_wire, 5000, [11])],
        gaps=[{"seq_start": 900, "seq_end": 1000, "length": 100}],
    )
    gap_result = search_session_sequence.sequence_validated_session(
        _resolved_scan(gap_directions), gap_directions, "b"
    )
    assert gap_result["session_sequence"]["automatic_pairing_performed"] is False, gap_result
    assert gap_result["session_sequence"]["status"] == "blocked_by_client_stream_integrity", gap_result

    # Never fall back to an older valid state if a later inbound candidate exists but cannot validate.
    bad_inbound = bytearray(inbound_wire)
    bad_inbound[8] ^= 0x80
    invalid_directions = _directions(
        [
            _range(inbound_wire, 1000, [10]),
            _range(bytes(bad_inbound), 1040, [11]),
        ],
        [_range(outbound_wire, 5000, [12])],
    )
    invalid = search_session_sequence.sequence_validated_session(
        _resolved_scan(invalid_directions), invalid_directions, "b"
    )
    invalid_pair = invalid["session_sequence"]["pairs"][0]
    assert invalid_pair["paired"] is False, invalid_pair
    assert any(
        d["kind"] == "latest_proven_inbound_predecessor_not_validated"
        for d in invalid_pair["diagnostics"]
    ), invalid_pair

    print("Strict search session sequencing regression: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
