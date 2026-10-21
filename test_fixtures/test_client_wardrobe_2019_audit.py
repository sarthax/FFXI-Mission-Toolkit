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
    inspect_2019_store_lifecycle, PER_STORE_CLEAR_DWORDS,
    MANAGER_SLOT_COUNT_FIELD_OFFSET, INVENTORY_CURSOR_COUNT_OFFSET,
    INVENTORY_CURSOR_POINTER_OFFSET, INVENTORY_CURSOR_MAX_SLOTS,
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
        # Include every anchor, including the later fixed-buffer initializer.
        max_end = max(
            rva - 0x1000 + len(bytes.fromhex(pattern))
            for rva, pattern in ANCHORS.values()
        )
        decoded = bytearray(max_end + 16)
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
        self.assertEqual(mapped["active_store_pointer_global_va"], "0x104CDA08")
        self.assertEqual(
            mapped["observed_runtime_store_reassignment_rvas"],
            ["0xF7116", "0xF7295", "0xF9B3C"]
        )
        self.assertFalse(mapped["store_lifetime_mapped_completely"])
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


    def test_manager_lifecycle_selected_static_boundaries(self):
        observed = inspect_2019_store_lifecycle(True)
        self.assertEqual(observed["evidence_status"], "VERIFIED_STATIC_ANCHORS")
        self.assertEqual(PER_STORE_CLEAR_DWORDS, 0xEC20)
        self.assertEqual(observed["per_store_zero_clear_bytes"], 0x3B080)
        self.assertEqual(observed["fixed_size_transfer_value_bytes"], 0x3B080)
        self.assertEqual(len(observed["fixed_size_transfer_immediate_rvas"]), 11)
        self.assertFalse(observed["fixed_size_transfer_semantics_confirmed"])
        self.assertEqual(observed["read_like_stream_callee_rva"], "0x307CFF")
        self.assertEqual(observed["write_like_stream_callee_rva"], "0x307E16")
        self.assertEqual(len(observed["read_like_fixed_transfer_immediate_rvas"]), 6)
        self.assertEqual(len(observed["write_like_fixed_transfer_immediate_rvas"]), 5)
        self.assertFalse(observed["persistent_file_format_and_schema_confirmed"])
        self.assertEqual(observed["linear_disassembly_candidate_reference_count"], 1045)
        self.assertEqual(observed["observed_direct_global_writer_instruction_count"], 15)
        self.assertFalse(observed["global_writer_sites_independently_cfg_confirmed"])
        self.assertIn("0x3FA7", observed["active_store_pointer_set_rvas"])
        self.assertIn("0xF8A55", observed["active_store_pointer_set_rvas"])
        self.assertEqual(observed["manager_slot_count_field_offset"], 0x3B088)
        self.assertEqual(MANAGER_SLOT_COUNT_FIELD_OFFSET, 0x3B088)
        self.assertEqual(observed["manager_default_slot_count"], 1)
        self.assertEqual(observed["separate_manager_index_validation_rva"], "0xF6EE0")
        self.assertTrue(observed["manager_index_truncated_to_16_bits"])
        self.assertTrue(observed["manager_index_guarded_by_slot_count"])
        self.assertFalse(observed["manager_guard_proves_inventory_container_safety"])
        self.assertEqual(observed["manager_slot_selection_rvas"],
                         ["0xF710A", "0xF7009"])
        self.assertEqual(observed["manager_cleanup_call_rva"], "0xF700D")
        self.assertEqual(observed["active_store_pointer_clear_rvas"],
                         ["0xF70D6", "0xF6FE2"])
        self.assertIn("0xF73E1", observed["active_store_pointer_set_rvas"])
        self.assertIn("0xF740E", observed["active_store_pointer_set_rvas"])
        self.assertFalse(observed["complete_pointer_writer_inventory"])
        self.assertFalse(observed["store_object_allocation_size_proved_for_all_instances"])
        self.assertFalse(observed["store_object_lifetime_proved"])
        self.assertEqual(observed["safety_decision"], "NO_GO_MOVE_OR_EXTEND_EXISTING_ARRAY")

    def test_inventory_cursor_fields_preserved_after_legacy_array(self):
        observed = inspect_2019_store_lifecycle(True)
        cursor = observed["post_inventory_cursor"]
        self.assertEqual(cursor["count_offset"], INVENTORY_CURSOR_COUNT_OFFSET)
        self.assertEqual(cursor["pointer_offset"], INVENTORY_CURSOR_POINTER_OFFSET)
        self.assertEqual(cursor["count_offset"], ORIGINAL_ITEM_ARRAY_END)
        self.assertEqual(cursor["pointer_offset"], ORIGINAL_ITEM_ARRAY_END + 4)
        self.assertEqual(cursor["maximum_slots"], INVENTORY_CURSOR_MAX_SLOTS)
        self.assertEqual(cursor["maximum_slots"], SLOTS_PER_CONTAINER)
        self.assertEqual(cursor["cursor_pointer_clear_rva"], "0xE88CC")
        self.assertTrue(observed["cursor_uses_existing_inventory_records"])
        unknown = inspect_2019_store_lifecycle(False)
        self.assertIsNone(unknown["cursor_uses_existing_inventory_records"])
        self.assertEqual(unknown["evidence_status"], "UNVERIFIED_STATIC_ANCHORS")
        self.assertEqual(unknown["safety_decision"], "NO_GO_MOVE_OR_EXTEND_EXISTING_ARRAY")
        self.assertIsNone(unknown["manager_index_guarded_by_slot_count"])

    def test_static_io_size_candidates_have_exact_count_and_no_false_semantics(self):
        report = inspect_2019_store_lifecycle(True)
        sizes = report["fixed_size_transfer_immediate_rvas"]
        self.assertEqual(len(sizes), len(set(sizes)))
        self.assertEqual(
            sorted(sizes),
            sorted(report["read_like_fixed_transfer_immediate_rvas"] +
                   report["write_like_fixed_transfer_immediate_rvas"])
        )
        self.assertFalse(report["persistent_file_format_and_schema_confirmed"])
        self.assertEqual(sizes[0], "0x3FA1")
        self.assertEqual(sizes[-1], "0x4818")
        self.assertEqual(report["fixed_size_transfer_value_bytes"],
                         report["per_store_zero_clear_bytes"])
        self.assertFalse(report["fixed_size_transfer_semantics_confirmed"])
        self.assertFalse(report["complete_pointer_writer_inventory"])


if __name__ == "__main__":
    unittest.main()
