#!/usr/bin/env python3
"""Synthetic-only tests for bounded experimental POL1 recompression."""
import random
import struct
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from workbench.client.pol1_repack_experiment import encode_pol1, assess_pol1_repack_fit
from workbench.client.pol1_unpack import unpack_pol1, Pol1Error


def fixture_pe(raw: bytes, expected: int, capacity: int | None = None) -> bytes:
    """Make a minimal synthetic PE-shaped fixture. Never use retail data."""
    capacity = len(raw) if capacity is None else capacity
    assert len(raw) <= capacity
    pe = 0x80
    image = bytearray(0x200 + capacity)
    struct.pack_into("<I", image, 0x3C, pe)
    image[pe:pe + 4] = b"PE\0\0"
    struct.pack_into("<H", image, pe + 6, 2)
    struct.pack_into("<H", image, pe + 20, 0xE0)
    table = pe + 24 + 0xE0
    for offset, name, vsize, rva, rawsize, rawoff in (
        (table, b".text", expected, 0x1000, 0, 0),
        (table + 40, b"POL1", capacity, 0x9000, capacity, 0x200),
    ):
        image[offset:offset + 8] = name.ljust(8, b"\0")
        struct.pack_into("<IIII", image, offset + 8, vsize, rva, rawsize, rawoff)
    image[0x200:0x200 + len(raw)] = raw
    return bytes(image)


class SyntheticPol1RepackTests(unittest.TestCase):
    def test_reference_vector_and_no_write(self):
        sample = b"abcabc"
        packed = encode_pol1(sample)
        self.assertEqual(packed, b"\xe0abc\x00\x03")
        image = fixture_pe(packed, len(sample), len(packed) + 5)
        snapshot = bytes(image)
        report = assess_pol1_repack_fit(image)
        self.assertEqual(report["status"], "FITS_RAW_SECTION")
        self.assertEqual(report["headroom_bytes"], 5)
        self.assertEqual(report["in_memory_decoded_roundtrip"], "PASS")
        self.assertEqual(image, snapshot)

    def test_sizes_and_random_data(self):
        rng = random.Random(20261021)
        patterns = [
            b"Z" * 8192,
            b"hello\x00" * 600,
            bytes(range(256)) * 25,
            bytes(rng.randrange(256) for _ in range(4096)),
        ]
        patterns += [b"abcdef"[:n] for n in range(1, 7)]
        for source in patterns:
            with self.subTest(length=len(source)):
                packed = encode_pol1(source)
                image = fixture_pe(packed, len(source))
                self.assertEqual(unpack_pol1(image)["bytes"], source)
                self.assertEqual(encode_pol1(source), packed)

    def test_out_of_capacity_and_rejections(self):
        original = fixture_pe(encode_pol1(b"a" * 8192), 8192)
        self.assertEqual(assess_pol1_repack_fit(original)["status"], "FITS_RAW_SECTION")
        rng = random.Random(2026)
        high_entropy = bytes(rng.randrange(256) for _ in range(8192))
        report = assess_pol1_repack_fit(original, high_entropy)
        self.assertEqual(report["status"], "EXCEEDS_RAW_SECTION")
        self.assertEqual(report["in_memory_decoded_roundtrip"], "NOT_ATTEMPTED")
        with self.assertRaises(Pol1Error):
            assess_pol1_repack_fit(original, b"too short")
        for bad in [b"", bytearray(b"abc"), "string"]:
            with self.assertRaises(Pol1Error):
                encode_pol1(bad)
        with self.assertRaises(Pol1Error):
            assess_pol1_repack_fit(b"broken PE")

    def test_overlap_and_history_limits(self):
        source = b"Q" * 5000 + b"unique" + b"Q" * 5000
        packed = encode_pol1(source)
        self.assertEqual(unpack_pol1(fixture_pe(packed, len(source)))["bytes"], source)

    def test_same_length_in_memory_candidate_changes_decoded_hash(self):
        original = b"a" * 8192
        candidate = b"b" * 8192
        image = fixture_pe(encode_pol1(original), len(original))
        report = assess_pol1_repack_fit(image, candidate)
        self.assertEqual(report["status"], "FITS_RAW_SECTION")
        self.assertEqual(report["in_memory_decoded_roundtrip"], "PASS")
        self.assertNotEqual(report["decoded_sha256"], report["candidate_decoded_sha256"])


if __name__ == "__main__":
    unittest.main()
