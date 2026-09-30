#!/usr/bin/env python3
"""Static/functional regression contract for the coordinated packet decoder workbench."""

from pathlib import Path

import packet_decode

ROOT = Path(__file__).resolve().parents[1]


def main():
    # Real 52-byte 0x034 shape used as a bounded layout exercise. The assertions deliberately
    # check byte mapping/coverage mechanics rather than assigning semantics beyond the active DB.
    raw = (
        "34 1A F4 03 BD 11 0F 01 00 00 00 00 00 00 00 00 "
        "05 00 00 00 00 00 00 00 FF C3 3F 00 47 D2 14 0B "
        "FF 0F 00 00 1A 00 02 00 BD 01 F1 00 5F 03 B8 00 "
        "F1 00 00 00"
    )
    layout = packet_decode.analyze_layout("s2c", 0x034, raw)
    assert layout["length"] == 52
    assert len(layout["bytes"]) == 52
    assert 0 <= layout["coverage_pct"] <= 100
    assert layout["claimed_bytes"] + layout["unknown_bytes"] == 52
    assert all("offset" in b and "hex" in b and "ascii" in b for b in layout["bytes"])
    assert all("range_hex" in r and "raw_hex" in r and "end" in r for r in layout["rows"])

    template = (ROOT / "gui" / "templates" / "packets_decode.html").read_text(encoding="utf-8")
    server = (ROOT / "gui_server.py").read_text(encoding="utf-8")
    backend = (ROOT / "packet_decode.py").read_text(encoding="utf-8")

    assert "Decoded structure" in template
    assert "Raw packet map" in template
    assert "schema coverage" in template
    assert 'class="packet-field' in template
    assert 'class="hex-byte' in template
    assert "function selectRow(row)" in template
    assert "uint32 LE" in template
    assert "float32 LE" in template
    assert "analyze_layout(direction, opcode_int, hex_bytes)" in server
    assert "def analyze_layout(" in backend

    print("Packet decoder coordinated field/hex UI regression: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
