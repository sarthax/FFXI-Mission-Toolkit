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
)


def synthetic_commands():
    data_rva = FIRST_WARDROBE_COMMAND_RVA - 0x80
    data = bytearray(b"\\x00" * 512)
    for i, (name, command_id) in enumerate(EXPECTED_COMMAND_IDS.items()):
        at = 0x80 + i * RECORD_BYTES
        data[at:at + 16] = name.encode("ascii").ljust(16, b"\\x00")
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
        self.assertNotIn("bytes", repr(observed))
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


if __name__ == "__main__":
    unittest.main()
