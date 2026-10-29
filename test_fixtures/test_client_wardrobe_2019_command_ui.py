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
    UI_JUMP_TABLE_RVA, WARDROBE_COMMANDS, WARDROBE_MODE_OBJECTS,
    inspect_2019_mode_object_getters,
    inspect_2019_bank2_mode9,
    BANK2_COMMAND_RVA, BANK2_HANDLER_RECORD_RVA, BANK2_POINTER_READ_RVA,
    BANK2_HELPER_CALL_RVA, BANK2_HELPER_RVA, BANK2_OBJECT_GLOBAL_VA,
    BANK2_CTOR_RVA, BANK2_VTABLE_VA, BANK2_GETTER_RVA,
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

    bank2_name = BANK2_COMMAND_RVA - DATA_RVA
    data[bank2_name:bank2_name + 16] = b"/bank2".ljust(16, bytes(1))
    struct.pack_into("<HH", data, bank2_name + 20, 115, 0x51)
    struct.pack_into(
        "<III", data, BANK2_HANDLER_RECORD_RVA - DATA_RVA,
        115, IMAGE_BASE + 0x7CF00, 0,
    )
    write_code(
        BANK2_POINTER_READ_RVA,
        bytes.fromhex("8b0d") + struct.pack("<I", BANK2_OBJECT_GLOBAL_VA),
    )
    write_code(
        BANK2_HELPER_CALL_RVA,
        bytes([0xE8]) + struct.pack(
            "<i", BANK2_HELPER_RVA - (BANK2_HELPER_CALL_RVA + 5)
        ),
    )
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


