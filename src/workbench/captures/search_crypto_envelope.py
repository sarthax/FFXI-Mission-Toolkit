"""Source-backed cryptographic envelope metadata for FFXI search/cache TCP frames.

This module deliberately does not implement Blowfish.  It records the exact clear/encrypted/hash/key
regions and per-frame key derivation used by LandSandBoat's inbound SearchHandler so a later decoder
can prove decryption before exposing packet type or semantic fields.
"""
from __future__ import annotations

import hashlib


# LandSandBoat SearchHandler::key[0:16].  Inbound decrypt copies the frame's final uint32 into
# key[16:20], hashes exactly those first 20 bytes with MD5, and uses the resulting 16-byte digest
# to initialize Blowfish for that one frame.
_SEARCH_BASE_KEY = bytes.fromhex("30733D6D3C31495A327A424363387B7E")
SEARCH_HEADER_SIZE = 8
SEARCH_HASH_SIZE = 16
SEARCH_SEED_SIZE = 4
SEARCH_TRAILER_SIZE = SEARCH_HASH_SIZE + SEARCH_SEED_SIZE
SEARCH_MIN_FRAME_SIZE = 28


def inspect_frame(raw: bytes) -> dict:
    """Describe LSB's inbound search crypto envelope without decrypting it.

    The caller is expected to have already established the clear search framing.  This function
    remains fail-closed for short frames and never interprets the encrypted packet-type byte.
    """
    result = {
        "valid_envelope": False,
        "certainty": "unknown_opaque",
        "raw_length": len(raw),
        "decoder_status": "crypto_envelope_only_not_decrypted",
        "diagnostics": [],
    }
    if len(raw) < SEARCH_MIN_FRAME_SIZE:
        result["diagnostics"].append({
            "kind": "truncated_search_crypto_envelope",
            "minimum_length": SEARCH_MIN_FRAME_SIZE,
            "observed_length": len(raw),
        })
        return result

    length = len(raw)
    seed_offset = length - SEARCH_SEED_SIZE
    hash_offset = length - SEARCH_TRAILER_SIZE
    hashed_plaintext_start = SEARCH_HEADER_SIZE
    hashed_plaintext_end = hash_offset

    # Mirrors: tmp = (length - 12) / 4; tmp -= tmp % 2; each pair is one 8-byte BF block.
    encrypted_word_count = (length - 12) // 4
    encrypted_word_count -= encrypted_word_count % 2
    encrypted_length = encrypted_word_count * 4
    encrypted_start = SEARCH_HEADER_SIZE
    encrypted_end = encrypted_start + encrypted_length

    seed = raw[seed_offset:length]
    key_input = _SEARCH_BASE_KEY + seed
    derived_key = hashlib.md5(key_input).digest()

    result.update({
        "valid_envelope": True,
        "certainty": "verified_structure",
        "clear_header": {
            "offset": 0,
            "length": SEARCH_HEADER_SIZE,
            "raw_hex": raw[:SEARCH_HEADER_SIZE].hex().upper(),
        },
        "frame_seed": {
            "offset": seed_offset,
            "length": SEARCH_SEED_SIZE,
            "raw_hex": seed.hex().upper(),
            "certainty": "verified_observation",
            "provenance": "LandSandBoat SearchHandler::decrypt frame[-4:] -> key[16:20]",
        },
        "key_derivation": {
            "algorithm": "MD5",
            "input_length": 20,
            "fixed_prefix_length": 16,
            "frame_seed_length": 4,
            "derived_blowfish_key_hex": derived_key.hex().upper(),
            "certainty": "verified_from_source",
        },
        "encrypted_region": {
            "offset_start": encrypted_start,
            "offset_end": encrypted_end,
            "length": encrypted_length,
            "block_size": 8,
            "raw_hex": raw[encrypted_start:encrypted_end].hex().upper(),
            "certainty": "verified_from_source",
        },
        "post_decrypt_hash_contract": {
            "hash_input_offset_start": hashed_plaintext_start,
            "hash_input_offset_end": hashed_plaintext_end,
            "hash_input_length": hashed_plaintext_end - hashed_plaintext_start,
            "expected_md5_offset": hash_offset,
            "expected_md5_length": SEARCH_HASH_SIZE,
            "expected_md5_raw_hex_pre_decrypt": raw[hash_offset:seed_offset].hex().upper(),
            "algorithm": "MD5",
            "validation_available_only_after_decryption": True,
            "certainty": "verified_from_source",
        },
        "packet_type_contract": {
            "offset": 0x0B,
            "readable_only_after_decryption_and_hash_validation": True,
            "value": None,
            "certainty": "not_decoded",
        },
        "server_key_continuation_contract": {
            "post_decrypt_source_offset": length - 0x18,
            "length": 4,
            "meaning": "copied to SearchHandler key[20:24] after inbound decrypt for subsequent server-side encryption state",
            "value": None,
            "certainty": "not_decoded",
        },
    })
    return result


def validate_decrypted_frame(decrypted: bytes) -> dict:
    """Validate an externally decrypted candidate using LSB's post-decrypt MD5 contract.

    This helper does not perform or trust decryption itself.  It only promotes packet-type evidence
    if the supplied bytes have a valid length and post-decrypt MD5.  The first 8 clear bytes and
    final 4-byte seed are expected to remain in their wire positions.
    """
    result = {
        "validated": False,
        "certainty": "unknown_opaque",
        "diagnostics": [],
        "packet_type": None,
    }
    if len(decrypted) < SEARCH_MIN_FRAME_SIZE:
        result["diagnostics"].append({
            "kind": "truncated_decrypted_search_candidate",
            "minimum_length": SEARCH_MIN_FRAME_SIZE,
            "observed_length": len(decrypted),
        })
        return result

    hash_offset = len(decrypted) - SEARCH_TRAILER_SIZE
    seed_offset = len(decrypted) - SEARCH_SEED_SIZE
    computed = hashlib.md5(decrypted[SEARCH_HEADER_SIZE:hash_offset]).digest()
    observed = decrypted[hash_offset:seed_offset]
    result["post_decrypt_md5"] = {
        "computed_hex": computed.hex().upper(),
        "observed_hex": observed.hex().upper(),
        "valid": computed == observed,
        "offset": hash_offset,
        "length": SEARCH_HASH_SIZE,
    }
    if computed != observed:
        result["diagnostics"].append({"kind": "search_post_decrypt_md5_mismatch"})
        return result

    result["validated"] = True
    result["certainty"] = "verified"
    result["packet_type"] = decrypted[0x0B]
    result["packet_type_evidence"] = {
        "offset": 0x0B,
        "value": decrypted[0x0B],
        "certainty": "verified_after_post_decrypt_md5",
        "provenance": "LandSandBoat SearchHandler::read_func after decrypt()+validatePacket()",
    }
    return result
