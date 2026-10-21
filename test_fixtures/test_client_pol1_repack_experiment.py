#!/usr/bin/env python3
"""Synthetic-only tests for bounded experimental POL1 recompression."""
import hashlib
import io
import json
import random
import struct
import tempfile
import sys
import unittest
from contextlib import redirect_stdout, redirect_stderr
from unittest.mock import patch
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from workbench.client.pol1_repack_experiment import encode_pol1, assess_pol1_repack_fit, _stream_termination_metadata
from workbench.client.pol1_unpack import unpack_pol1, Pol1Error


def fixture_pe(raw: bytes, expected: int, capacity: int | None = None) -> bytes:
    """Make a minimal synthetic PE-shaped fixture. Never use retail data."""
    capacity = len(raw) if capacity is None else capacity
    assert len(raw) <= capacity
    pe = 0x80
    image = bytearray(0x200 + capacity)
    image[0:2] = b"MZ"
    struct.pack_into("<I", image, 0x3C, pe)
    image[pe:pe + 4] = b"PE\0\0"
    struct.pack_into("<H", image, pe + 6, 2)
    struct.pack_into("<H", image, pe + 20, 0xE0)
    struct.pack_into("<H", image, pe + 24, 0x10B)
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




    def test_rejects_zero_distance_ambiguity_before_declaring_prefix_fit(self):
        # The original decoder accepts this malformed stream by skipping a
        # zero-distance group, but a writable-prefix proof must reject it.
        malformed = bytes((0, 0, 0, 0xE0)) + b"abc"
        image = fixture_pe(malformed, 3)
        self.assertEqual(unpack_pol1(image)["bytes"], b"abc")
        with self.assertRaisesRegex(Pol1Error, "invalid POL1 back-reference"):
            assess_pol1_repack_fit(image)

    def test_rejects_malformed_pe_metadata_before_fit(self):
        original = fixture_pe(encode_pol1(b"abcabc"), 6)
        invalid = bytearray(original)
        invalid[0:2] = b"XX"
        with self.assertRaisesRegex(Pol1Error, "DOS signature"):
            assess_pol1_repack_fit(bytes(invalid))
        invalid = bytearray(original)
        struct.pack_into("<H", invalid, 0x80 + 24, 0xFFFF)
        with self.assertRaisesRegex(Pol1Error, "optional-header magic"):
            assess_pol1_repack_fit(bytes(invalid))




    def test_bounded_search_depths_and_cli_report(self):
        from workbench.client.cli.pol1_repack_report import main

        original = bytes(range(32)) * 80
        for depth in (16, 64, 128):
            encoded = encode_pol1(original, search_depth=depth)
            independently_decoded, consumed = independent_pol1_decode(encoded, len(original))
            self.assertEqual(independently_decoded, original)
            self.assertEqual(consumed, len(encoded))
            image = fixture_pe(encoded, len(original))
            result = assess_pol1_repack_fit(image, search_depth=depth)
            self.assertEqual(result["encoder_search_depth"], depth)
        with self.assertRaises(Pol1Error):
            encode_pol1(b"abc", search_depth=1000000)
        with self.assertRaises(Pol1Error):
            encode_pol1(b"abc", search_depth=True)
        with tempfile.TemporaryDirectory() as folder:
            file_path = Path(folder) / "synthetic.dll"
            file_path.write_bytes(fixture_pe(encode_pol1(b"abcabc"), 6))
            digest = hashlib.sha256(file_path.read_bytes()).hexdigest()
            with patch("sys.argv", [
                "pol1-repack-report", str(file_path),
                "--expected-sha256", digest, "--search-depth", "16"
            ]):
                output = io.StringIO()
                with redirect_stdout(output):
                    self.assertEqual(main(), 0)
                self.assertIn('"encoder_search_depth": 16', output.getvalue())




    def test_cli_comparison_mode_reuses_exact_hash_and_never_writes(self):
        from workbench.client.cli.pol1_repack_report import main

        code = b"MOCKRESEARCH" * 45
        image = fixture_pe(encode_pol1(code), len(code), len(encode_pol1(code)) + 8)
        with tempfile.TemporaryDirectory() as folder:
            file_path = Path(folder) / "synthetic.dll"
            file_path.write_bytes(image)
            digest = hashlib.sha256(image).hexdigest()
            with patch("sys.argv", [
                "pol1-repack-report", str(file_path),
                "--expected-sha256", digest, "--compare-depths"
            ]):
                output = io.StringIO()
                with redirect_stdout(output):
                    self.assertEqual(main(), 0)
            report = json.loads(output.getvalue())
            self.assertEqual(report["source_sha256"], digest)
            self.assertIn("original_stream_sha256", report)
            for comparison in report["results"]:
                self.assertIn("candidate_matches_original_stream", comparison)
                self.assertIn("candidate_common_prefix_bytes", comparison)
                self.assertIn("candidate_sha256", comparison)
            self.assertTrue(report["pol1_raw_section_isolated"])
            self.assertIn("entrypoint_boundary_safe", report)
            self.assertIn("entrypoint_in_pol1", report)
            self.assertEqual([row["depth"] for row in report["results"]], [16, 64, 128])
            self.assertEqual(len(report["results"]), 3)
            self.assertEqual(report["best_fit_depth"]["status"], "FITS_ORIGINAL_STREAM_BUDGET")
            for row in report["results"]:
                self.assertEqual(row["in_memory_decoded_roundtrip"], "PASS")
                self.assertTrue(row["protected_suffix_unchanged"])
            with patch("sys.argv", [
                "pol1-repack-report", str(file_path),
                "--expected-sha256", "0" * 64, "--compare-depths"
            ]):
                with redirect_stderr(io.StringIO()):
                    with self.assertRaises(SystemExit):
                        main()
            self.assertEqual(file_path.read_bytes(), image)




    def test_rejects_overlapping_raw_sections_or_header_aliases(self):
        image = fixture_pe(encode_pol1(b"abcabc"), 6)
        table = 0x80 + 24 + 0xE0
        broken = bytearray(image)
        # Give the virtual .text section a nonzero raw extent coincident with
        # POL1, which makes the intended on-disk ownership ambiguous.
        struct.pack_into("<II", broken, table + 16, 4, 0x200)
        with self.assertRaisesRegex(Pol1Error, "overlaps another PE section"):
            assess_pol1_repack_fit(bytes(broken))

        broken = bytearray(image)
        # POL1's source bytes must not reside inside the section table itself.
        struct.pack_into("<I", broken, table + 40 + 20, table + 50)
        with self.assertRaisesRegex(Pol1Error, "overlaps PE headers"):
            assess_pol1_repack_fit(bytes(broken))




    def test_deep_and_lazy_encoder_preserve_original_code(self):
        rng = random.Random(1303)
        samples = [
            b"abcabc",
            bytes((i // 7) % 32 for i in range(9000)),
            (b"ABCxyz" * 2000) + (b"ABCxyzdef" * 200),
            bytes(rng.randrange(256) for _ in range(4096)),
        ]
        for source in samples:
            for depth, lazy in ((256, False), (512, False), (1024, False),
                                (128, True), (256, True), (512, True)):
                with self.subTest(size=len(source), depth=depth, lazy=lazy):
                    encoded = encode_pol1(source, search_depth=depth, lazy_match=lazy)
                    recovered, consumed = independent_pol1_decode(encoded, len(source))
                    self.assertEqual(recovered, source)
                    self.assertEqual(consumed, len(encoded))
        with self.assertRaises(Pol1Error):
            encode_pol1(b"abc", search_depth=2048)
        with self.assertRaises(Pol1Error):
            encode_pol1(b"abc", lazy_match=1)

    def test_cli_improved_comparison_records_modes_without_writes(self):
        from workbench.client.cli.pol1_repack_report import main

        code = b"abcabc"
        image = fixture_pe(encode_pol1(code), len(code), capacity=32)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "synthetic.dll"
            path.write_bytes(image)
            digest = hashlib.sha256(image).hexdigest()
            with patch("sys.argv", [
                "pol1-repack-report", str(path),
                "--expected-sha256", digest, "--compare-improved"
            ]):
                output = io.StringIO()
                with redirect_stdout(output):
                    self.assertEqual(main(), 0)
            report = json.loads(output.getvalue())
            self.assertEqual(report["comparison_mode"], "improved")
            self.assertEqual(
                [(x["depth"], x["lazy_match"]) for x in report["results"]],
                [(256, False), (512, False), (1024, False), (128, True), (256, True)]
            )
            self.assertTrue(report["pol1_raw_section_isolated"])
            self.assertEqual(len(report["results"]), 5)
            self.assertIsNotNone(report["best_fit_depth"])
            for item in report["results"]:
                self.assertEqual(item["status"], "FITS_ORIGINAL_STREAM_BUDGET")
                self.assertEqual(item["in_memory_decoded_roundtrip"], "PASS")
                self.assertTrue(item["protected_suffix_unchanged"])
            with patch("sys.argv", [
                "pol1-repack-report", str(path),
                "--expected-sha256", "0" * 64, "--compare-improved"
            ]):
                with redirect_stderr(io.StringIO()):
                    with self.assertRaises(SystemExit):
                        main()
            with patch("sys.argv", [
                "pol1-repack-report", str(path), "--expected-sha256", digest,
                "--compare-improved", "--lazy-match"
            ]):
                with redirect_stderr(io.StringIO()):
                    with self.assertRaises(SystemExit):
                        main()
            self.assertEqual(path.read_bytes(), image)




    def test_lazy_parsing_can_reduce_size_on_synthetic_pattern(self):
        source = (
            b"abcu" + b"Q" * 40 + b"bcdefghijklmnopqrstuvwxyz"
            + b"R" * 40 + b"abcdefghijklmnopqrstuvwxyz"
        )
        baseline = encode_pol1(source, search_depth=128)
        lazy = encode_pol1(source, search_depth=128, lazy_match=True)
        self.assertLess(len(lazy), len(baseline))
        decoded, used = independent_pol1_decode(lazy, len(source))
        self.assertEqual(decoded, source)
        self.assertEqual(used, len(lazy))



    def test_original_packed_stream_identity_and_lazy_divergence(self):
        original = (
            b"abcu" + b"Q" * 40 + b"bcdefghijklmnopqrstuvwxyz"
            + b"R" * 40 + b"abcdefghijklmnopqrstuvwxyz"
        )
        baseline = encode_pol1(original, search_depth=128)
        image = fixture_pe(baseline, len(original), len(baseline) + 23)
        baseline_report = assess_pol1_repack_fit(image, search_depth=128)
        self.assertEqual(baseline_report["in_memory_decoded_roundtrip"], "PASS")
        self.assertTrue(baseline_report["candidate_matches_original_stream"])
        self.assertEqual(
            baseline_report["original_stream_sha256"],
            baseline_report["candidate_sha256"]
        )
        self.assertEqual(baseline_report["candidate_common_prefix_bytes"], len(baseline))

        improved = assess_pol1_repack_fit(image, search_depth=128, lazy_match=True)
        self.assertEqual(improved["in_memory_decoded_roundtrip"], "PASS")
        self.assertLess(improved["candidate_encoded_size"], len(baseline))
        self.assertFalse(improved["candidate_matches_original_stream"])
        self.assertNotEqual(improved["original_stream_sha256"], improved["candidate_sha256"])
        self.assertLess(improved["candidate_common_prefix_bytes"], len(baseline))
        self.assertTrue(improved["protected_suffix_unchanged"])


    def test_decoder_end_metadata_counts_partial_group_without_loader_assumption(self):
        packed = encode_pol1(b"abcabc")
        end = _stream_termination_metadata(packed, 6)
        self.assertEqual(end["consumed_bytes"], len(packed))
        self.assertEqual(end["control_group_count"], 1)
        self.assertEqual(end["token_count"], 4)
        self.assertEqual(end["last_group_token_count"], 4)
        self.assertEqual(end["last_group_unused_flag_bits"], 4)
        self.assertFalse(end["last_group_unused_flags_nonzero"])
        self.assertEqual(end["last_token_kind"], "backreference")
        self.assertFalse(end["last_token_truncated_at_decoded_limit"])
        self.assertEqual(end["last_token_nominal_output_bytes"], 3)
        self.assertEqual(end["last_token_actual_output_bytes"], 3)

        literal_end = _stream_termination_metadata(bytes((0xFF, ord("A"))), 1)
        self.assertEqual(literal_end["consumed_bytes"], 2)
        self.assertEqual(literal_end["last_group_unused_flag_bits"], 7)
        self.assertTrue(literal_end["last_group_unused_flags_nonzero"])
        self.assertEqual(literal_end["last_token_kind"], "literal")
        with self.assertRaisesRegex(Pol1Error, "truncated"):
            _stream_termination_metadata(bytes((0x80,)), 1)

    def test_decoder_end_metadata_flags_nominal_overrun_without_editing_source(self):
        # One literal followed by a nominal 18-byte match, intentionally
        # clipped to three decoded bytes by our bounded decoder.
        original_stream = bytes((0x80, ord("A"), 0xF0, 0x01))
        end = _stream_termination_metadata(original_stream, 4)
        self.assertEqual(end["last_token_kind"], "backreference")
        self.assertEqual(end["last_token_nominal_output_bytes"], 18)
        self.assertEqual(end["last_token_actual_output_bytes"], 3)
        self.assertTrue(end["last_token_truncated_at_decoded_limit"])
        image = fixture_pe(original_stream, 4, capacity=len(original_stream) + 9)
        report = assess_pol1_repack_fit(image, search_depth=256)
        self.assertTrue(report["original_decoder_termination"]["last_token_truncated_at_decoded_limit"])
        self.assertFalse(report["candidate_decoder_termination"]["last_token_truncated_at_decoded_limit"])
        self.assertEqual(report["in_memory_decoded_roundtrip"], "PASS")

    def test_cli_comparison_contains_both_decoder_termination_views(self):
        from workbench.client.cli.pol1_repack_report import main

        image = fixture_pe(encode_pol1(b"abcabc"), 6, capacity=40)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "synthetic.dll"
            path.write_bytes(image)
            digest = hashlib.sha256(image).hexdigest()
            with patch("sys.argv", [
                "pol1-repack-report", str(path),
                "--expected-sha256", digest, "--compare-improved"
            ]):
                output = io.StringIO()
                with redirect_stdout(output):
                    self.assertEqual(main(), 0)
            result = json.loads(output.getvalue())
            self.assertEqual(result["original_decoder_termination"]["consumed_bytes"], 6)
            self.assertIsNone(result["bytes_between_stream_end_and_entrypoint"])
            for entry in result["results"]:
                meta = entry["candidate_decoder_termination"]
                self.assertEqual(meta["consumed_bytes"], entry["candidate_encoded_size"])
                self.assertIn(meta["last_token_kind"], ("literal", "backreference"))
            self.assertEqual(path.read_bytes(), image)



    def test_post_output_explicit_zero_distance_marker_in_same_control_group(self):
        source = b"abcabc"
        encoded = encode_pol1(source)
        self.assertEqual(encoded, b"\xe0abc\\x00\\x03")
        without_stop = _stream_termination_metadata(encoded, len(source))
        self.assertEqual(
            without_stop["post_output_next_token"]["status"],
            "NEXT_MATCH_WORD_INCOMPLETE"
        )
        with_stop = _stream_termination_metadata(encoded + b"\x00\\x00", len(source))
        self.assertEqual(with_stop["consumed_bytes"], len(encoded))
        self.assertEqual(with_stop["post_output_next_token"], {
            "status": "ZERO_DISTANCE_STOP",
            "zero_distance_stop": True,
            "marker_offset": len(encoded),
        })
        with_nonzero = _stream_termination_metadata(
            encoded + b"\x00\\x01", len(source)
        )
        self.assertEqual(
            with_nonzero["post_output_next_token"]["status"],
            "NEXT_MATCH_HAS_NONZERO_DISTANCE"
        )
        literal = _stream_termination_metadata(bytes((0xFF, ord("A"))), 1)
        self.assertEqual(
            literal["post_output_next_token"]["status"], "NEXT_TOKEN_IS_LITERAL"
        )

    def test_virtual_substitution_reports_next_token_without_writing(self):
        source = b"abcabc"
        encoded = encode_pol1(source)
        original_image = fixture_pe(encoded + b"\x00\\x00", len(source), len(encoded) + 7)
        copy = bytes(original_image)
        observed = assess_pol1_repack_fit(original_image, search_depth=256)
        self.assertEqual(observed["in_memory_decoded_roundtrip"], "PASS")
        self.assertTrue(observed["protected_suffix_unchanged"])
        self.assertEqual(
            observed["original_decoder_termination"]["post_output_next_token"]["status"],
            "ZERO_DISTANCE_STOP"
        )
        self.assertEqual(
            observed["virtual_substitution_post_output_next_token"]["status"],
            "ZERO_DISTANCE_STOP"
        )
        self.assertEqual(original_image, copy)

        shorter_source = (
            b"abcu" + b"Q" * 40 + b"bcdefghijklmnopqrstuvwxyz"
            + b"R" * 40 + b"abcdefghijklmnopqrstuvwxyz"
        )
        original_packed = encode_pol1(shorter_source, search_depth=128)
        original_image = fixture_pe(
            original_packed + b"\x00\\x00", len(shorter_source), len(original_packed) + 10
        )
        result = assess_pol1_repack_fit(
            original_image, search_depth=128, lazy_match=True
        )
        self.assertLess(result["candidate_encoded_size"], len(original_packed))
        self.assertEqual(result["in_memory_decoded_roundtrip"], "PASS")
        self.assertEqual(
            result["original_decoder_termination"]["post_output_next_token"]["status"],
            "ZERO_DISTANCE_STOP"
        )
        self.assertIn(
            result["virtual_substitution_post_output_next_token"]["status"],
            ("ZERO_DISTANCE_STOP", "NEXT_MATCH_HAS_NONZERO_DISTANCE",
             "NEXT_TOKEN_IS_LITERAL", "NEXT_MATCH_WORD_INCOMPLETE")
        )


if __name__ == "__main__":
    unittest.main()
