#!/usr/bin/env python3
"""Synthetic-only Dec 2019 Wardrobe command/dispatcher evidence regressions."""
import struct
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from workbench.client.pol1_unpack import Pol1Error
from workbench.client.wardrobe_2019_command_ui import (
    COMMAND_NAME_RVA, COMMAND_HANDLER_TABLE_RVA,
    COMMAND_HELPER_RVA, COMMAND_NAME_RECORD_BYTES,
    HANDLER_RECORD_BYTES, IMAGE_BASE, MODE_FIRST, MODE_LAST,
    MODE_CASE_TARGETS, MODE_CASE_UI_POINTER_GLOBALS,
    MODE_FORWARD_BYTES, MODE_GETTER_BYTES, MODE_SELECTOR_BYTES,
    UI_JUMP_TABLE_RVA, WARDROBE_COMMANDS,
    inspect_2019_command_ui_dispatch,
)

DATA_RVA = 0x344000
CODE_RVA = 0x1000


def synthetic_ui_tables():
    """Create fabricated tables/instructions with the known 2019 anchor *shape*."""
    data = bytearray(0xA000)
    code = bytearray(0x1D6000 - CODE_RVA)

    def write_code(rva, value):
        at = rva - CODE_RVA
        code[at:at + len(value)] = value

    for idx, (id_, name, handler, global_va) in enumerate(WARDROBE_COMMANDS):
        name_off = COMMAND_NAME_RVA + idx * COMMAND_NAME_RECORD_BYTES - DATA_RVA
        data[name_off:name_off + 16] = name.encode("ascii").ljust(16, bytes(1))
        struct.pack_into("<HH", data, name_off + 20, id_, 0x51)
        record_off = COMMAND_HANDLER_TABLE_RVA + idx * HANDLER_RECORD_BYTES - DATA_RVA
        struct.pack_into("<III", data, record_off, id_, IMAGE_BASE + handler, 0)
        insn = (bytes([0xA1]) + struct.pack("<I", global_va)
                + bytes([0x6A, 0, 0x50, 0xE8])
                + struct.pack("<i", COMMAND_HELPER_RVA - (handler + 13)))
        write_code(handler, insn)

    write_code(0x1D16F0, MODE_FORWARD_BYTES)
    write_code(0x1D4E85, MODE_GETTER_BYTES)
    write_code(0x1D4E8A, MODE_SELECTOR_BYTES)
    for target, pointer in zip(MODE_CASE_TARGETS, MODE_CASE_UI_POINTER_GLOBALS):
        # The 2019 branches start with either mov eax,[abs] or
        # mov ecx/edx,[abs] and then set a selected UI pointer.
        if target in (0x1D4E99, 0x1D4EB6, 0x1D4ED3, 0x1D4EF0):
            insn = bytes([0xA1]) + struct.pack("<I", pointer)
        elif target in (0x1D4EAB, 0x1D4EC8, 0x1D4EE5):
            insn = bytes.fromhex("8b15") + struct.pack("<I", pointer)
        else:
            insn = bytes.fromhex("8b0d") + struct.pack("<I", pointer)
        write_code(target, insn)
    for idx, case in enumerate(MODE_CASE_TARGETS):
        struct.pack_into("<I", code,
                         UI_JUMP_TABLE_RVA - CODE_RVA + idx * 4,
                         IMAGE_BASE + case)
    return bytes(data), bytes(code)


