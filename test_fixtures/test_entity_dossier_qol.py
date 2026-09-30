#!/usr/bin/env python3
"""Regression contract for Entity implementation dossier integration."""

from pathlib import Path

import entity_profile

ROOT = Path(__file__).resolve().parents[1]


def main():
    profile = {
        "name": "Test NPC",
        "npcid": 17000001,
        "zoneid": 77,
        "zone_folder": "Nyzul_Isle",
        "id_decode": {"zone_bits": 77},
        "npc_list": {
            "pos": (1.0, 2.0, 3.0),
            "untargetable": False,
        },
        "sql_hits": {"npc_list.sql": ["row"]},
        "lua_hits": {"scripts/zones/Nyzul_Isle/npcs/TestNPC.lua": []},
        "script_name_guess": "TestNPC",
        "instance_memberships": [
            {"instanceid": 1, "instance_name": "test_instance", "instance_zone": 77, "entrance_zone": 72},
        ],
        "capture_events": [{"event_hex": "0x00CA", "message_id": 7465, "count": 2}],
        "wiki_references": [{"title": "Test NPC", "url": "https://example.invalid", "kind": "primary"}],
        "field_sources": {
            "name": [
                {"source": "client_dat", "value": "Test NPC", "confidence": "high"},
                {"source": "topaz_sql", "value": "Test NPC", "confidence": "server"},
            ]
        },
        "gap_warning": False,
        "mob_chain": None,
    }
    entity_profile._synthesize_profile(profile)
    assert profile["behavior_source"].endswith("/npcs/TestNPC.lua"), profile
    assert any(row["label"] == "Lua references" and row["present"] for row in profile["evidence_summary"])
    assert any(row["label"] == "instance_entities" for row in profile["wiring_chain"])
    assert profile["attention"] == [], profile

    server = (ROOT / "gui_server.py").read_text(encoding="utf-8")
    template = (ROOT / "gui" / "templates" / "entity_detail.html").read_text(encoding="utf-8")

    assert 'profile["event_wiring"] = []' in server
    assert '"client_defined": bool(health_row)' in server
    assert '"runtime_observed": bool(observed["count"])' in server
    assert "scan_event_health(event_dir" in server
    assert "def _entity_behavior_summary(" in server
    assert "inspect_lsb_behavior(root, chosen[\"path\"])" in server
    assert '"behavior_summary"' in server

    assert "Entity evidence bridge" in template
    assert "Needs attention" in template
    assert "SQL / implementation wiring" in template
    assert "Observed CSID / dialog wiring" in template
    assert "Lua behavior summary" in template
    assert "Important effects / engine-facing behavior" in template
    assert "Lua / engine API calls" in template
    assert "Event lifecycle" in template
    assert "State / helper summary" in template
    assert "Binding Reference" in template
    assert "Open full Behavior Inspector" in template
    assert "defined in client" in template
    assert "not observed in captures" in template
    assert "Open Event Wiring Dossier" in template
    assert "Inspect Lua behavior" in template
    assert "Feature Trace" in template
    assert "Capture evidence" in template
    assert 'id="entity-provenance"' in template

    print("Entity implementation dossier regression: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
