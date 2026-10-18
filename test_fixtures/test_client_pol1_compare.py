#!/usr/bin/env python3
"""Cross-build comparison preserves UNKNOWN and missing measurements."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from workbench.client.cli.pol1_compare import compare_reports


def test_comparison():
    old = {"unpacked": {"sha256": "old"}, "wardrobe_commands": {"sha256": "dll-old", "commands": [
        {"command": "/wardrobe", "status": "VERIFIED_BYTES"},
        {"command": "/wardrobe5", "status": "UNKNOWN"}]}}
    new = {"unpacked": {"sha256": "new"}, "wardrobe_commands": {"sha256": "dll-new", "commands": [
        {"command": "/wardrobe", "status": "VERIFIED_BYTES"},
        {"command": "/wardrobe5", "status": "VERIFIED_BYTES"}]}}
    diff = compare_reports(old, new)
    entries = {x["command"]: x for x in diff["command_comparison"]}
    assert entries["/wardrobe"]["result"] == "UNCHANGED"
    assert entries["/wardrobe5"]["result"] == "DIFFERENT_EVIDENCE"
    assert entries["/wardrobe8"]["result"] == "NOT_MEASURED"
    assert not diff["identical_decoded_code"]
    assert compare_reports(old, old)["identical_decoded_code"]

if __name__ == "__main__":
    test_comparison()
    print("POL1 cross-build report test: PASS")
