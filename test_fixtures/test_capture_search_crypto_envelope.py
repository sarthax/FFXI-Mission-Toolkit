#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import struct

from workbench.captures import search_crypto_envelope, search_framing


def framed_wire_candidate() -> bytes:
    packet = bytearray(range(32))
    struct.pack_into("<H", packet, 0, len(packet))
    packet[2:4] = b"\x00\x00"
    packet[4:8] = b"IXFF"
    packet[-4:] = bytes.fromhex("01020304")
    return bytes(packet)


def validated_decrypted_candidate(packet_type: int = 0x03) -> bytes:
    packet = bytearray(32)
    struct.pack_into("<H", packet, 0, len(packet))
    packet[4:8] = b"IXFF"
    packet[8:12] = b"\x11\x22\x33" + bytes([packet_type])
    packet[-4:] = bytes.fromhex("01020304")
    packet[12:28] = hashlib.md5(packet[8:12]).digest()
    return bytes(packet)


def _range(payload: bytes, seq: int) -> dict:
    return {
        "seq_start": seq,
        "seq_end": seq + len(payload),
        "length": len(payload),
        "payload_hex": payload.hex().upper(),
        "frame_numbers": [1],
        "first_timestamp_seconds": 1.0,
        "last_timestamp_seconds": 1.0,
    }


def main():
    wire = framed_wire_candidate()
    scanned = search_framing.scan_range(wire, 9000)
    assert len(scanned["frames"]) == 1, scanned
    frame = scanned["frames"][0]
    assert frame["decoder_status"] == "encrypted_or_opaque", frame

    envelope = frame["crypto_envelope"]
    assert envelope["valid_envelope"] is True, envelope
    assert envelope["decoder_status"] == "crypto_envelope_only_not_decrypted", envelope
    assert envelope["direction_scope"] == "client_to_search_server_only", envelope
    assert envelope["applicability_requires_endpoint_role"] is True, envelope
    assert envelope["frame_seed"]["offset"] == 28, envelope
    assert envelope["frame_seed"]["raw_hex"] == "01020304", envelope
    assert envelope["key_derivation"]["input_length"] == 20, envelope
    assert envelope["key_derivation"]["derived_blowfish_key_hex"] == "6A15DA0320124399517BDF754E670064", envelope
    assert envelope["encrypted_region"] == {
        "offset_start": 8,
        "offset_end": 24,
        "length": 16,
        "block_size": 8,
        "raw_hex": wire[8:24].hex().upper(),
        "certainty": "verified_from_source_for_inbound_client_frame",
    }, envelope
    assert envelope["post_decrypt_hash_contract"]["hash_input_offset_start"] == 8, envelope
    assert envelope["post_decrypt_hash_contract"]["hash_input_offset_end"] == 12, envelope
    assert envelope["post_decrypt_hash_contract"]["expected_md5_offset"] == 12, envelope
    assert envelope["packet_type_contract"]["offset"] == 0x0B, envelope
    assert envelope["packet_type_contract"]["value"] is None, envelope
    assert envelope["outbound_warning"]["independently_derivable_from_outbound_frame"] is False, envelope

    bidirectional = search_framing.scan_directions({
        "a_to_b": {"ranges": [_range(wire, 10000)]},
        "b_to_a": {"ranges": [_range(wire, 11000)]},
    })
    # Endpoint role b means a_to_b is the client -> verified search server direction.
    search_framing.resolve_crypto_direction(bidirectional, "b")
    inbound = next(f for f in bidirectional["frames"] if f["direction"] == "a_to_b")
    outbound = next(f for f in bidirectional["frames"] if f["direction"] == "b_to_a")
    assert inbound["crypto_envelope"]["applicable_to_observed_direction"] is True, inbound
    assert inbound["crypto_envelope"]["key_derivation"]["applicable_to_observed_direction"] is True, inbound
    assert outbound["crypto_envelope"]["applicable_to_observed_direction"] is False, outbound
    assert outbound["crypto_envelope"]["key_derivation"]["applicable_to_observed_direction"] is False, outbound
    assert any(
        d["kind"] == "search_inbound_crypto_contract_direction_mismatch"
        for d in outbound["crypto_envelope"]["diagnostics"]
    ), outbound

    decrypted = validated_decrypted_candidate(0x03)
    validated = search_crypto_envelope.validate_decrypted_frame(decrypted)
    assert validated["validated"] is True, validated
    assert validated["direction_scope"] == "client_to_search_server_only", validated
    assert validated["post_decrypt_md5"]["valid"] is True, validated
    assert validated["packet_type"] == 0x03, validated
    assert validated["packet_type_evidence"]["certainty"] == "verified_after_post_decrypt_md5", validated

    corrupted = bytearray(decrypted)
    corrupted[8] ^= 0xFF
    rejected = search_crypto_envelope.validate_decrypted_frame(bytes(corrupted))
    assert rejected["validated"] is False, rejected
    assert rejected["packet_type"] is None, rejected
    assert any(d["kind"] == "search_post_decrypt_md5_mismatch" for d in rejected["diagnostics"]), rejected

    short = search_crypto_envelope.inspect_frame(b"\x00" * 20)
    assert short["valid_envelope"] is False, short
    assert any(d["kind"] == "truncated_search_crypto_envelope" for d in short["diagnostics"]), short

    print("Search crypto envelope regression: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
