#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    template = (ROOT / "gui" / "templates" / "capture_help.html").read_text(encoding="utf-8")
    shell = (ROOT / "workbench" / "gui_shell.py").read_text(encoding="utf-8")
    server = (ROOT / "gui_server.py").read_text(encoding="utf-8")
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
        "Captain StatTrack",
        "Generic PCAP / PCAPNG",
        "Capturebar video / screenshots",
        "PriceLog",
    ]
    for name in required_supported:
        assert name in template, name

    required_gaps = [
        "Lobby / world / search application decoding",
        "PacketDB ZONES / PACKET_DEFINITION",
        "Captain PacketBridge live stream",
        "Runtime-only Captain/Windower helpers",
        "PacketViewer-derived NDJSON / analysis interchange",
        "Unknown historical/community loggers",
    ]
    for name in required_gaps:
        assert name in template, name

    assert "Recognized but intentionally not duplicated" in template
    assert "Raw packet convergence" in template
    assert "source_format" in template
    assert "opcode + direction + exact raw bytes" in template
    assert "<code>CHATLOG</code>" in template
    assert "__UNKNOWN_ZONE__" in template
    assert "Supported as network evidence" in template
    assert "Historical/runtime tools audited but not separate file formats" in template

    print("Capture help support matrix regression: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
