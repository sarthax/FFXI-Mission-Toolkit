#!/usr/bin/env python3
"""Synthetic-only exact-2019 wardrobe layout and fingerprint checks."""
import hashlib
import struct
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from workbench.client.pol1_unpack import Pol1Error
from workbench.client.wardrobe_2019_audit import (
    CODE_WINDOWS,
    LEGACY_TEXT_RVA,
    _extract_commands,
    _verify_code_windows,
    audit_2019_wardrobe,
    inspect_2019_wardrobe,
    legacy_layout_risk,
)


def synthetic_command_pe() -> bytes:
    """Clearly synthetic PE section with table-shaped rows, not client data."""
    image = bytearray(0x800)
    image[:2] = b"MZ"
    struct.pack_into("<I", image, 0x3C, 0x80)
    image[0x80:0x84] = b"PE\0\0"
    struct.pack_into("<H", image, 0x80 + 6, 1)
    struct.pack_into("<H", image, 0x80 + 20, 0xE0)
    section = 0x80 + 24 + 0xE0
    image[section:section+8] = b".data\0\0\0"
    struct.pack_into("<IIII", image, section + 8,
                     0x600, 0x34B000, 0x600, 0x200)
    names = [
        ("/wardrobe", 111), ("/wardrobe2", 112),
        ("/wardrobe3", 113), ("/wardrobe4", 114),
        ("/bank2", 115), ("/mailbox", 116),
        ("/deliverybox", 116), ("/sendpost", 118),
        ("/layout", 119), ("/remodel", 120),
    ]
    for index, (name, number) in enumerate(names):
        at = 0x200 + 0x1B0 + index * 24
        image[at:at+16] = name.encode("ascii").ljust(16, b"\0")
        struct.pack_into("<H", image, at + 20, number)
    return bytes(image)


class TestLegacyWardrobeAudit(unittest.TestCase):
    def test_hypothetical_new_container_collides_with_existing_state(self):
        facts = legacy_layout_risk()
        self.assertEqual(facts["record_stride_bytes"], 3564)
        self.assertEqual(facts["hypothetical_container_13_start"], 0x14D5C)
        self.assertEqual(facts["hypothetical_container_13_end_exclusive"], 0x15B48)
        self.assertTrue(facts["overlaps_observed_other_state"])
        self.assertTrue(facts["overlaps_capacity8"])
        self.assertTrue(facts["overlaps_capacity16"])
        self.assertEqual(facts["capacity16_end_exclusive"], 0x15314)
        self.assertEqual(facts["interpretation"], "INFERRED_OVERLAP_NOT_A_VALID_ALLOCATION")

    def test_command_rows_and_original_id_collisions(self):
        image = synthetic_command_pe()
        result = _extract_commands(image)
        self.assertEqual([v["command_id"] for v in result],
                         [111, 112, 113, 114, 118, 119, 120])
        self.assertEqual(result[0]["name"], "/wardrobe")
        self.assertEqual(result[-1]["name"], "/remodel")

        altered = bytearray(image)
        altered[0x200 + 0x1B0] = ord("X")
        with self.assertRaisesRegex(Pol1Error, "unexpected row"):
            _extract_commands(bytes(altered))

    def test_code_window_probes_are_metadata_only_and_fail_closed(self):
        size = max(rva + width - LEGACY_TEXT_RVA for _, rva, width, _, _ in CODE_WINDOWS)
        decoded = bytearray(size + 1)
        for _, rva, width, offsets, motifs in CODE_WINDOWS:
            at = rva - LEGACY_TEXT_RVA
            cursor = 0
            for offset in offsets:
                decoded[at + cursor:at + cursor + 4] = struct.pack("<I", offset)
                cursor += 4
            for motif in motifs:
                decoded[at + cursor:at + cursor + len(motif)] = motif
                cursor += len(motif)
            self.assertLessEqual(cursor, width)
        result = _verify_code_windows(bytes(decoded))
        self.assertEqual(len(result), len(CODE_WINDOWS))
        self.assertTrue(all(entry["status"] == "VERIFIED_BYTES" for entry in result))
        self.assertNotIn("bytes", str(result).lower().replace("verified_bytes", ""))

        first_rva = CODE_WINDOWS[0][1]
        decoded[first_rva - LEGACY_TEXT_RVA] = 255
        with self.assertRaisesRegex(Pol1Error, "capacity_u8_reader"):
            _verify_code_windows(bytes(decoded))

    def test_original_file_hash_guard_and_no_io(self):
        with self.assertRaisesRegex(Pol1Error, "exact-size"):
            audit_2019_wardrobe(b"")
        with self.assertRaisesRegex(Pol1Error, "exact 2019 original SHA"):
            audit_2019_wardrobe(b"\0" * 2_870_352)

    def test_read_only_file_wrapper_rejects_wrong_size(self):
        import tempfile
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "not-a-client.dll"
            path.write_bytes(b"TEST")
            with self.assertRaisesRegex(Pol1Error, "unexpected source size"):
                inspect_2019_wardrobe(path)
            self.assertEqual(path.read_bytes(), b"TEST")


if __name__ == "__main__":
    unittest.main()
