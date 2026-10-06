#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    template = (ROOT / "gui" / "templates" / "capture_help.html").read_text(encoding="utf-8")
    shell = (ROOT / "src" / "workbench" / "gui_shell.py").read_text(encoding="utf-8")
    server = (ROOT / "src" / "workbench" / "app" / "_host_impl.py").read_text(encoding="utf-8")
    captures = (ROOT / "gui" / "templates" / "captures.html").read_text(encoding="utf-8")

    assert '@app.get("/captures/help"' in server
    assert '"href": "/captures/help"' in shell
    assert 'href="/captures/help"' in captures

    required_supported = [
        "Windower PacketLogger",
        "PacketViewer",
        "MalRD PacketDB",
        "Ashita Packeteer",
        "NPCLogger SQLite",
        "Legacy NPCLogger Lua",
        "ActionView",
        "EventView",
        "IDView",
        "CapLog",
        "Windower Logger",
        "HPTrack",
        "KITrack",
        "LevelRangeTrack",
        "AttackDelay",
        "PathLog",
        "MissionTrack",
        "ShopStock",
        "GuildStock",
        "WeatherTrack",
        "POITrack",
        "SpawnTrack",
        "CheckParam",
        "CraftTrack",
        "ConquestTrack",
        "PriceLog",
        "PCAP / PCAPNG",
    ]
    for name in required_supported:
        assert name in template, name

    required_gaps = [
        "Captain EventView v2 standalone logs",
        "Lobby + search/cache TCP decoding",
        "PacketDB ZONES / PACKET_DEFINITION",
        "Unknown historical/community loggers",
    ]
    for name in required_gaps:
        assert name in template, name

    assert "Recognized but intentionally not duplicated" in template
    assert "Raw packet convergence" in template
    assert "Canonical chat convergence" in template
    assert "Historical tool archaeology" in template
    assert "CAPTURE_TOOL_ARCHAEOLOGY.md" in template
    assert "capture_chat_observations" in template
    assert "capturebar_overlay" in template
    assert "CAPTUREBAR_CONTEXT" in template
    assert "PCAP/PCAPNG limits" in template
    assert "Network planes" in template
    assert "TCP reconstruction" in template
    assert "Validated lobby decoding" in template
    assert "capture_network_messages" in template
    assert "ffxi_lobby" in template
    assert "Ports are not used as proof" in template
    assert "unknown_tcp" in template
    assert "Missing bytes are never synthesized" in template
    assert "LOBBY_WORLD_STREAM_RESEARCH.md" in template
    assert "search/cache" in template
    assert "storage/account subflows" in template
    assert "direction <code>unknown</code>" in template
    assert "Blowfish" in template and "zlib" in template
    assert "X/Z/Y" in template
    assert "__UNKNOWN__" in template
    assert "whole-session" in template.lower()
    assert "source_format" in template
    assert "opcode + direction + exact raw bytes" in template

    print("Capture help support matrix regression: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
