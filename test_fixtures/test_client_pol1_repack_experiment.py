#!/usr/bin/env python3
"""Synthetic-only tests for bounded experimental POL1 recompression."""
import hashlib
import io
import random
import struct
import tempfile
import sys
import unittest
from contextlib import redirect_stdout, redirect_stderr
from unittest.mock import patch
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


def independent_pol1_decode(tokens: bytes, expected: int) -> tuple[bytes, int]:
    """Second synthetic token reader, independently structured from unpack_pol1."""
    out = bytearray()
    at = 0
    while len(out) < expected:
        if at >= len(tokens):
            raise ValueError("truncated control group")
        flags = tokens[at]
        at += 1
        for shift in range(7, -1, -1):
            if len(out) == expected:
                break
            if (flags >> shift) & 1:
                if at >= len(tokens):
                    raise ValueError("truncated literal")
                out.append(tokens[at])
                at += 1
            else:
                if at + 2 > len(tokens):
                    raise ValueError("truncated backreference")
                word = int.from_bytes(tokens[at:at + 2], "big")
                at += 2
                distance = word & 4095
                if distance == 0 or distance > len(out):
                    raise ValueError("invalid distance")
                size = min(expected - len(out), (word >> 12) + 3)
                for _ in range(size):
                    out.append(out[-distance])
    return bytes(out), at



class SyntheticPol1RepackTests(unittest.TestCase):
    def test_reference_vector_and_no_write(self):
        sample = b"abcabc"
        packed = encode_pol1(sample)
        self.assertEqual(packed, b"\xe0abc\x00\x03")
        image = fixture_pe(packed, len(sample), len(packed) + 5)
        snapshot = bytes(image)
        report = assess_pol1_repack_fit(image)
        self.assertEqual(report["status"], "FITS_ORIGINAL_STREAM_BUDGET")
        self.assertEqual(report["headroom_bytes"], 0)
        self.assertEqual(report["protected_suffix_bytes"], 5)
        self.assertTrue(report["protected_suffix_unchanged"])
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
        self.assertEqual(assess_pol1_repack_fit(original)["status"], "FITS_ORIGINAL_STREAM_BUDGET")
        rng = random.Random(2026)
        high_entropy = bytes(rng.randrange(256) for _ in range(8192))
        report = assess_pol1_repack_fit(original, high_entropy)
        self.assertEqual(report["status"], "EXCEEDS_ORIGINAL_STREAM_BUDGET")
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
        self.assertEqual(report["status"], "FITS_ORIGINAL_STREAM_BUDGET")
        self.assertEqual(report["in_memory_decoded_roundtrip"], "PASS")
        self.assertNotEqual(report["decoded_sha256"], report["candidate_decoded_sha256"])


    def test_cli_exact_hash_gate(self):
        from workbench.client.cli.pol1_repack_report import main

        image = fixture_pe(encode_pol1(b"abcabc"), 6, 11)
        with tempfile.TemporaryDirectory() as folder:
            file_path = Path(folder) / "synthetic.dll"
            file_path.write_bytes(image)
            digest = hashlib.sha256(image).hexdigest()
            with patch("sys.argv", ["pol1-repack-report", str(file_path), "--expected-sha256", digest]):
                output = io.StringIO()
                with redirect_stdout(output):
                    self.assertEqual(main(), 0)
                self.assertIn("FITS_ORIGINAL_STREAM_BUDGET", output.getvalue())
            with patch("sys.argv", ["pol1-repack-report", str(file_path), "--expected-sha256", "0" * 64]):
                with redirect_stderr(io.StringIO()):
                    with self.assertRaises(SystemExit):
                        main()
            self.assertEqual(file_path.read_bytes(), image)



    def test_preserves_loader_suffix_and_refuses_false_raw_fit(self):
        packed = encode_pol1(b"abcabc")
        image = bytearray(fixture_pe(packed, 6, len(packed) + 64))
        stub_at = len(packed) + 24
        image[0x200 + stub_at:0x200 + stub_at + 10] = b"LOADERSTUB"
        # PE entry point is at the end of the preserved compressed-stream
        # region, in the same synthetic POL1 section as our raw bytes.
        struct.pack_into("<I", image, 0x80 + 24 + 16, 0x9000 + stub_at)
        image = bytes(image)
        report = assess_pol1_repack_fit(image)
        self.assertEqual(report["status"], "FITS_ORIGINAL_STREAM_BUDGET")
        self.assertEqual(report["original_stream_consumed_bytes"], len(packed))
        self.assertEqual(report["safe_stream_budget_bytes"], len(packed))
        self.assertEqual(report["entrypoint_section_offset"], stub_at)
        self.assertTrue(report["protected_suffix_unchanged"])
        self.assertEqual(report["protected_suffix_bytes"], 64)

        # This candidate WOULD fit the raw section, but no longer fits the
        # actual original compressed-stream prefix. The old implementation
        # incorrectly treated loader bytes as available space.
        changed = assess_pol1_repack_fit(image, b"abcdef")
        self.assertLess(changed["candidate_encoded_size"], 64)
        self.assertEqual(changed["status"], "EXCEEDS_ORIGINAL_STREAM_BUDGET")
        self.assertEqual(changed["in_memory_decoded_roundtrip"], "NOT_ATTEMPTED")
        self.assertEqual(image[0x200 + stub_at:0x200 + stub_at + 10], b"LOADERSTUB")

    def test_rejects_stream_that_overlaps_entrypoint(self):
        packed = encode_pol1(b"abcabc")
        image = bytearray(fixture_pe(packed, 6, len(packed) + 16))
        struct.pack_into("<I", image, 0x80 + 24 + 16, 0x9000 + 2)
        result = assess_pol1_repack_fit(bytes(image))
        self.assertEqual(result["status"], "UNSAFE_ORIGINAL_STREAM_BOUNDARY")
        self.assertFalse(result["entrypoint_boundary_safe"])
        self.assertEqual(result["in_memory_decoded_roundtrip"], "NOT_ATTEMPTED")



    def test_independent_oracle_randomized_streams(self):
        rng = random.Random(1303)
        for length in range(1, 192):
            if length % 3 == 0:
                original = bytes(rng.randrange(256) for _ in range(length))
            elif length % 3 == 1:
                original = bytes((i // 3) % 17 for i in range(length))
            else:
                original = (b"abccba" * ((length + 5) // 6))[:length]
            encoded = encode_pol1(original)
            decoded, consumed = independent_pol1_decode(encoded, length)
            self.assertEqual(decoded, original)
            self.assertEqual(consumed, len(encoded))



if __name__ == "__main__":
    unittest.main()
