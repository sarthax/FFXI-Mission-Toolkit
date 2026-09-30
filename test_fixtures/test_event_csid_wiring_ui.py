#!/usr/bin/env python3
"""Regression contract for Events/CSID wiring dossier QOL."""

from pathlib import Path

import explore_event

ROOT = Path(__file__).resolve().parents[1]


def main():
    sample = """function event()
    npc:dialog(7466, 0, 0)
    vm:systemMessage(7465)
    player:startEvent(202)
end
"""
    summary = explore_event.summarize_decompile(sample)
    assert summary["message_ids"] == [7466, 7465], summary
    assert any(c["method"] == "dialog" for c in summary["calls"]), summary
    assert any(c["method"] == "startEvent" for c in summary["calls"]), summary

    scaffold = explore_event.lua_scaffold(
        202,
        observed_options=[0, 1, 1],
        observed_params=["1, 2, 3", "4, 5, 6"],
    )
    assert "player:startEvent(202)" in scaffold
    assert "observed option values: 0, 1" in scaffold
    assert "observed capture params (uninterpreted)" in scaffold
    assert "Scaffolding only" in scaffold

    server = (ROOT / "gui_server.py").read_text(encoding="utf-8")
    browser = (ROOT / "gui" / "templates" / "events.html").read_text(encoding="utf-8")
    detail = (ROOT / "gui" / "templates" / "event_view.html").read_text(encoding="utf-8")
    bridge = (ROOT / "vendor" / "xi-events-py" / "decompile_from_mission_toolkit.py").read_text(encoding="utf-8")
    explore = (ROOT / "explore_event.py").read_text(encoding="utf-8")

    assert "def _event_server_refs(" in server
    assert "def _event_capture_rows(" in server
    assert "lua_events.typed_calls(" in server
    assert "explore_event.lua_scaffold(" in server
    assert "server_ref_count" in server
    assert "runtime_count" in server
    assert "return explore_event.decompile_event(out_dir, entity_id, csid, zoneid)" in server
    assert "scan_event_health(events_yml.parent, zoneid)" in server
    assert "def scan_event_health(" in explore
    assert "fixture_from_documents(" in bridge
    assert 'sys.stdout.reconfigure(encoding="utf-8", errors="replace")' in bridge

    assert "Wiring dossier" in browser
    assert "0x{{ \"%04X\"|format(r.csid) }}" in browser
    assert "runtime obs." in browser
    assert "decompile health" in browser
    assert "stub / empty" in browser
    assert "decompile failed" in browser
    assert "View decompile issue" in browser

    assert "Client CSID decompile" in detail
    assert "Runtime observations" in detail
    assert "Dialog / message IDs" in detail
    assert "Server implementation references" in detail
    assert "Lua implementation scaffold" in detail
    assert "Lua / engine handoff calls in this handler" in detail
    assert "/backport/bindings?q={{ call.method|urlencode }}" in detail
    assert "Copy decompile" in detail
    assert "Copy Lua" in detail
    assert "Client decompile unavailable" in detail
    assert "independent server/runtime evidence" in detail

    print("Events/CSID wiring dossier regression: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
