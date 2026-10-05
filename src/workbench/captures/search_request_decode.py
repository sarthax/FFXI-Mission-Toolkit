"""Decode a small source-backed subset of already-decrypted FFXI search requests.

All entry points require the same post-decrypt MD5 validation used by LandSandBoat before any
request-specific field is exposed. This module intentionally excludes auction-house request bodies
and the larger bit-packed SEARCH/SEARCH_ALL filter grammar.
"""
from __future__ import annotations

import struct

from workbench.captures import search_crypto_envelope


SEARCH_PACKET_TRAILER_SIZE = 0x14


def _u16(data: bytes, offset: int) -> int:
    return struct.unpack_from("<H", data, offset)[0]


def _u32(data: bytes, offset: int) -> int:
    return struct.unpack_from("<I", data, offset)[0]


def decode_validated_request(decrypted: bytes) -> dict:
    """Validate then decode only request fields directly consumed by LSB handlers."""
    validation = search_crypto_envelope.validate_decrypted_frame(decrypted)
    result = {
        "validated": validation["validated"],
        "packet_type": validation.get("packet_type"),
        "packet_type_name": validation.get("packet_type_name"),
        "validation": validation,
        "fields": {},
        "field_evidence": {},
        "decoder_status": "rejected_before_request_decode",
        "diagnostics": list(validation.get("diagnostics") or []),
        "raw_hex": decrypted.hex().upper(),
    }
    if not validation["validated"]:
        return result

    packet_type = validation["packet_type"]
    data_end = len(decrypted) - SEARCH_PACKET_TRAILER_SIZE
    result["decoder_status"] = "validated_request_type_payload_not_decoded"

    if packet_type == 0x01:  # ID_LIST
        count_offset = 0x10
        ids_offset = 0x12
        if data_end < ids_offset:
            result["diagnostics"].append({
                "kind": "truncated_id_list_request",
                "required_data_end": ids_offset,
                "observed_data_end": data_end,
            })
            return result
        requested_count = _u16(decrypted, count_offset)
        available_count = max(0, (data_end - ids_offset) // 4)
        decoded_count = min(requested_count, 20, available_count)
        character_ids = [_u32(decrypted, ids_offset + 4 * i) for i in range(decoded_count)]
        result["fields"] = {
            "requested_count": requested_count,
            "decoded_count": decoded_count,
            "character_ids": character_ids,
        }
        result["field_evidence"] = {
            "requested_count": {"offset": count_offset, "length": 2, "certainty": "verified_from_source"},
            "character_ids": {
                "offset": ids_offset,
                "element_length": 4,
                "decoded_count": decoded_count,
                "source_cap": 20,
                "certainty": "verified_from_source",
            },
        }
        result["decoder_status"] = "validated_basic_request_fields_decoded"
        return result

    if packet_type == 0x02:  # GROUP_LIST
        required_end = 0x20
        if data_end < required_end:
            result["diagnostics"].append({
                "kind": "truncated_group_list_request",
                "required_data_end": required_end,
                "observed_data_end": data_end,
            })
            return result
        result["fields"] = {
            "party_id": _u32(decrypted, 0x10),
            "alliance_id": _u32(decrypted, 0x14),
            "linkshell_id_1": _u32(decrypted, 0x18),
            "linkshell_id_2": _u32(decrypted, 0x1C),
        }
        result["field_evidence"] = {
            "party_id": {"offset": 0x10, "length": 4, "certainty": "verified_from_source"},
            "alliance_id": {"offset": 0x14, "length": 4, "certainty": "verified_from_source"},
            "linkshell_id_1": {"offset": 0x18, "length": 4, "certainty": "verified_from_source"},
            "linkshell_id_2": {"offset": 0x1C, "length": 4, "certainty": "verified_from_source"},
        }
        result["decoder_status"] = "validated_basic_request_fields_decoded"
        return result

    if packet_type == 0x08:  # SEARCH_COMMENT
        required_end = 0x14
        if data_end < required_end:
            result["diagnostics"].append({
                "kind": "truncated_search_comment_request",
                "required_data_end": required_end,
                "observed_data_end": data_end,
            })
            return result
        result["fields"] = {"player_id": _u32(decrypted, 0x10)}
        result["field_evidence"] = {
            "player_id": {"offset": 0x10, "length": 4, "certainty": "verified_from_source"},
        }
        result["decoder_status"] = "validated_basic_request_fields_decoded"
        return result

    # Known but deliberately unsupported request bodies stay validated and opaque. This includes
    # SEARCH/SEARCH_ALL bit-packed filters and all auction-house request types in this slice.
    result["diagnostics"].append({
        "kind": "validated_search_request_body_not_supported",
        "packet_type": packet_type,
        "packet_type_name": validation.get("packet_type_name"),
    })
    return result
