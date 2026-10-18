#!/usr/bin/env python3
"""Read-only command evidence scanner: exact boundaries, offsets and scan bounds."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from workbench.client.command_evidence import command_evidence, exact_command_probe


def main():
    data = b"prefix\0/wardrobe\0" + b"\x00" * 7 + b"/wardrobe2\0" + b"/wardrobe8x\0"
    assert exact_command_probe(data, "/wardrobe")["count"] == 1
    assert exact_command_probe(data, "/wardrobe2")["count"] == 1
    assert exact_command_probe(data, "/wardrobe8")["count"] == 0
    evidence = command_evidence(data)
    assert [r["token"] for r in evidence["hits"]] == ["/wardrobe", "/wardrobe2", "/wardrobe8x"]
    assert evidence["hits"][0]["offset"] == 7
    assert evidence["hits"][0]["terminated_nul"]
    assert command_evidence(b"x" * (64 * 1024 * 1024 + 1))["status"] == "skipped"
    try:
        exact_command_probe(data, "wardrobe")
    except ValueError:
        pass
    else:
        raise AssertionError("missing leading slash must be invalid")
    print("command evidence self-test: PASS")


if __name__ == "__main__":
    main()
