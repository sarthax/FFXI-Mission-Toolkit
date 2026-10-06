"""Source-backed search/cache cryptographic envelope and validated transform helpers.

Inbound client-to-search-server frames are independently decryptable from their own final 4-byte
seed. Server-to-client frames require rolling 24-byte state established by a previously validated
inbound frame, so outbound decryption is exposed only through an explicit state handoff helper.
"""
from __future__ import annotations

import hashlib

from workbench.captures import ffxi_blowfish


_SEARCH_BASE_KEY = bytes.fromhex("30733D6D3C31495A327A424363387B7E")
SEARCH_HEADER_SIZE = 8
SEARCH_HASH_SIZE = 16
SEARCH_SEED_SIZE = 4
SEARCH_TRAILER_SIZE = SEARCH_HASH_SIZE + SEARCH_SEED_SIZE
SEARCH_MIN_FRAME_SIZE = 28
SEARCH_MARKER = b"IXFF"

SEARCH_REQUEST_TYPES = {
    0x00: "SEARCH_ALL",
    0x01: "ID_LIST",
    0x02: "GROUP_LIST",
    0x03: "SEARCH",
    0x05: "AH_HISTORY_SINGLE",
    0x06: "AH_HISTORY_STACK",
    0x08: "SEARCH_COMMENT",
    0x10: "AH_REQUEST_MORE",
    0x15: "AH_REQUEST",
}


def _encrypted_region(length: int) -> tuple[int, int]:
    encrypted_word_count = (length - 12) // 4
    encrypted_word_count -= encrypted_word_count % 2
    return SEARCH_HEADER_SIZE, SEARCH_HEADER_SIZE + encrypted_word_count * 4


def inspect_frame(raw: bytes) -> dict:
    """Describe the source-backed inbound crypto envelope without decrypting it."""
    result = {
        "valid_envelope": False,
        "certainty": "unknown_opaque",
        "raw_length": len(raw),
        "decoder_status": "crypto_envelope_only_not_decrypted",
        "direction_scope": "client_to_search_server_only",
        "applicability_requires_endpoint_role": True,
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
    encrypted_start, encrypted_end = _encrypted_region(length)
    seed = raw[seed_offset:length]
    derived_key = hashlib.md5(_SEARCH_BASE_KEY + seed).digest()

    result.update({
        "valid_envelope": True,
        "certainty": "verified_structure_for_inbound_contract",
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
            "certainty": "verified_from_source_for_inbound_client_frame",
        },
        "encrypted_region": {
            "offset_start": encrypted_start,
            "offset_end": encrypted_end,
            "length": encrypted_end - encrypted_start,
            "block_size": 8,
            "raw_hex": raw[encrypted_start:encrypted_end].hex().upper(),
            "certainty": "verified_from_source_for_inbound_client_frame",
        },
        "post_decrypt_hash_contract": {
            "hash_input_offset_start": SEARCH_HEADER_SIZE,
            "hash_input_offset_end": hash_offset,
            "hash_input_length": hash_offset - SEARCH_HEADER_SIZE,
            "expected_md5_offset": hash_offset,
            "expected_md5_length": SEARCH_HASH_SIZE,
            "expected_md5_raw_hex_pre_decrypt": raw[hash_offset:seed_offset].hex().upper(),
            "algorithm": "MD5",
            "validation_available_only_after_decryption": True,
            "certainty": "verified_from_source_for_inbound_client_frame",
        },
        "packet_type_contract": {
            "offset": 0x0B,
            "readable_only_after_decryption_and_hash_validation": True,
            "value": None,
            "name": None,
            "certainty": "not_decoded",
        },
        "server_key_continuation_contract": {
            "post_decrypt_source_offset": length - 0x18,
            "length": 4,
            "meaning": "copied to SearchHandler key[20:24] after inbound decrypt for subsequent server-side encryption state",
            "value": None,
            "certainty": "not_decoded",
        },
        "outbound_warning": {
            "independently_derivable_from_outbound_frame": False,
            "reason": "server encryption hashes 24-byte rolling key state; key[20:24] comes from a previously decrypted inbound frame",
        },
    })
    return result


