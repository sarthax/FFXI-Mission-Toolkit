#!/usr/bin/env python3
"""Synthetic-only static .data arena and multiple live-context evidence tests."""
import struct
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from workbench.client.pol1_unpack import Pol1Error
from workbench.client.wardrobe_2019_allocator import (
    LIFECYCLE_MOTIFS, STATIC_ARENA_ZERO_BYTES, CONTEXT_RESET_BYTES,
    EXTENSION_BYTES, STATIC_FIRST_CONTEXT_VA, TEXT_RVA,
    _verify_lifecycle_motifs, describe_2019_allocator,
)


def fake_pe_data_section(virtual_size=0x670000):
    """Minimal synthetic PE header with an uninitialized, virtual .data range."""
    image = bytearray(0x400)
    image[:2] = b"MZ"
    struct.pack_into("<I", image, 0x3C, 0x80)
    image[0x80:0x84] = b"PE\0\0"
    struct.pack_into("<H", image, 0x80 + 6, 1)
    struct.pack_into("<H", image, 0x80 + 20, 0xE0)
    section = 0x80 + 24 + 0xE0
    image[section:section+8] = b".data\0\0\0"
    struct.pack_into("<IIII", image, section+8,
                     virtual_size, 0x344000, 0, 0)
    return bytes(image)


def fake_decoded_with_anchors():
    """Tiny instruction motifs embedded in inert synthetic filler, never a DLL."""
    end = max(rva + len(bytes.fromhex(motif)) - TEXT_RVA
              for _, rva, motif in LIFECYCLE_MOTIFS)
    image = bytearray(end + 1)
    for _, rva, motif in LIFECYCLE_MOTIFS:
        val = bytes.fromhex(motif)
        pos = rva - TEXT_RVA
        image[pos:pos + len(val)] = val
    return image


class Test2019InventoryArena(unittest.TestCase):
    def test_static_root_and_fixed_context_reset(self):
        evidence = describe_2019_allocator(fake_pe_data_section(),
                                           bytes(fake_decoded_with_anchors()))
        self.assertEqual(evidence["status"],
                         "VERIFIED_STATIC_INITIALIZATION_NOT_FULL_ALLOCATION_AUDIT")
        self.assertEqual(evidence["first_context_va"], "0x1096DB64")
        self.assertEqual(STATIC_FIRST_CONTEXT_VA, 0x1096DB64)
        self.assertTrue(evidence["first_root_in_virtual_data"])
        self.assertEqual(evidence["initial_arena_zero_bytes"], 257524)
        self.assertEqual(evidence["per_context_reset_zero_bytes"], 241792)
        self.assertEqual(evidence["hypothetical_four_wardrobe_record_bytes"], 14256)
        self.assertEqual(evidence["hypothetical_four_wardrobe_end_exclusive"], "0x1850C")
        self.assertEqual(evidence["hypothetical_five_container_record_bytes"], 17820)
        self.assertEqual(evidence["hypothetical_new_records_start"], "0x14D5C")
        self.assertEqual(evidence["hypothetical_new_records_end_exclusive"], "0x192F8")
        self.assertTrue(evidence["multiple_active_context_assignment_sites"])
        self.assertEqual(len(evidence["anchor_evidence"]), len(LIFECYCLE_MOTIFS))
        self.assertNotIn("code_bytes", evidence)
        self.assertEqual(STATIC_ARENA_ZERO_BYTES, 0x3EDF4)
        self.assertEqual(CONTEXT_RESET_BYTES, 0x3B080)
        self.assertEqual(EXTENSION_BYTES, 5*81*44)

    def test_any_changed_anchor_fails_closed(self):
        decoded = fake_decoded_with_anchors()
        name, rva, needle = LIFECYCLE_MOTIFS[7]
        decoded[rva-TEXT_RVA] ^= 0x80
        with self.assertRaisesRegex(Pol1Error, name):
            _verify_lifecycle_motifs(bytes(decoded))

    def test_wrong_virtual_section_and_short_code_rejected(self):
        with self.assertRaisesRegex(Pol1Error, "not contained"):
            describe_2019_allocator(
                fake_pe_data_section(0x100000),
                bytes(fake_decoded_with_anchors()))
        with self.assertRaisesRegex(Pol1Error, "window outside"):
            describe_2019_allocator(fake_pe_data_section(), b"\x00"*32)


if __name__ == "__main__":
    unittest.main()
