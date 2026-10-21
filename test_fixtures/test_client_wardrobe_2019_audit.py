#!/usr/bin/env python3
"""Synthetic-only tests for exact-build 2019 Wardrobe read-only evidence gates."""
import hashlib
import io
import json
import struct
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from workbench.client.pol1_unpack import Pol1Error
from workbench.client.wardrobe_2019_audit import (
    ANCHORS, EXPECTED_COMMAND_IDS, FIRST_WARDROBE_COMMAND_RVA,
    RECORD_BYTES, audit_2019_wardrobe, inspect_command_table, inspect_decoded_sites,
    bounded_2019_record_offset, inspect_2019_item_packet_location,
    PACKET_LOCATION_FIELDS, ITEM_STORE_OFFSET, ITEM_RECORD_BYTES, SLOTS_PER_CONTAINER,
    inspect_2019_store_layout, ORIGINAL_ITEM_ARRAY_END, PROJECTED_18_CONTAINER_END,
)


def synthetic_commands():
    data_rva = FIRST_WARDROBE_COMMAND_RVA - 0x80
    data = bytearray(b"\x00" * 512)
    for i, (name, command_id) in enumerate(EXPECTED_COMMAND_IDS.items()):
        at = 0x80 + i * RECORD_BYTES
        data[at:at + 16] = name.encode("ascii").ljust(16, b"\x00")
        struct.pack_into("<H", data, at + 0x14, command_id)
    return data, data_rva


