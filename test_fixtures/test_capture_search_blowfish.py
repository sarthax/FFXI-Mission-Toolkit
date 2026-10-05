#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import struct

from workbench.captures import ffxi_blowfish, search_crypto_envelope, search_framing


def decrypted_search_comment(
    player_id: int = 0x11223344,
    seed: bytes = b"\x01\x02\x03\x04",
) -> bytes:
    packet = bytearray(40)
    struct.pack_into("<H", packet, 0, len(packet))
    packet[4:8] = b"IXFF"
    packet[8:12] = b"\x11\x22\x33\x08"  # request type 0x08 at offset 0x0B
    struct.pack_into("<I", packet, 0x10, player_id)
    packet[-4:] = seed
    hash_offset = len(packet) - search_crypto_envelope.SEARCH_TRAILER_SIZE
    packet[hash_offset:-4] = hashlib.md5(packet[8:hash_offset]).digest()
    return bytes(packet)


def encrypt_inbound_frame(decrypted: bytes) -> bytes:
    envelope = search_crypto_envelope.inspect_frame(decrypted)
    assert envelope["valid_envelope"] is True, envelope
    start = envelope["encrypted_region"]["offset_start"]
    end = envelope["encrypted_region"]["offset_end"]
    key = bytes.fromhex(envelope["key_derivation"]["derived_blowfish_key_hex"])
    encrypted = bytearray(decrypted)
    encrypted[start:end] = ffxi_blowfish.encrypt_blocks(decrypted[start:end], key)
    return bytes(encrypted)


def decrypted_server_response(state: bytes) -> bytes:
    packet = bytearray(40)
    struct.pack_into("<H", packet, 0, len(packet))
    packet[4:8] = b"IXFF"
    # Deliberately opaque response bytes: this fixture proves crypto/state only, not response schema.
    packet[8:20] = bytes.fromhex("A1A2A3A4A5A6A7A8A9AAABAC")
    packet[-4:] = state[16:20]
    hash_offset = len(packet) - search_crypto_envelope.SEARCH_TRAILER_SIZE
    packet[hash_offset:-4] = hashlib.md5(packet[8:hash_offset]).digest()
    return bytes(packet)


def encrypt_outbound_frame(decrypted: bytes, state: bytes) -> bytes:
    envelope = search_crypto_envelope.inspect_frame(decrypted)
    start = envelope["encrypted_region"]["offset_start"]
    end = envelope["encrypted_region"]["offset_end"]
    key = hashlib.md5(state).digest()
    encrypted = bytearray(decrypted)
    encrypted[start:end] = ffxi_blowfish.encrypt_blocks(decrypted[start:end], key)
    return bytes(encrypted)


def one_range(payload: bytes) -> dict:
    return {
        "ranges": [{
            "seq_start": 1000,
            "seq_end": 1000 + len(payload),
            "length": len(payload),
            "payload_hex": payload.hex().upper(),
            "frame_numbers": [1],
            "first_timestamp_seconds": 1.0,
            "last_timestamp_seconds": 1.0,
        }],
        "gaps": [], "retransmissions": [], "overlaps": [], "conflicting_overlaps": [],
    }


