#!/usr/bin/env python3
"""Regression contract for capture-native packet decoder integration."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    server = (ROOT / "src" / "workbench" / "app" / "_host_impl.py").read_text(encoding="utf-8")
    base = (ROOT / "gui" / "templates" / "base.html").read_text(encoding="utf-8")
    packet_list = (ROOT / "gui" / "templates" / "capture_packets.html").read_text(encoding="utf-8")
    packet_detail = (ROOT / "gui" / "templates" / "capture_packet_detail.html").read_text(encoding="utf-8")
    timeline = (ROOT / "gui" / "templates" / "capture_timeline.html").read_text(encoding="utf-8")
    query = (ROOT / "gui" / "templates" / "capture_query.html").read_text(encoding="utf-8")
    help_page = (ROOT / "gui" / "templates" / "capture_help.html").read_text(encoding="utf-8")
    roadmap = (ROOT / "docs" / "workbench" / "ROADMAP.md").read_text(encoding="utf-8")
    capture_detail = (ROOT / "gui" / "templates" / "capture_detail.html").read_text(encoding="utf-8")
    packet_tools = (ROOT / "gui" / "templates" / "packets.html").read_text(encoding="utf-8")
    packet_manual = (ROOT / "gui" / "templates" / "packets_decode.html").read_text(encoding="utf-8")
    shell = (ROOT / "src" / "workbench" / "gui_shell.py").read_text(encoding="utf-8")

    assert '@app.get("/captures/{capture_id}/packets/{seq}"' in server
    assert 'packet_decode.analyze_layout(pd_direction, opcode_int, packet["raw_hex"])' in server
    assert "Capture direction is unknown" in server
    assert "unique known opcode definition; capture direction remains unknown" in server
    assert "capture_packet_correlations" in server
    assert "neighbor_rows = con.execute(" in server
    assert '"neighbors": neighbors' in server
    assert 'normalized_table") == "capture_raw_packets"' in server
    assert 'f"/captures/{locator[\'capture_id\']}/packets/{seq}"' in server

    assert "main.wide-workbench" in base
    assert "{% block main_class %}{% endblock %}" in base
    assert "max-width: 980px" not in base
    assert "main { width: 100%; max-width: none;" in base
    assert "main.narrow-content" in base
    assert "{% block main_class %}wide-workbench{% endblock %}" in packet_detail
    assert "Packet Viewer" in packet_detail
    assert "Packet Browser" in packet_detail
    assert "Session packets" in packet_detail
    assert "Decoded structure" in packet_detail
    assert "Raw packet map" in packet_detail
    assert "Selected field" in packet_detail
    assert "Capture context" in packet_detail
    assert "Source provenance" in packet_detail
    assert "Cross-source correlations" in packet_detail
    assert "open exact source row/block" in packet_detail
    assert "function esc(value)" in packet_detail
    assert "coverage {{ layout.coverage_pct }}%" in packet_detail

    assert 'href="/captures/{{ capture_id }}/packets/{{ r.seq }}"' in packet_list
    assert "Packet Browser" in packet_list
    assert "Open Packet Viewer" in packet_list
    assert "open in manual decoder" in packet_list
    assert 'href="/captures/{{ capture_id }}/packets/{{ r.seq }}"' in timeline
    assert "table == 'capture_raw_packets' and c == 'seq'" in query

    assert "open Packet Browser" in capture_detail
    assert "Open Packet Browser" in capture_detail
    assert "Manual Packet Viewer / Decoder" in packet_tools
    assert "Packet Browser" in packet_tools
    assert "Manual Packet Viewer / Decoder" in packet_manual
    assert '{"label": "Packet Tools", "href": "/packets"}' in shell

    assert "Packet inspection is capture-native" in help_page
    assert "Future live stream rule" in help_page
    assert "Unified packet inspection surface" in roadmap
    assert "Live world-session packet producer" in roadmap

    print("Capture-native packet decoder integration regression: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
