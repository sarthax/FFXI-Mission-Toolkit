#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import struct

from workbench.captures import ffxi_blowfish, search_crypto_envelope, search_framing


def decrypted_search_frame(packet_type: int = 0x03, seed: bytes = b"\x01\x02\x03\x04") -> bytes:
    packet = bytearray(32)
    struct.pack_into("<H", packet, 0, len(packet))
    packet[4:8] = b"IXFF"
    packet[8:12] = b"\x11\x22\x33" + bytes([packet_type])
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

    decrypted = decrypted_search_frame(0x03)
    wire = encrypt_inbound_frame(decrypted)
    assert wire[:8] == decrypted[:8]
    assert wire[-4:] == decrypted[-4:]
    assert wire[8:24] != decrypted[8:24]

    decoded = search_crypto_envelope.decrypt_inbound_frame(wire)
    assert decoded["decryption_performed"] is True, decoded
    assert decoded["validated"] is True, decoded
    assert decoded["decoder_status"] == "decrypted_and_validated", decoded
    assert decoded["packet_type"] == 0x03, decoded
    assert decoded["packet_type_name"] == "SEARCH", decoded
    assert bytes.fromhex(decoded["decrypted_hex"]) == decrypted, decoded

    # Direction resolution is the higher-level gate: only client -> verified search endpoint decrypts.
    scan = search_framing.scan_directions({
        "a_to_b": one_range(wire),
        "b_to_a": one_range(wire),
    })
    search_framing.resolve_crypto_direction(scan, "b")
    inbound = next(f for f in scan["frames"] if f["direction"] == "a_to_b")
    outbound = next(f for f in scan["frames"] if f["direction"] == "b_to_a")
    assert inbound["decryption_validated"] is True, inbound
    assert inbound["validated_packet_type_name"] == "SEARCH", inbound
    assert inbound["inbound_decryption"]["validated"] is True, inbound
    assert "inbound_decryption" not in outbound, outbound
    assert outbound["crypto_envelope"]["applicable_to_observed_direction"] is False, outbound

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