def main():
    # Independent deterministic block vector cross-checked against the LSB-compatible C primitive.
    key = bytes.fromhex("6A15DA0320124399517BDF754E670064")
    plaintext = bytes.fromhex("0001020304050607")
    ciphertext = ffxi_blowfish.encrypt_blocks(plaintext, key)
    assert ciphertext.hex().upper() == "00D103BFB60109A0", ciphertext.hex()
    assert ffxi_blowfish.decrypt_blocks(ciphertext, key) == plaintext

    decrypted = decrypted_search_comment()
    wire = encrypt_inbound_frame(decrypted)
    envelope = search_crypto_envelope.inspect_frame(wire)
    start = envelope["encrypted_region"]["offset_start"]
    end = envelope["encrypted_region"]["offset_end"]
    assert wire[:8] == decrypted[:8]
    assert wire[-4:] == decrypted[-4:]
    assert wire[start:end] != decrypted[start:end]

    decoded = search_crypto_envelope.decrypt_inbound_frame(wire)
    assert decoded["decryption_performed"] is True, decoded
    assert decoded["validated"] is True, decoded
    assert decoded["decoder_status"] == "decrypted_and_validated", decoded
    assert decoded["packet_type"] == 0x08, decoded
    assert decoded["packet_type_name"] == "SEARCH_COMMENT", decoded
    assert bytes.fromhex(decoded["decrypted_hex"]) == decrypted, decoded

    # Direction resolution is the higher-level gate: only client -> verified search endpoint decrypts
    # and only the validated inbound packet reaches request-field decoding.
    scan = search_framing.scan_directions({
        "a_to_b": one_range(wire),
        "b_to_a": one_range(wire),
    })
    search_framing.resolve_crypto_direction(scan, "b")
    inbound = next(f for f in scan["frames"] if f["direction"] == "a_to_b")
    outbound = next(f for f in scan["frames"] if f["direction"] == "b_to_a")
    assert inbound["decryption_validated"] is True, inbound
    assert inbound["validated_packet_type_name"] == "SEARCH_COMMENT", inbound
    assert inbound["inbound_decryption"]["validated"] is True, inbound
    assert inbound["validated_request"]["decoder_status"] == "validated_basic_request_fields_decoded", inbound
    assert inbound["validated_request"]["fields"]["player_id"] == 0x11223344, inbound
    assert inbound["validated_request"]["field_evidence"]["player_id"]["offset"] == 0x10, inbound
    assert "inbound_decryption" not in outbound, outbound
    assert "validated_request" not in outbound, outbound
    assert outbound["crypto_envelope"]["applicable_to_observed_direction"] is False, outbound

    # A validated inbound observation yields the exact 24-byte state needed by server encryption.
    state_evidence = search_crypto_envelope.derive_outbound_state(wire, decrypted)
    assert state_evidence["validated"] is True, state_evidence
    assert state_evidence["state_length"] == 24, state_evidence
    assert state_evidence["inbound_seed_hex"] == "01020304", state_evidence
    assert state_evidence["continuation_offset"] == 0x10, state_evidence
    assert state_evidence["continuation_hex"] == "44332211", state_evidence
    state = bytes.fromhex(state_evidence["state_hex"])

    # Server response crypto can now be validated with explicit predecessor state while response
    # payload semantics remain intentionally opaque.
    server_plain = decrypted_server_response(state)
    server_wire = encrypt_outbound_frame(server_plain, state)
    server_decoded = search_crypto_envelope.decrypt_outbound_frame(server_wire, state_evidence)
    assert server_decoded["decryption_performed"] is True, server_decoded
    assert server_decoded["validated"] is True, server_decoded
    assert server_decoded["decoder_status"] == "outbound_decrypted_and_validated", server_decoded
    assert server_decoded["payload_semantics"] == "unknown_opaque", server_decoded
    assert bytes.fromhex(server_decoded["decrypted_hex"]) == server_plain, server_decoded

    wrong_state = bytearray(state)
    wrong_state[16] ^= 0xFF
    rejected_state = search_crypto_envelope.decrypt_outbound_frame(server_wire, bytes(wrong_state))
    assert rejected_state["validated"] is False, rejected_state
    assert rejected_state["decryption_performed"] is False, rejected_state
    assert any(d["kind"] == "search_outbound_state_seed_mismatch" for d in rejected_state["diagnostics"]), rejected_state

    corrupted = bytearray(wire)
    corrupted[8] ^= 0x80
    rejected = search_crypto_envelope.decrypt_inbound_frame(bytes(corrupted))
    assert rejected["decryption_performed"] is True, rejected
    assert rejected["validated"] is False, rejected
    assert rejected["decoder_status"] == "decrypted_candidate_rejected", rejected
    assert rejected.get("packet_type") is None, rejected

    try:
        ffxi_blowfish.decrypt_blocks(b"1234567", key)
    except ValueError:
        pass
    else:
        raise AssertionError("unaligned block input must fail closed")

    print("FFXI search Blowfish compatibility regression: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