class Wardrobe2019CommandUITests(unittest.TestCase):
    def test_legacy_commands_resolve_to_four_distinct_handler_entries(self):
        data, code = synthetic_ui_tables()
        report = inspect_2019_command_ui_dispatch(data, DATA_RVA, code)
        self.assertEqual(report["status"], "EXACT_STATIC_ANCHORS_MATCH")
        self.assertEqual([x["command_id"] for x in report["commands"]],
                         [111, 112, 113, 114])
        self.assertEqual([x["handler_rva"] for x in report["commands"]],
                         ["0x7CE80", "0x7CEA0", "0x7CEC0", "0x7CEE0"])
        self.assertTrue(all(
            x["name_and_id_match"] and x["handler_table_matches"] and
            x["loads_object_and_calls_shared_helper"] for x in report["commands"]
        ))
        self.assertEqual(report["shared_command_helper_rva"], "0x1D1680")
        self.assertFalse(report["command_to_runtime_mode_id_mapping_proved"])

    def test_original_mode_jump_table_does_not_cover_modes_13_to_16(self):
        data, code = synthetic_ui_tables()
        report = inspect_2019_command_ui_dispatch(data, DATA_RVA, code)
        self.assertEqual(report["switch_first_mode"], 2)
        self.assertEqual(report["switch_last_mode"], 12)
        self.assertEqual(report["switch_entry_count"], 11)
        self.assertTrue(report["selector_uses_mode_minus_two"])
        self.assertTrue(report["jump_table_matches"])
        self.assertTrue(report["helper_forward_getter_and_selector_match"])
        self.assertEqual([m["mode"] for m in report["ui_mode_cases"]],
                         list(range(MODE_FIRST, MODE_LAST + 1)))
        self.assertTrue(all(m["case_global_matches"] for m in report["ui_mode_cases"]))
        self.assertTrue(report["proposed_modes_13_16_use_default_in_original"])
        self.assertFalse(report["new_wardrobe_commands_or_mode_cases_present"])
        self.assertFalse(report["complete_menu_builder_and_ui_state_recovered"])

    def test_mutated_handler_table_and_name_fail_closed(self):
        data, code = synthetic_ui_tables()
        damaged = bytearray(data)
        damaged[COMMAND_HANDLER_TABLE_RVA + 12 - DATA_RVA + 4] ^= 1
        report = inspect_2019_command_ui_dispatch(bytes(damaged), DATA_RVA, code)
        self.assertEqual(report["status"], "INCOMPLETE_STATIC_EVIDENCE")
        self.assertFalse(report["commands"][1]["handler_table_matches"])
        self.assertIsNone(report["new_wardrobe_commands_or_mode_cases_present"])
        damaged = bytearray(data)
        damaged[COMMAND_NAME_RVA + 48 - DATA_RVA] ^= 1
        report = inspect_2019_command_ui_dispatch(bytes(damaged), DATA_RVA, code)
        self.assertFalse(report["commands"][2]["name_and_id_match"])
        self.assertEqual(report["status"], "INCOMPLETE_STATIC_EVIDENCE")

    def test_modified_forwarder_helper_and_mode_getter_fail_closed(self):
        data, code = synthetic_ui_tables()
        for site in (0x7CE80 + 9, 0x1D16F0 + 11, 0x1D4E85 + 2,
                     0x1D4E8A + 6):
            with self.subTest(rva=site):
                damaged = bytearray(code)
                damaged[site - CODE_RVA] ^= 1
                report = inspect_2019_command_ui_dispatch(
                    data, DATA_RVA, bytes(damaged))
                self.assertEqual(report["status"], "INCOMPLETE_STATIC_EVIDENCE")

    def test_mutated_case_global_and_jumptable_fail_closed(self):
        data, code = synthetic_ui_tables()
        for site in (MODE_CASE_TARGETS[3] + 2, UI_JUMP_TABLE_RVA + 12):
            damaged = bytearray(code)
            damaged[site - CODE_RVA] ^= 1
            report = inspect_2019_command_ui_dispatch(
                data, DATA_RVA, bytes(damaged))
            self.assertFalse(report["helper_forward_getter_and_selector_match"])
            self.assertEqual(report["status"], "INCOMPLETE_STATIC_EVIDENCE")
            self.assertIsNone(report["proposed_modes_13_16_use_default_in_original"])

    def test_bad_types_bounds_and_truncation_do_not_claim_support(self):
        data, code = synthetic_ui_tables()
        for bad in (None, bytearray(data), "data"):
            with self.assertRaises(Pol1Error):
                inspect_2019_command_ui_dispatch(bad, DATA_RVA, code)
        for bad in (True, 3.0, "0x344000"):
            with self.assertRaises(Pol1Error):
                inspect_2019_command_ui_dispatch(data, bad, code)
        truncated = inspect_2019_command_ui_dispatch(
            data[:3], DATA_RVA, code[:0x1200])
        self.assertEqual(truncated["status"], "INCOMPLETE_STATIC_EVIDENCE")
        self.assertIsNone(truncated["new_wardrobe_commands_or_mode_cases_present"])
        with self.assertRaises(Pol1Error):
            inspect_2019_command_ui_dispatch(data, DATA_RVA,
                                              bytes(8 * 1024 * 1024 + 1))


if __name__ == "__main__":
    unittest.main()
