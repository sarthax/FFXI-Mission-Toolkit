#!/usr/bin/env python3
"""Static/functional regression contract for the coordinated packet decoder workbench."""

from pathlib import Path

from workbench.packets import decode as packet_decode

ROOT = Path(__file__).resolve().parents[1]


def main():
    # Real 52-byte 0x034 shape used as a bounded layout exercise. The assertions deliberately
    # check byte mapping/coverage mechanics rather than assigning semantics beyond the active DB.
    raw = (
        "34 1A C0 00 38 D3 04 01 01 00 00 00 00 00 00 00 "
        "94 0B 00 00 90 00 00 00 90 00 00 00 00 00 00 00 "
        "03 00 00 00 FF 0F 00 00 38 03 4D 00 2D 01 08 00 "
        "4D 00 00 00"
    )
    packetlogger_grid = """[2025-05-01 23:24:24]
        |  0  1  2  3  4  5  6  7  8  9  A  B  C  D  E  F      | 0123456789ABCDEF
    -----------------------------------------------------  ----------------------
      0 | 37 30 4E 00 53 FF FF FF FF FF FF FF FF FF FF FF    0 | 70N.S...........
      1 | FF FF FF FF FF FF FF FF FF FF FF FF FF FF FF FF    1 | ................
      2 | FF FF FF FF D3 F2 07 00 08 04 64 00 3B 00 64 00    2 | ..........d.;.d.
      3 | 00 38 38 38 00 00 20 00 00 00 00 00 20 A0 03 00    3 | .888.. ..... ...
      4 | 20 F7 E3 2B 00 00 00 00 00 00 00 00 01 00 00 00    4 |  ..+............
      5 | 00 00 00 00 00 00 00 00 80 03 00 00 3B 00 00 00    5 | ............;...
"""
    from workbench.captures.ingestion import build_index as build_capture_index
    parsed = build_capture_index.parse_packetlogger_records(packetlogger_grid, "0x037")
    assert len(parsed) == 1, parsed
    assert parsed[0]["ts"] == "2025-05-01 23:24:24", parsed
    assert parsed[0]["raw_hex"].startswith("37304E0053"), parsed
    assert len(parsed[0]["raw_hex"]) == 96 * 2, len(parsed[0]["raw_hex"])

    layout = packet_decode.analyze_layout("s2c", 0x034, raw)
    assert layout["length"] == 52
    assert len(layout["bytes"]) == 52
    assert 0 <= layout["coverage_pct"] <= 100
    assert layout["claimed_bytes"] + layout["unknown_bytes"] == 52
    assert all("offset" in b and "hex" in b and "ascii" in b for b in layout["bytes"])
    assert all("range_hex" in r and "raw_hex" in r and "end" in r for r in layout["rows"])

    template = (ROOT / "gui" / "templates" / "packets_decode.html").read_text(encoding="utf-8")
    tools_template = (ROOT / "gui" / "templates" / "packets.html").read_text(encoding="utf-8")
    server = (ROOT / "src" / "workbench" / "app" / "_host_impl.py").read_text(encoding="utf-8")
    backend = (ROOT / "src" / "workbench" / "packets" / "_decode_impl.py").read_text(encoding="utf-8")

    assert "{% block main_class %}wide-workbench{% endblock %}" in template
    assert "Decoded structure" in template
    assert "Raw packet map" in template
    assert "Selected field" in template
    assert "Scratch context" in template
    assert "coverage {{ layout.coverage_pct }}%" in template
    assert 'class="packet-field' in template
    assert 'class="hex-byte' in template
    assert "function selectRow(row)" in template
    assert "function esc(value)" in template
    assert "uint32 LE" in template
    assert "float32 LE" in template
    assert "Bulk Packet Decode" in template
    assert 'action="/packets/bulk"' in template
    assert 'enctype="multipart/form-data"' in template
    assert 'name="packet_files"' in template
    assert 'multiple' in template
    assert 'rows="18"' in template
    assert 'method="post" action="/packets/decode"' in template
    assert 'name="hex_bytes" rows="8"' in template
    assert "Open in Packet Viewer" in template
    assert "r.raw_hex|urlencode" in template
    assert 'href="/packets/decode?mode=bulk"' in tools_template
    assert 'RedirectResponse(url="/packets/decode?mode=bulk", status_code=303)' in server
    assert '"mode": "bulk"' in server
    assert '"bulk_rows": decoded_rows or None' in server
    assert "build_capture_index.ingest_single_file" in server
    assert "build_capture_index.ingest_from_source" in server
    assert "def _packet_decoder_upload_rows(" in server
    assert "def _packet_decoder_normalize_text(" in server
    assert "analyze_layout(direction, opcode_int, normalized_hex)" in server
    assert '@app.post("/packets/decode"' in server
    assert "def analyze_layout(" in backend

    print("Packet decoder coordinated field/hex UI regression: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
