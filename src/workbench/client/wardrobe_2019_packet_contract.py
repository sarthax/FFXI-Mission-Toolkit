"""Synthetic packet-shape gates for exact Dec 2019 FFXiMain.dll research.

This module is deliberately NOT a production packet parser, sender, or client
hook. Its data layout is grounded in the exact source-hash 2019 decoded
ITEM_MAX handler and the 52-byte legacy packet emitted by the separately
audited Valhalla server. It rejects extended/unknown formats rather than
guessing client capabilities.
"""
from __future__ import annotations

import struct

from workbench.client.wardrobe_2019_audit import (
    EXPECTED_SHA256,
    inspect_2019_item_packet_location,
)

LEGACY_ITEM_MAX_PACKET_ID = 0x1C
LEGACY_ITEM_MAX_WIRE_LENGTH = 0x34  # Valhalla 13-container packet (not a client-enforced length)
LEGACY_ITEM_MAX_MIN_READ_SPAN = 0x2E  # Last 2019 u16 access ends at offset 0x2D
LEGACY_CAPACITY_COUNT = 13
LEGACY_U8_OFFSET = 0x04
LEGACY_U16_OFFSET = 0x14
LEGACY_RESERVED_GAP = (0x11, 0x14)
LEGACY_ITEM_PACKET_IDS = (0x1E, 0x1F, 0x20)


def _exact_legacy_build(sha256: str) -> bool:
    return type(sha256) is str and sha256 == EXPECTED_SHA256


def observe_2019_item_max_frame(frame: bytes, *, source_sha256: str,
                                declared_packet_id: int = 0x1C) -> dict:
    """Decode only known legacy capacity offsets in a *synthetic/offline* frame.

    The 52-byte condition describes a checked Valhalla packet fixture, NOT an
    assertion that the retail client checks a length or supports no other
    frame length. Packet ID is caller-declared, not authenticated by a header
    decoder. Returned numbers are input observations, not permission to act.
    """
    if not _exact_legacy_build(source_sha256):
        return {"status": "UNKNOWN_OR_DIFFERENT_CLIENT_BUILD", "decodable": False}
    if type(declared_packet_id) is not int or declared_packet_id != LEGACY_ITEM_MAX_PACKET_ID:
        return {"status": "WRONG_DECLARED_PACKET_ID", "decodable": False}
    if not isinstance(frame, bytes):
        return {"status": "INVALID_FRAME_TYPE", "decodable": False}
    if len(frame) != LEGACY_ITEM_MAX_WIRE_LENGTH:
        return {
            "status": "UNVERIFIED_FRAME_LENGTH",
            "decodable": False,
            "provided_length": len(frame),
            "required_synthetic_legacy_frame_length": LEGACY_ITEM_MAX_WIRE_LENGTH,
        }
    byte_values = list(frame[
        LEGACY_U8_OFFSET:LEGACY_U8_OFFSET + LEGACY_CAPACITY_COUNT
    ])
    word_values = [
        struct.unpack_from("<H", frame, LEGACY_U16_OFFSET + 2 * index)[0]
        for index in range(LEGACY_CAPACITY_COUNT)
    ]
    return {
        "status": "LEGACY_2019_CAPACITY_BYTES_OBSERVED",
        "decodable": True,
        "frame_length": len(frame),
        "capacity_container_ids": list(range(LEGACY_CAPACITY_COUNT)),
        "capacity_u8_values": byte_values,
        "capacity_u16_values": word_values,
        "reserved_bytes_not_interpreted": list(range(*LEGACY_RESERVED_GAP)),
        "extended_container_ids_exposed": [],
        "modern_packet_0x1c_compatible": None,
        "client_execution_or_server_compatibility_verified": False,
        "caution": (
            "Offline inspected values only. Declared packet identity is not "
            "validated against the wire header. Never send extended formats "
            "to an unmodified 2019 client."
        ),
    }


def inspect_2019_legacy_item_frame(frame: bytes, *, source_sha256: str,
                                   declared_packet_id: int) -> dict:
    """Fail-closed offline legacy record-route candidate, *never* a dispatch.

    The known 2019 0x1E/0x1F/0x20 entry instruction paths have differing
    offsets; this checks only the minimum bytes used for their container/slot
    indexes. Full wire framing, dispatch and execution are unverified.
    """
    if not _exact_legacy_build(source_sha256):
        return {"status": "UNKNOWN_OR_DIFFERENT_CLIENT_BUILD",
                "candidate_route_allowed": False}
    if type(declared_packet_id) is not int or declared_packet_id not in LEGACY_ITEM_PACKET_IDS:
        return {"status": "UNSUPPORTED_DECLARED_PACKET_ID",
                "candidate_route_allowed": False}
    result = inspect_2019_item_packet_location(declared_packet_id, frame)
    allowed = result["status"] == "LEGACY_BOUNDS_OK"
    return {
        "status": (
            "LEGACY_BOUNDS_CANDIDATE_ONLY" if allowed
            else "DENIED_OR_INSUFFICIENT_LEGACY_PACKET"
        ),
        "candidate_route_allowed": allowed,
        "packet_id": declared_packet_id,
        "location_status": result["status"],
        "container_id": result.get("container_id"),
        "slot_id": result.get("slot_id"),
        "record_offset": result["safe_record_offset"] if allowed else None,
        "extension_routing_allowed": False,
        "full_packet_framing_and_runtime_execution_verified": False,
    }


def describe_2019_vs_modern_capacity_contract() -> dict:
    """Document known layouts without offering a modern-format decoder."""
    return {
        "status": "RESEARCH_ONLY_NO_PACKET_WRITER",
        "legacy_2019": {
            "container_count": 13,
            "u8_source_offset": 0x04,
            "u16_source_offset": 0x14,
            "min_read_span": LEGACY_ITEM_MAX_MIN_READ_SPAN,
            "valhalla_legacy_fixture_length": LEGACY_ITEM_MAX_WIRE_LENGTH,
            "exact_client_sha256": EXPECTED_SHA256,
        },
        "newer_2026_prior_research": {
            "container_count": 18,
            "u8_source_offset": 0x04,
            "u16_source_offset": 0x24,
            "min_read_span": 0x48,
            "exact_2026_wire_capture_available": False,
            "format_valid_for_2019": False,
        },
        "per_session_build_capability_signal_verified": False,
        "modern_packet_writer_or_parser_implemented": False,
        "safety_decision": "NO_GO_MODERN_FORMAT_ON_UNMODIFIED_2019",
    }
