#!/usr/bin/env python3
"""Regression contract for capture-native packet decoder integration."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    server = (ROOT / "gui_server.py").read_text(encoding="utf-8")
    packet_list = (ROOT / "gui" / "templates" / "capture_packets.html").read_text(encoding="utf-8")
    packet_detail = (ROOT / "gui" / "templates" / "capture_packet_detail.html").read_text(encoding="utf-8")
    timeline = (ROOT / "gui" / "templates" / "capture_timeline.html").read_text(encoding="utf-8")
    query = (ROOT / "gui" / "templates" / "capture_query.html").read_text(encoding="utf-8")
    help_page = (ROOT / "gui" / "templates" / "capture_help.html").read_text(encoding="utf-8")
    roadmap = (ROOT / "docs" / "workbench" / "ROADMAP.md").read_text(encoding="utf-8")

    assert '@app.get("/captures/{capture_id}/packets/{seq}"' in server
    assert "packet_decode.analyze_layout(pd_direction, opcode_int, packet["raw_hex"])" in server
    assert "Capture direction is unknown" in server
    assert "unique known opcode definition; capture direction remains unknown" in server
    assert "capture_packet_correlations" in server
    assert 'normalized_table") == "capture_raw_packets"' in server
    assert 'f"/captures/{locator[\'capture_id\']}/packets/{seq}"' in server

    assert 'href="/captures/{{ capture_id }}/packets/{{ r.seq }}"' in packet_list
    assert "inspect in capture context" in packet_list
    assert "open scratch decoder" in packet_list
    assert 'href="/captures/{{ capture_id }}/packets/{{ r.seq }}"' in timeline
    assert "table == 'capture_raw_packets' and c == 'seq'" in query

    assert "Decoded structure" in packet_detail
    assert "Raw packet map" in packet_detail
    assert "Source provenance" in packet_detail
    assert "Cross-source correlations" in packet_detail
    assert "open exact source row/block" in packet_detail
    assert "schema coverage" in packet_detail

    assert "Packet inspection is capture-native" in help_page
    assert "Future live stream rule" in help_page
    assert "Unified packet inspection surface" in roadmap
    assert "Live world-session packet producer" in roadmap

    print("Capture-native packet decoder integration regression: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
