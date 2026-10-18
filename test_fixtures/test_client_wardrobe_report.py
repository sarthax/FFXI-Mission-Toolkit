#!/usr/bin/env python3
"""Exact Wardrobe command evidence must not confuse prefix matches."""
import tempfile
from pathlib import Path
from workbench.client.cli.pol1_report import wardrobe_command_evidence

def test_wardrobe_commands_are_exact():
    with tempfile.TemporaryDirectory() as d:
        file = Path(d) / "client.dll"
        file.write_bytes(b"/wardrobe4\0 /wardrobe8x\0 /wardrobe\0 /wardrobe5\0")
        report = wardrobe_command_evidence(str(file))
        by_name = {row["command"]: row for row in report["commands"]}
        assert by_name["/wardrobe"]["status"] == "VERIFIED_BYTES"
        assert by_name["/wardrobe4"]["status"] == "VERIFIED_BYTES"
        assert by_name["/wardrobe5"]["status"] == "VERIFIED_BYTES"
        assert by_name["/wardrobe8"]["status"] == "UNKNOWN"
        assert by_name["/wardrobe2"]["status"] == "UNKNOWN"
        assert report["sha256"]

if __name__ == "__main__":
    test_wardrobe_commands_are_exact()
    print("wardrobe command report: PASS")