def _validate_decrypted_structure(decrypted: bytes) -> dict:
    """Validate the clear framing and post-transform MD5 without assigning direction semantics."""
    result = {
        "validated": False,
        "certainty": "unknown_opaque",
        "diagnostics": [],
    }
    if len(decrypted) < SEARCH_MIN_FRAME_SIZE:
        result["diagnostics"].append({
            "kind": "truncated_decrypted_search_candidate",
            "minimum_length": SEARCH_MIN_FRAME_SIZE,
            "observed_length": len(decrypted),
        })
        return result

    declared = int.from_bytes(decrypted[0:2], "little")
    if declared != len(decrypted):
        result["diagnostics"].append({
            "kind": "search_declared_length_mismatch",
            "declared_length": declared,
            "observed_length": len(decrypted),
        })
        return result
    if decrypted[4:8] != SEARCH_MARKER:
        result["diagnostics"].append({
            "kind": "search_marker_mismatch",
            "observed_hex": decrypted[4:8].hex().upper(),
            "expected_ascii": "IXFF",
        })
        return result

    hash_offset = len(decrypted) - SEARCH_TRAILER_SIZE
    seed_offset = len(decrypted) - SEARCH_SEED_SIZE
    computed = hashlib.md5(decrypted[SEARCH_HEADER_SIZE:hash_offset]).digest()
    observed = decrypted[hash_offset:seed_offset]
    result["framing_validation"] = {
        "declared_length": declared,
        "observed_length": len(decrypted),
        "marker": "IXFF",
        "valid": True,
        "certainty": "verified",
    }
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
    return result


def validate_decrypted_frame(decrypted: bytes) -> dict:
    """Validate a decrypted inbound request, then expose its request type."""
    result = {
        **_validate_decrypted_structure(decrypted),
        "direction_scope": "client_to_search_server_only",
        "packet_type": None,
        "packet_type_name": None,
    }
    if not result["validated"]:
        return result

    packet_type = decrypted[0x0B]
    packet_type_name = SEARCH_REQUEST_TYPES.get(packet_type)
    result["packet_type"] = packet_type
    result["packet_type_name"] = packet_type_name or "UNKNOWN"
    result["packet_type_evidence"] = {
        "offset": 0x0B,
        "value": packet_type,
        "name": packet_type_name or "UNKNOWN",
        "known_request_type": packet_type_name is not None,
        "certainty": "verified_after_framing_and_post_decrypt_md5",
        "provenance": "LandSandBoat SearchHandler::TCPREQUESTTYPE read by read_func after decrypt()+validatePacket()",
    }
    return result


def decrypt_inbound_frame(raw: bytes) -> dict:
    """Decrypt one independently proven client->search-server frame and validate it fail-closed."""
    envelope = inspect_frame(raw)
    result = {
        "decryption_performed": False,
        "validated": False,
        "certainty": "unknown_opaque",
        "direction_scope": "client_to_search_server_only",
        "decoder_status": "rejected_before_decryption",
        "envelope": envelope,
        "validation": None,
        "decrypted_hex": None,
        "diagnostics": list(envelope.get("diagnostics") or []),
    }
    if not envelope.get("valid_envelope"):
        return result

    start = int(envelope["encrypted_region"]["offset_start"])
    end = int(envelope["encrypted_region"]["offset_end"])
    key = bytes.fromhex(envelope["key_derivation"]["derived_blowfish_key_hex"])
    decrypted = bytearray(raw)
    decrypted[start:end] = ffxi_blowfish.decrypt_blocks(raw[start:end], key)
    validation = validate_decrypted_frame(bytes(decrypted))

    result.update({
        "decryption_performed": True,
        "validated": bool(validation.get("validated")),
        "certainty": "verified" if validation.get("validated") else "decrypted_candidate_unverified",
        "decoder_status": "decrypted_and_validated" if validation.get("validated") else "decrypted_candidate_rejected",
        "validation": validation,
        "decrypted_hex": bytes(decrypted).hex().upper(),
        "diagnostics": list(validation.get("diagnostics") or []),
    })
    if validation.get("validated"):
        result["packet_type"] = validation.get("packet_type")
        result["packet_type_name"] = validation.get("packet_type_name")
    return result