def synthetic_mode_objects(code: bytes):
    """Construct synthetic .rdata vtables and constant-return getter instructions."""
    rdata_rva = 0x31E000
    rdata = bytearray(0x26000)
    updated_code = bytearray(code)
    for name, ctor, vtable, object_global, getter, mode in WARDROBE_MODE_OBJECTS:
        ctor_code = (
            bytes.fromhex("c700") + struct.pack("<I", vtable)
            + bytes([0xA3]) + struct.pack("<I", object_global)
        )
        updated_code[ctor - CODE_RVA:ctor - CODE_RVA + len(ctor_code)] = ctor_code
        struct.pack_into("<I", rdata, vtable - IMAGE_BASE - rdata_rva + 0x54,
                         IMAGE_BASE + getter)
        getter_bytes = bytes([0xB8]) + struct.pack("<I", mode) + bytes([0xC3])
        updated_code[getter - CODE_RVA:getter - CODE_RVA + 6] = getter_bytes
    bank2_ctor = (
        bytes.fromhex("c700") + struct.pack("<I", BANK2_VTABLE_VA)
        + bytes([0xA3]) + struct.pack("<I", BANK2_OBJECT_GLOBAL_VA)
    )
    updated_code[
        BANK2_CTOR_RVA - CODE_RVA:BANK2_CTOR_RVA - CODE_RVA + 11
    ] = bank2_ctor
    struct.pack_into(
        "<I", rdata, BANK2_VTABLE_VA - IMAGE_BASE - rdata_rva + 0x54,
        IMAGE_BASE + BANK2_GETTER_RVA,
    )
    updated_code[
        BANK2_GETTER_RVA - CODE_RVA:BANK2_GETTER_RVA - CODE_RVA + 6
    ] = bytes([0xB8]) + struct.pack("<I", 9) + bytes([0xC3])
    return bytes(rdata), bytes(updated_code)




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


    def test_constructor_vtable_and_getters_prove_four_mode_constants(self):
        _, decoded = synthetic_ui_tables()
        rdata, decoded = synthetic_mode_objects(decoded)
        report = inspect_2019_mode_object_getters(rdata, 0x31E000, decoded)
        self.assertEqual(report["status"], "EXACT_MODE_OBJECT_CHAIN_VERIFIED")
        self.assertTrue(report["command_to_mode_mapping_proved_by_static_getters"])
        self.assertEqual([x["command"] for x in report["mode_objects"]],
                         ["/wardrobe", "/wardrobe2", "/wardrobe3", "/wardrobe4"])
        self.assertEqual([x["reported_mode"] for x in report["mode_objects"]],
                         [8, 10, 11, 12])
        self.assertTrue(report["mode_9_is_not_one_of_four_wardrobe_commands"])
        self.assertTrue(all(
            x["constructor_sets_expected_vtable_and_global"]
            and x["vtable_slot_points_to_getter"]
            and x["getter_returns_constant_mode"]
            for x in report["mode_objects"]
        ))
        self.assertFalse(report["object_creation_or_ui_runtime_execution_verified"])
        self.assertFalse(report["client_mode_13_to_16_implemented"])

    def test_corrupted_constructor_vtable_or_mode_getter_fail_closed(self):
        _, decoded = synthetic_ui_tables()
        rdata, decoded = synthetic_mode_objects(decoded)
        first = WARDROBE_MODE_OBJECTS[0]
        for label, broken_rdata, broken_code in (
            ("constructor", rdata, decoded[:first[1] - CODE_RVA] +
             bytes([decoded[first[1] - CODE_RVA] ^ 1]) +
             decoded[first[1] - CODE_RVA + 1:]),
            ("vtable", rdata[:first[2] - IMAGE_BASE - 0x31E000 + 0x54] +
             bytes([rdata[first[2] - IMAGE_BASE - 0x31E000 + 0x54] ^ 1]) +
             rdata[first[2] - IMAGE_BASE - 0x31E000 + 0x55:], decoded),
            ("getter", rdata, decoded[:first[4] - CODE_RVA + 1] +
             bytes([decoded[first[4] - CODE_RVA + 1] ^ 1]) +
             decoded[first[4] - CODE_RVA + 2:]),
        ):
            with self.subTest(kind=label):
                report = inspect_2019_mode_object_getters(
                    broken_rdata, 0x31E000, broken_code
                )
                self.assertEqual(report["status"], "INCOMPLETE_STATIC_EVIDENCE")
                self.assertFalse(
                    report["command_to_mode_mapping_proved_by_static_getters"])
                self.assertIsNone(
                    report["mode_9_is_not_one_of_four_wardrobe_commands"])

    def test_incomplete_rdata_and_wrong_types_reject_mode_mapping(self):
        _, decoded = synthetic_ui_tables()
        report = inspect_2019_mode_object_getters(bytes(32), 0x31E000, decoded)
        self.assertEqual(report["status"], "INCOMPLETE_STATIC_EVIDENCE")
        self.assertIsNone(report["mode_9_is_not_one_of_four_wardrobe_commands"])
        with self.assertRaises(Pol1Error):
            inspect_2019_mode_object_getters(bytearray(64), 0x31E000, decoded)
        with self.assertRaises(Pol1Error):
            inspect_2019_mode_object_getters(bytes(64), True, decoded)


    def test_adjacent_bank2_getter_is_mode_9_not_a_wardrobe(self):
        data, code = synthetic_ui_tables()
        rdata, code = synthetic_mode_objects(code)
        report = inspect_2019_bank2_mode9(
            data, DATA_RVA, rdata, 0x31E000, code,
        )
        self.assertEqual(report["status"], "ORIGINAL_BANK2_MODE_9_VERIFIED")
        self.assertEqual(report["command"], "/bank2")
        self.assertEqual(report["command_id"], 115)
        self.assertEqual(report["returned_mode"], 9)
        self.assertEqual(report["helper_rva"], "0x1D1570")
        self.assertTrue(all(report["static_checks"].values()))
        self.assertTrue(report["mode9_reserved_for_original_bank2_path"])
        self.assertFalse(report["runtime_execution_or_complete_ui_semantics_proved"])

    def test_bank2_command_constructor_and_mode_getter_tampering_fail_closed(self):
        data, code = synthetic_ui_tables()
        rdata, code = synthetic_mode_objects(code)
        for kind, data2, rdata2, code2 in (
            ("name", data[:BANK2_COMMAND_RVA-DATA_RVA] +
             b"X" + data[BANK2_COMMAND_RVA-DATA_RVA+1:], rdata, code),
            ("dispatch", data[:BANK2_HANDLER_RECORD_RVA-DATA_RVA] +
             b"X" + data[BANK2_HANDLER_RECORD_RVA-DATA_RVA+1:], rdata, code),
            ("getter", data, rdata, code[:BANK2_GETTER_RVA-CODE_RVA+1] +
             bytes([0x0A]) + code[BANK2_GETTER_RVA-CODE_RVA+2:]),
        ):
            with self.subTest(kind=kind):
                report = inspect_2019_bank2_mode9(
                    data2, DATA_RVA, rdata2, 0x31E000, code2,
                )
                self.assertEqual(report["status"], "INCOMPLETE_STATIC_EVIDENCE")
                self.assertIsNone(report["mode9_reserved_for_original_bank2_path"])


if __name__ == "__main__":
    unittest.main()
