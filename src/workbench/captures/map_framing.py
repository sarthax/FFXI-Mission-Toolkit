"""Source-backed structural checks for the initial FFXI map/game UDP login datagram.

This module intentionally recognizes only the non-encrypted client 0x000A zone-login handshake that
LandSandBoat validates before creating/decrypting a map session. It does not decrypt later map
traffic and does not assign semantics to unknown fields.
"""
from __future__ import annotations

import hashlib
import struct


FFXI_HEADER_SIZE = 0x1C
LOGIN_OPCODE = 0x000A
LOGIN_PACKET_SIZE = 0x005C
CHECKSUM_SIZE = 16
LOGIN_BODY_SIZE = LOGIN_PACKET_SIZE - CHECKSUM_SIZE
MIN_DATAGRAM_SIZE = FFXI_HEADER_SIZE + LOGIN_PACKET_SIZE
LOGIN_PACKET_CHECK_OFFSET = 0x04
LOGIN_PACKET_CHECK_SUM_START = 0x08


def inspect_login_datagram(payload: bytes) -> dict:
    """Return evidence for a source-backed non-encrypted map 0x000A datagram.

    Verified structural facts:
    - outer common header is 0x1C bytes;
    - client 0x000A declares size 0x5C, including the 16-byte checksum trailer;
    - the final 16 bytes are MD5 over the 0x4C-byte pre-trailer inner packet body;
    - the first inner uint16 carries opcode in the low 9 bits and size in 4-byte words;
    - LoginPacketCheck is the byte-sum of the packet body beginning at inner offset 0x08.

    No character/account/ticket/platform fields are decoded here.
    """
    result = {
        "recognized": False,
        "protocol_family": "ffxi_map",
        "message_type": "client_zone_login_0x000A",
        "certainty": "unknown_opaque",
        "validation_basis": [],
        "diagnostics": [],
        "raw_length": len(payload),
        "raw_payload_hex": payload.hex().upper(),
        "field_evidence": {},
    }

    if len(payload) < MIN_DATAGRAM_SIZE:
        result["diagnostics"].append({
            "kind": "truncated_map_login_candidate",
            "minimum_length": MIN_DATAGRAM_SIZE,
            "observed_length": len(payload),
        })
        return result

    inner_start = FFXI_HEADER_SIZE
    inner_header = struct.unpack_from("<H", payload, inner_start)[0]
    opcode = inner_header & 0x01FF
    size_words = (inner_header >> 9) & 0x7F
    declared_size = size_words * 4

    result["field_evidence"]["opcode"] = {
        "offset": inner_start,
        "bit_mask": "0x01FF",
        "value": opcode,
        "certainty": "verified_observation",
    }
    result["field_evidence"]["declared_inner_size"] = {
        "offset": inner_start,
        "bit_range": "9..15",
        "word_size": 4,
        "value": declared_size,
        "certainty": "verified_observation",
    }

    if opcode != LOGIN_OPCODE:
        result["diagnostics"].append({
            "kind": "map_non_login_datagram",
            "observed_opcode": opcode,
        })
        return result
    result["validation_basis"].append("LandSandBoat recv_parse requires inner opcode 0x000A before session creation")

    if declared_size != LOGIN_PACKET_SIZE:
        result["diagnostics"].append({
            "kind": "map_login_declared_size_mismatch",
            "observed_size": declared_size,
            "expected_size": LOGIN_PACKET_SIZE,
        })
        return result
    result["validation_basis"].append("XiPackets GP_CLI_COMMAND_LOGIN declared size 0x005C")

    checksum_start = inner_start + LOGIN_BODY_SIZE
    checksum_end = checksum_start + CHECKSUM_SIZE
    inner_body = payload[inner_start:checksum_start]
    observed_md5 = payload[checksum_start:checksum_end]
    computed_md5 = hashlib.md5(inner_body).digest()
    md5_valid = observed_md5 == computed_md5
    result["field_evidence"]["outer_md5"] = {
        "offset": checksum_start,
        "length": CHECKSUM_SIZE,
        "certainty": "verified" if md5_valid else "observed",
        "valid": md5_valid,
        "raw_hex": observed_md5.hex().upper(),
    }
    if not md5_valid:
        result["diagnostics"].append({
            "kind": "map_outer_md5_mismatch",
            "checksum_offset": checksum_start,
        })
        return result
    result["validation_basis"].append("LandSandBoat recv_parse outer MD5 validation")

    observed_check = payload[inner_start + LOGIN_PACKET_CHECK_OFFSET]
    computed_check = sum(payload[inner_start + LOGIN_PACKET_CHECK_SUM_START:checksum_start]) & 0xFF
    packet_check_valid = observed_check == computed_check
    result["field_evidence"]["LoginPacketCheck"] = {
        "offset": inner_start + LOGIN_PACKET_CHECK_OFFSET,
        "length": 1,
        "observed": observed_check,
        "computed": computed_check,
        "valid": packet_check_valid,
        "certainty": "verified" if packet_check_valid else "observed",
    }
    if not packet_check_valid:
        result["diagnostics"].append({
            "kind": "map_login_packet_check_mismatch",
            "observed": observed_check,
            "computed": computed_check,
        })
        return result
    result["validation_basis"].append("LandSandBoat/XiPackets LoginPacketCheck byte-sum validation")

    result["recognized"] = True
    result["certainty"] = "verified"
    result["decoder_status"] = "verified_handshake_structure_payload_fields_opaque"
    result["opaque_inner_hex"] = inner_body.hex().upper()
    if len(payload) > checksum_end:
        result["diagnostics"].append({
            "kind": "opaque_trailing_bytes",
            "offset": checksum_end,
            "length": len(payload) - checksum_end,
            "raw_slice_hex": payload[checksum_end:].hex().upper(),
        })
    return result