class Wardrobe2019AuditTests(unittest.TestCase):
    def test_command_table_exact_ids_and_absent_new_names_are_not_absence_proof(self):
        data, rva = synthetic_commands()
        result = inspect_command_table(bytes(data), rva)
        self.assertTrue(result["legacy_commands_verified"])
        self.assertEqual([x["observed_id"] for x in result["entries"]], [111, 112, 113, 114])
        self.assertTrue(all(not v for v in result["additional_command_records_found"].values()))
        self.assertIn("UNKNOWN", result["caution"])
        self.assertEqual(result["record_size_bytes"], 24)

    def test_command_table_displacement_and_wrong_id_fail_closed(self):
        data, rva = synthetic_commands()
        data[0x80 + RECORD_BYTES + 0x14] = 0
        self.assertFalse(inspect_command_table(bytes(data), rva)["legacy_commands_verified"])
        data, rva = synthetic_commands()
        self.assertFalse(inspect_command_table(bytes(data), rva + 24)["legacy_commands_verified"])
        self.assertFalse(inspect_command_table(b"", rva)["legacy_commands_verified"])

    def test_static_opcode_anchor_comparison_never_exposes_code(self):
        decoded = bytearray(0xF0000)
        for addr, hexbytes in ANCHORS.values():
            off = addr - 0x1000
            raw = bytes.fromhex(hexbytes)
            decoded[off:off + len(raw)] = raw
        observed = inspect_decoded_sites(bytes(decoded))
        self.assertTrue(observed["all_static_anchors_match"])
        self.assertEqual(len(observed["anchors"]), len(ANCHORS))
        self.assertTrue(all(
            set(item) == {"rva", "matches_expected_bytes"}
            for item in observed["anchors"].values()
        ))
        site = 0xE97CD - 0x1000
        decoded[site] ^= 0x01
        self.assertFalse(inspect_decoded_sites(bytes(decoded))["all_static_anchors_match"])
        self.assertFalse(inspect_decoded_sites(b"")["all_static_anchors_match"])

    def test_incorrect_source_hash_blocks_any_build_specific_claims(self):
        image = b"MZ" + bytes(2048)
        actual = hashlib.sha256(image).hexdigest()
        with patch("workbench.client.wardrobe_2019_audit.unpack_pol1") as decode:
            report = audit_2019_wardrobe(image)
            decode.assert_not_called()
        self.assertEqual(report["status"], "UNKNOWN_BUILD_FINGERPRINT")
        self.assertEqual(report["source_sha256"], actual)
        self.assertTrue(report["do_not_apply_2019_assumptions"])
        self.assertNotIn("safety_decision", report)
        for invalid in ("file", b"", bytearray(image)):
            with self.assertRaises(Pol1Error):
                audit_2019_wardrobe(invalid)

    def test_cli_is_read_only_on_unknown_build(self):
        from workbench.client.cli.wardrobe_2019_report import main
        original = b"MZ" + bytes(1024)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "synthetic.dll"
            path.write_bytes(original)
            with patch("sys.argv", ["wardrobe-2019-report", str(path)]):
                output = io.StringIO()
                with redirect_stdout(output):
                    self.assertEqual(main(), 0)
            report = json.loads(output.getvalue())
            self.assertEqual(report["status"], "UNKNOWN_BUILD_FINGERPRINT")
            self.assertEqual(path.read_bytes(), original)
            self.assertEqual([x.name for x in Path(folder).iterdir()], ["synthetic.dll"])


    def test_legacy_2019_address_guard_boundary_values(self):
        self.assertEqual(bounded_2019_record_offset(0, 0), ITEM_STORE_OFFSET)
        self.assertEqual(bounded_2019_record_offset(12, 80),
                         ITEM_STORE_OFFSET + (12 * 81 + 80) * ITEM_RECORD_BYTES)
        self.assertEqual(bounded_2019_record_offset(12, 0),
                         ITEM_STORE_OFFSET + 12 * SLOTS_PER_CONTAINER * ITEM_RECORD_BYTES)
        for cid in (-1, 13, 14, 15, 16, 255, True, 1.0):
            with self.subTest(container=cid):
                self.assertIsNone(bounded_2019_record_offset(cid, 0))
        for slot in (-1, 81, 255, True, 2.0):
            with self.subTest(slot=slot):
                self.assertIsNone(bounded_2019_record_offset(12, slot))

    def test_legacy_packet_location_guard_all_observed_packet_types(self):
        for packet_id, (cid_at, slot_at) in PACKET_LOCATION_FIELDS.items():
            with self.subTest(packet=packet_id):
                for cid, slot, accepted in (
                    (0, 0, True), (12, 80, True), (13, 0, False),
                    (14, 5, False), (15, 5, False), (16, 5, False),
                    (255, 0, False), (12, 81, False), (12, 255, False),
                ):
                    payload = bytearray(max(cid_at, slot_at) + 1)
                    payload[cid_at], payload[slot_at] = cid, slot
                    report = inspect_2019_item_packet_location(packet_id, bytes(payload))
                    self.assertEqual(report["status"] == "LEGACY_BOUNDS_OK", accepted)
                    self.assertEqual(report["safe_record_offset"] is not None, accepted)
                self.assertEqual(
                    inspect_2019_item_packet_location(packet_id, bytes(slot_at))["status"],
                    "TRUNCATED_PACKET"
                )

    def test_legacy_packet_location_guard_denies_unknown_and_invalid_input(self):
        self.assertEqual(
            inspect_2019_item_packet_location(0x29, bytes(64))["status"],
            "UNKNOWN_PACKET_NO_ADDRESS"
        )
        self.assertEqual(
            inspect_2019_item_packet_location(True, bytes(64))["status"],
            "UNKNOWN_PACKET_NO_ADDRESS"
        )
        self.assertEqual(
            inspect_2019_item_packet_location(0x1E, bytearray(64))["status"],
            "INVALID_PACKET_BUFFER"
        )

    def test_in_place_expansion_overlaps_existing_client_fields(self):
        mapped = inspect_2019_store_layout(True)
        self.assertEqual(mapped["evidence_status"], "VERIFIED_STATIC_ANCHORS")
        self.assertEqual(mapped["fixed_global_base_va"], "0x1096DB60")
        self.assertEqual(mapped["global_zero_init_bytes"], 0x3EDF4)
        self.assertEqual(mapped["active_store_offset_from_global_base"], 4)
        self.assertEqual(mapped["legacy_item_array_exclusive_end_offset"], 0x14D5C)
        self.assertEqual(mapped["observed_following_scalar_field_offset"], 0x14D5C)
        self.assertEqual(mapped["observed_following_pointer_field_offset"], 0x14D60)
        self.assertEqual(mapped["projected_18_container_array_exclusive_end_offset"], 0x192F8)
        self.assertEqual(mapped["extra_bytes_for_five_containers"], 5 * 81 * 44)
        self.assertEqual(mapped["extra_bytes_for_five_containers"], 17820)
        self.assertTrue(mapped["proposed_in_place_growth_overlaps_observed_fields"])
        self.assertEqual(mapped["safety_decision"], "NO_GO_IN_PLACE_ARRAY_GROWTH")
        self.assertEqual(ORIGINAL_ITEM_ARRAY_END, 0x14D5C)
        self.assertEqual(PROJECTED_18_CONTAINER_END, 0x192F8)

    def test_missing_static_anchor_never_claims_verified_overlap(self):
        unknown = inspect_2019_store_layout(False)
        self.assertEqual(unknown["evidence_status"], "UNVERIFIED_STATIC_ANCHORS")
        self.assertIsNone(unknown["proposed_in_place_growth_overlaps_observed_fields"])
        self.assertEqual(unknown["safety_decision"], "NO_GO_IN_PLACE_ARRAY_GROWTH")



if __name__ == "__main__":
    unittest.main()
