#!/usr/bin/env python3
"""Regression contract for Entity implementation dossier integration."""

from pathlib import Path

from workbench.devtools.entities import profile as entity_profile

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

    # Missing evidence alone must not create implementation actions.
    profile["behavior_summary"] = {}
    profile["event_wiring"] = []
    assert entity_profile.synthesize_implementation_actions(profile) == [], profile

    action_profile = {
        "attention": [{
            "kind": "provenance_conflict",
            "label": "Sources disagree on position",
            "detail": "client_dat=(1,2,3) · topaz_sql=(4,5,6)",
        }],
        "lua_hits": {"scripts/zones/Test/npcs/Test.lua": []},
        "behavior_summary": {
            "available": True,
            "shared_helpers": [
                {"qualified_name": "xi.test.missingHelper", "status": "UNRESOLVED"},
            ],
        },
        "event_wiring": [
            {
                "event_id": 202,
                "runtime_observed": True,
                "client_defined": False,
                "count": 3,
                "href": "/events/view?zone=Test&entity=1&csid=202",
            },
            {
                "event_id": 203,
                "runtime_observed": False,
                "client_defined": True,
                "decompile_status": "invalid",
                "decompile_detail": "invalid bytecode",
                "href": "/events/view?zone=Test&entity=1&csid=203",
            },
        ],
    }
    actions = entity_profile.synthesize_implementation_actions(action_profile)
    kinds = {row["kind"] for row in actions}
    assert {
        "provenance_conflict",
        "shared_helper_resolution",
        "runtime_event_client_gap",
        "client_event_decompile",
    } <= kinds, actions

    server = (ROOT / "src" / "workbench" / "app" / "_host_impl.py").read_text(encoding="utf-8")
    template = (ROOT / "gui" / "templates" / "entity_detail.html").read_text(encoding="utf-8")

    assert 'profile["event_wiring"] = []' in server
    assert '"client_defined": bool(health_row)' in server
    assert '"runtime_observed": bool(observed["count"])' in server
    assert "scan_event_health(event_dir" in server
    assert "def _entity_behavior_summary(" in server
    assert "inspect_lsb_behavior(root, chosen[\"path\"])" in server
    assert '"behavior_summary"' in server
    assert '"callback_ownership": []' in server
    assert '"scheduled_callbacks": []' in server
    assert "entity_profile.synthesize_implementation_actions(profile)" in server
    assert "def _entity_relationship_summary(" in server
    assert "feature_trace.trace(" in server
    assert '"incoming": []' in server
    assert '"outgoing": []' in server
    assert 'profile["feature_trace_path"] = {}' in server
    assert "feature_trace.entity_implementation_path(graph_con, con, str(npcid))" in server
    assert '"coverage_cues": path.get("coverage_cues") or []' in server

    assert "Entity evidence bridge" in template
    assert "Feature Trace implementation path" in template
    assert "Open full Implementation Path" in template
    assert "source representations" in template
    assert "provider branches" in template
    assert "source-native links" in template
    assert "direct graph relationships" in template
    assert "direct evidence IDs" in template
    assert "Feature Trace coverage cues describe indexed evidence state only" in template
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
    assert "Callback / source ownership" in template
    assert "Scheduled callback evidence" in template
    assert "Evidence-backed implementation actions" in template
    assert "Missing evidence by itself does not create an action" in template
    assert "Used By / direct canonical relationships" in template
    assert "Used by / incoming" in template
    assert "Direct dependencies / outgoing" in template
    assert "Exact source-native links" in template
    assert "Open full Feature Trace" in template
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