def derive_outbound_state(inbound_wire: bytes, inbound_decrypted: bytes) -> dict:
    """Derive the exact 24-byte SearchHandler state produced by one validated inbound request.

    This does not search for or guess a predecessor. The caller must provide the wire frame and its
    corresponding validated decrypted bytes from the same observation.
    """
    validation = validate_decrypted_frame(inbound_decrypted)
    result = {
        "validated": False,
        "certainty": "unknown_opaque",
        "diagnostics": list(validation.get("diagnostics") or []),
        "source_inbound_validation": validation,
    }
    if len(inbound_wire) != len(inbound_decrypted):
        result["diagnostics"].append({
            "kind": "search_state_source_length_mismatch",
            "wire_length": len(inbound_wire),
            "decrypted_length": len(inbound_decrypted),
        })
        return result
    if not validation.get("validated"):
        return result

    seed = inbound_wire[-SEARCH_SEED_SIZE:]
    continuation_offset = len(inbound_decrypted) - 0x18
    continuation = inbound_decrypted[continuation_offset:continuation_offset + 4]
    state = _SEARCH_BASE_KEY + seed + continuation
    result.update({
        "validated": True,
        "certainty": "verified",
        "state_hex": state.hex().upper(),
        "state_length": len(state),
        "base_prefix_hex": _SEARCH_BASE_KEY.hex().upper(),
        "inbound_seed_hex": seed.hex().upper(),
        "continuation_hex": continuation.hex().upper(),
        "continuation_offset": continuation_offset,
        "provenance": "SearchHandler decrypt: key[16:20]=wire[-4:], key[20:24]=decrypted[length-0x18:length-0x14]",
    })
    return result


def decrypt_outbound_frame(raw: bytes, outbound_state: dict | bytes) -> dict:
    """Decrypt one server->client frame using explicit state from a validated inbound predecessor.

    The helper validates the clear framing, requires the outbound frame's final 4 bytes to equal the
    state's key[16:20] value written by SearchHandler::encrypt(), decrypts the aligned region using
    MD5 over all 24 state bytes, then validates the post-decrypt MD5. Response payload semantics are
    intentionally left opaque.
    """
    if isinstance(outbound_state, dict):
        state_hex = outbound_state.get("state_hex") if outbound_state.get("validated") else None
        state = bytes.fromhex(state_hex) if state_hex else b""
    else:
        state = bytes(outbound_state)

    result = {
        "decryption_performed": False,
        "validated": False,
        "certainty": "unknown_opaque",
        "direction_scope": "search_server_to_client_with_explicit_predecessor_state",
        "decoder_status": "rejected_before_decryption",
        "diagnostics": [],
        "decrypted_hex": None,
        "payload_semantics": "unknown_opaque",
    }
    if len(state) != 24:
        result["diagnostics"].append({
            "kind": "invalid_search_outbound_state",
            "expected_length": 24,
            "observed_length": len(state),
        })
        return result
    if len(raw) < SEARCH_MIN_FRAME_SIZE:
        result["diagnostics"].append({
            "kind": "truncated_search_outbound_candidate",
            "minimum_length": SEARCH_MIN_FRAME_SIZE,
            "observed_length": len(raw),
        })
        return result
    if int.from_bytes(raw[0:2], "little") != len(raw) or raw[4:8] != SEARCH_MARKER:
        result["diagnostics"].append({"kind": "search_outbound_clear_framing_mismatch"})
        return result

    expected_seed = state[16:20]
    observed_seed = raw[-SEARCH_SEED_SIZE:]
    if observed_seed != expected_seed:
        result["diagnostics"].append({
            "kind": "search_outbound_state_seed_mismatch",
            "expected_hex": expected_seed.hex().upper(),
            "observed_hex": observed_seed.hex().upper(),
        })
        return result

    start, end = _encrypted_region(len(raw))
    key = hashlib.md5(state).digest()
    decrypted = bytearray(raw)
    decrypted[start:end] = ffxi_blowfish.decrypt_blocks(raw[start:end], key)
    validation = _validate_decrypted_structure(bytes(decrypted))
    result.update({
        "decryption_performed": True,
        "validated": bool(validation.get("validated")),
        "certainty": "verified" if validation.get("validated") else "decrypted_candidate_unverified",
        "decoder_status": "outbound_decrypted_and_validated" if validation.get("validated") else "outbound_decrypted_candidate_rejected",
        "validation": validation,
        "derived_blowfish_key_hex": key.hex().upper(),
        "decrypted_hex": bytes(decrypted).hex().upper(),
        "diagnostics": list(validation.get("diagnostics") or []),
        "payload_semantics": "unknown_opaque",
    })
    return result
