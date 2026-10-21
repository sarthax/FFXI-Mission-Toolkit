#!/usr/bin/env python3
"""Purely synthetic 2019/2026 client capacity and legacy item routing tests."""
import struct
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from workbench.client.wardrobe_2019_audit import EXPECTED_SHA256
from workbench.client.wardrobe_2019_packet_contract import (
    LEGACY_ITEM_MAX_WIRE_LENGTH,
    LEGACY_ITEM_MAX_MIN_READ_SPAN,
    observe_2019_item_max_frame,
    inspect_2019_legacy_item_frame,
    describe_2019_vs_modern_capacity_contract,
)


def synthetic_legacy_frame():
    data = bytearray(LEGACY_ITEM_MAX_WIRE_LENGTH)
    for i in range(13):
        data[0x04 + i] = i + 20
        struct.pack_into("<H", data, 0x14 + 2 * i, 500 + i)
    data[0x11:0x14] = b"\xaa\xbb\xcc"
    return bytes(data)


class Wardrobe2019PacketContractTests(unittest.TestCase):
    def test_exact_2019_layout_13_u8_and_13_u16(self):
        result = observe_2019_item_max_frame(
            synthetic_legacy_frame(), source_sha256=EXPECTED_SHA256)
        self.assertEqual(result["status"], "LEGACY_2019_CAPACITY_BYTES_OBSERVED")
        self.assertTrue(result["decodable"])
        self.assertEqual(result["frame_length"], 0x34)
        self.assertEqual(result["capacity_container_ids"], list(range(13)))
        self.assertEqual(result["capacity_u8_values"], list(range(20, 33)))
        self.assertEqual(result["capacity_u16_values"], list(range(500, 513)))
        self.assertEqual(result["reserved_bytes_not_interpreted"],
                         [0x11, 0x12, 0x13])
        self.assertEqual(result["extended_container_ids_exposed"], [])
        self.assertIsNone(result["modern_packet_0x1c_compatible"])
        self.assertFalse(result["client_execution_or_server_compatibility_verified"])

    def test_unverified_long_modern_and_short_frames_rejected(self):
        for frame_size in (0, 0x2D, LEGACY_ITEM_MAX_MIN_READ_SPAN, 0x30, 0x48, 0x4C):
            with self.subTest(frame_size=frame_size):
                result = observe_2019_item_max_frame(
                    bytes(frame_size), source_sha256=EXPECTED_SHA256)
                self.assertEqual(result["status"], "UNVERIFIED_FRAME_LENGTH")
                self.assertFalse(result["decodable"])
                self.assertNotIn("capacity_u8_values", result)
                self.assertNotIn("capacity_u16_values", result)

    def test_wrong_identity_declared_id_and_types_are_rejected(self):
        frame = synthetic_legacy_frame()
        for sha in ("", "0" * 64, EXPECTED_SHA256.upper(), None, True):
            self.assertEqual(
                observe_2019_item_max_frame(frame, source_sha256=sha)["status"],
                "UNKNOWN_OR_DIFFERENT_CLIENT_BUILD")
        for packet_id in (0x1D, 0x1E, 0x20, True, None, "0x1C"):
            self.assertEqual(
                observe_2019_item_max_frame(
                    frame, source_sha256=EXPECTED_SHA256,
                    declared_packet_id=packet_id)["status"],
                "WRONG_DECLARED_PACKET_ID")
        for bad in (None, bytearray(frame), memoryview(frame), "frame"):
            self.assertEqual(
                observe_2019_item_max_frame(bad, source_sha256=EXPECTED_SHA256)["status"],
                "INVALID_FRAME_TYPE")

    def test_minimum_item_location_fields_and_legacy_boundary(self):
        offsets = ((0x1E, 0x08, 0x09), (0x1F, 0x0A, 0x0B), (0x20, 0x0E, 0x0F))
        for packet_id, c_off, s_off in offsets:
            for cid, slot in ((0, 0), (12, 80)):
                frame = bytearray(max(c_off, s_off) + 1)
                frame[c_off], frame[s_off] = cid, slot
                result = inspect_2019_legacy_item_frame(
                    bytes(frame), source_sha256=EXPECTED_SHA256,
                    declared_packet_id=packet_id)
                self.assertEqual(result["status"], "LEGACY_BOUNDS_CANDIDATE_ONLY")
                self.assertTrue(result["candidate_route_allowed"])
                self.assertFalse(result["extension_routing_allowed"])
                self.assertEqual(result["container_id"], cid)
                self.assertEqual(result["slot_id"], slot)
                self.assertIsNotNone(result["record_offset"])
                self.assertFalse(result["full_packet_framing_and_runtime_execution_verified"])

    def test_wardrobe_5_8_and_invalid_slots_never_route_on_2019(self):
        offsets = ((0x1E, 0x08, 0x09), (0x1F, 0x0A, 0x0B), (0x20, 0x0E, 0x0F))
        for packet_id, c_off, s_off in offsets:
            for cid, slot in ((13, 0), (14, 80), (15, 0), (16, 80),
                              (17, 1), (255, 0), (12, 81), (12, 255)):
                frame = bytearray(max(c_off, s_off) + 1)
                frame[c_off], frame[s_off] = cid, slot
                result = inspect_2019_legacy_item_frame(
                    bytes(frame), source_sha256=EXPECTED_SHA256,
                    declared_packet_id=packet_id)
                self.assertFalse(result["candidate_route_allowed"])
                self.assertFalse(result["extension_routing_allowed"])
                self.assertIsNone(result["record_offset"])

    def test_truncation_unknown_packet_and_different_build_fail_closed(self):
        for packet_id, end in ((0x1E, 0x09), (0x1F, 0x0B), (0x20, 0x0F)):
            result = inspect_2019_legacy_item_frame(
                bytes(end), source_sha256=EXPECTED_SHA256,
                declared_packet_id=packet_id)
            self.assertEqual(result["status"], "DENIED_OR_INSUFFICIENT_LEGACY_PACKET")
            self.assertIsNone(result["record_offset"])
        for packet_id in (0x1C, 0x29, 0x3A, True, "0x1E"):
            self.assertEqual(
                inspect_2019_legacy_item_frame(
                    bytes(64), source_sha256=EXPECTED_SHA256,
                    declared_packet_id=packet_id)["status"],
                "UNSUPPORTED_DECLARED_PACKET_ID")
        self.assertEqual(
            inspect_2019_legacy_item_frame(
                bytes(64), source_sha256="different",
                declared_packet_id=0x1E)["status"],
            "UNKNOWN_OR_DIFFERENT_CLIENT_BUILD")

    def test_modern_contract_is_known_static_only_and_never_enabled(self):
        report = describe_2019_vs_modern_capacity_contract()
        old = report["legacy_2019"]
        newer = report["newer_2026_prior_research"]
        self.assertEqual(old["container_count"], 13)
        self.assertEqual(old["u8_source_offset"], 0x04)
        self.assertEqual(old["u16_source_offset"], 0x14)
        self.assertEqual(old["min_read_span"], 0x2E)
        self.assertEqual(old["valhalla_legacy_fixture_length"], 0x34)
        self.assertEqual(newer["container_count"], 18)
        self.assertEqual(newer["u16_source_offset"], 0x24)
        self.assertEqual(newer["min_read_span"], 0x48)
        self.assertFalse(newer["exact_2026_wire_capture_available"])
        self.assertFalse(newer["format_valid_for_2019"])
        self.assertFalse(report["per_session_build_capability_signal_verified"])
        self.assertFalse(report["modern_packet_writer_or_parser_implemented"])
        self.assertEqual(report["safety_decision"],
                         "NO_GO_MODERN_FORMAT_ON_UNMODIFIED_2019")


if __name__ == "__main__":
    unittest.main()
