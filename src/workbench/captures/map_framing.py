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
MIN_DATAGRAM_SIZE = FFXI_HEADER_SIZE + LOGIN_PACKET_SIZE


def inspect_login_datagram(payload: bytes) -> dict:
    """Return evidence for a source-backed non-encrypted map 0x000A datagram.

    Verified structural facts:
    - outer common header is 0x1C bytes;
    - the final 16 bytes are MD5 over bytes from offset 0x1C up to that checksum;
    - the first inner uint16 carries opcode in the low 9 bits and size in 4-byte words;
    - XiPackets documents client 0x000A as size 0x5C.

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

    if len(payload) <= FFXI_HEADER_SIZE + CHECKSUM_SIZE:
        result["diagnostics"].append({
            "kind": "truncated_map_datagram",
            "minimum_length": FFXI_HEADER_SIZE + CHECKSUM_SIZE + 1,
            "observed_length": len(payload),
        })
        return result

    checksum_start = len(payload) - CHECKSUM_SIZE
    body = payload[FFXI_HEADER_SIZE:checksum_start]
    observed_md5 = payload[checksum_start:]
    computed_md5 = hashlib.md5(body).digest()
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

    if len(payload) < MIN_DATAGRAM_SIZE:
        result["diagnostics"].append({
            "kind": "truncated_map_login_candidate",
            "minimum_length": MIN_DATAGRAM_SIZE,
            "observed_length": len(payload),
        })
        return result

    inner_header = struct.unpack_from("<H", payload, FFXI_HEADER_SIZE)[0]
    opcode = inner_header & 0x01FF
    size_words = (inner_header >> 9) & 0x7F
    declared_size = size_words * 4

    result["field_evidence"]["opcode"] = {
        "offset": FFXI_HEADER_SIZE,
        "bit_mask": "0x01FF",
        "value": opcode,
        "certainty": "verified_observation",
    }
    result["field_evidence"]["declared_inner_size"] = {
        "offset": FFXI_HEADER_SIZE,
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
    result["validation_basis"].append("XiPackets GP_CLI_COMMAND_LOGIN size 0x005C")

    result["recognized"] = True
    result["certainty"] = "verified"
    result["decoder_status"] = "verified_handshake_structure_payload_fields_opaque"
    result["opaque_inner_hex"] = payload[FFXI_HEADER_SIZE:checksum_start].hex().upper()
    return result
