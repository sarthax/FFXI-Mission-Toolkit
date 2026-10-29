#!/usr/bin/env python3
"""Synthetic static-window tests for 2019 UI-object ownership observations."""
import struct
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from workbench.client.pol1_unpack import Pol1Error
from workbench.client.wardrobe_2019_ui_objects import (
    UI_OBJECT_GLOBAL_COUNT, UI_OBJECT_GLOBAL_FIRST,
    UI_UPDATE_CALLEE_RVA, UI_CLEANUP_CALLEE_RVA,
    UI_DEALLOC_CALLEE_RVA, UI_CLEANUP_FIRST_RVA, UI_CLEANUP_STRIDE,
    inspect_2019_ui_object_lifecycle,
)

TEXT_RVA = 0x1000


def _relative_call(at: int, target: int) -> bytes:
    return bytes([0xE8]) + struct.pack("<i", target - (at + 5))


def synthetic_ui_lifecycle_windows() -> bytes:
    code = bytearray(0x160500 - TEXT_RVA)
    for i in range(UI_OBJECT_GLOBAL_COUNT):
        glob = UI_OBJECT_GLOBAL_FIRST + i * 4
        update = 0x159826 if i == 0 else (
            0x159831 if i == 1 else 0x15983C + (i - 2) * 0xF
        )
        load = bytes.fromhex("8b0d") + struct.pack("<I", glob)
        guard = b"" if i < 2 else bytes.fromhex("85c97405")
        call_start = update + len(load) + len(guard)
        source = load + guard + _relative_call(call_start, UI_UPDATE_CALLEE_RVA)
        code[update-TEXT_RVA:update-TEXT_RVA+len(source)] = source

        teardown = UI_CLEANUP_FIRST_RVA + i * UI_CLEANUP_STRIDE
        first = (
            bytes.fromhex("8b35") + struct.pack("<I", glob)
            + bytes.fromhex("3bf774168bce")
        )
        first += _relative_call(teardown+12, UI_CLEANUP_CALLEE_RVA)
        first += bytes.fromhex("56")
        first += _relative_call(teardown+18, UI_DEALLOC_CALLEE_RVA)
        first += bytes.fromhex("83c404893d") + struct.pack("<I", glob)
        assert len(first) == 32
        code[teardown-TEXT_RVA:teardown-TEXT_RVA+32] = first
    return bytes(code)


class Wardrobe2019UIObjectsTests(unittest.TestCase):
    def test_all_thirteen_selected_ui_update_and_teardown_paths(self):
        report = inspect_2019_ui_object_lifecycle(
            synthetic_ui_lifecycle_windows()
        )
        self.assertEqual(report["status"], "EXACT_13_UI_OBJECT_PATHS_VERIFIED")
        self.assertTrue(report["all_selected_paths_match"])
        self.assertEqual(report["selected_ui_object_pointer_count"], 13)
        self.assertEqual(len(report["entries"]), 13)
        self.assertEqual(
            [x["global_va"] for x in report["entries"]],
            [f"0x{UI_OBJECT_GLOBAL_FIRST + 4*i:X}" for i in range(13)],
        )
        self.assertTrue(all(
            x["update_path_matches"] and x["cleanup_free_and_clear_path_matches"]
            for x in report["entries"]
        ))
        self.assertEqual(
            report["entries"][-1]["selected_cleanup_block_rva"],
            "0x160380",
        )
        self.assertFalse(report["global_object_allocation_and_ctor_fully_mapped"])
        self.assertFalse(report["all_ui_owner_aliases_and_menu_lifetimes_mapped"])
        self.assertFalse(report["new_ui_object_instances_13_16_exist"])
        self.assertEqual(report["safety_decision"],
                         "NO_GO_APPEND_UI_OBJECT_POINTERS_IN_PLACE")

    def test_independent_update_mutations_fail_only_affected_item(self):
        original = synthetic_ui_lifecycle_windows()
        for i in (0, 1, 2, 7, 12):
            start = 0x159826 if i == 0 else (
                0x159831 if i == 1 else 0x15983C + (i - 2) * 0xF
            )
            for offset in (0, 2, 6 if i >= 2 else 7):
                with self.subTest(item=i, offset=offset):
                    mutated = bytearray(original)
                    mutated[start - TEXT_RVA + offset] ^= 0x01
                    result = inspect_2019_ui_object_lifecycle(bytes(mutated))
                    self.assertEqual(result["status"], "INCOMPLETE_STATIC_EVIDENCE")
                    self.assertFalse(result["all_selected_paths_match"])
                    self.assertFalse(result["entries"][i]["update_path_matches"])

    def test_wrong_teardown_targets_free_and_global_clear_fail_closed(self):
        original = synthetic_ui_lifecycle_windows()
        for i in (0, 4, 12):
            teardown = UI_CLEANUP_FIRST_RVA + i * UI_CLEANUP_STRIDE
            for byte_at in (0, 2, 7, 12, 19, 23, 26, 29):
                with self.subTest(item=i, byte_at=byte_at):
                    edited = bytearray(original)
                    edited[teardown - TEXT_RVA + byte_at] ^= 0x01
                    report = inspect_2019_ui_object_lifecycle(bytes(edited))
                    self.assertEqual(report["status"], "INCOMPLETE_STATIC_EVIDENCE")
                    self.assertFalse(
                        report["entries"][i]["cleanup_free_and_clear_path_matches"]
                    )

    def test_truncated_and_wrong_inputs_fail_closed(self):
        for bad in (None, bytearray(), "bytes"):
            with self.assertRaises(Pol1Error):
                inspect_2019_ui_object_lifecycle(bad)
        for invalid in (True, "0x1000", 1.0):
            with self.assertRaises(Pol1Error):
                inspect_2019_ui_object_lifecycle(b"", invalid)
        result = inspect_2019_ui_object_lifecycle(bytes(20))
        self.assertEqual(result["status"], "INCOMPLETE_STATIC_EVIDENCE")
        self.assertFalse(result["all_selected_paths_match"])
        with self.assertRaises(Pol1Error):
            inspect_2019_ui_object_lifecycle(bytes(8 * 1024 * 1024 + 1))


if __name__ == "__main__":
    unittest.main()
