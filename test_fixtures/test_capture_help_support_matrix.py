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
        "PriceLog",
    ]
    for name in required_supported:
        assert name in template, name

    required_gaps = [
        "Capturebar",
        "PCAP / PCAPNG",
        "Lobby / world-server packet streams",
        "PacketDB ZONES / PACKET_DEFINITION",
        "Unknown historical/community loggers",
    ]
    for name in required_gaps:
        assert name in template, name

    assert "Recognized but intentionally not duplicated" in template
    assert "Raw packet convergence" in template
    assert "Canonical chat convergence" in template
    assert "capture_chat_observations" in template
    assert "__UNKNOWN__" in template
    assert "whole-session" in template.lower()
    assert "source_format" in template
    assert "opcode + direction + exact raw bytes" in template

    print("Capture help support matrix regression: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
