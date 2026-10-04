from __future__ import annotations

from workbench.devtools.behavior.plain_view import build_plain_behavior_projection


def _graph() -> dict:
    return {
        "nodes": [
            {"id": "behavior:test", "kind": "subject", "label": "Test NPC", "meta": {}},
            {"id": "hook:onTrigger", "kind": "hook", "label": "onTrigger", "meta": {}},
            {"id": "rule:test", "kind": "rule", "label": "CONDITIONAL", "meta": {}},
            {"id": "condition:key", "kind": "condition", "label": "hasKeyItem TEST_KEY", "meta": {"value": "TEST_KEY"}},
            {"id": "state:step", "kind": "state", "label": "state:MissionStep", "meta": {}},
            {"id": "condition:step", "kind": "condition", "label": "getCharVar MissionStep", "meta": {"value": 3}},
            {"id": "effect:event", "kind": "effect", "label": "START_EVENT · 100", "meta": {"effect": "START_EVENT", "value": 100}},
            {"id": "effect:set", "kind": "effect", "label": "setCharVar LegacyStatus", "meta": {"effect": "SET_CHAR_VAR", "value": 3}},
            {"id": "target:event", "kind": "target", "label": "CSID 100", "meta": {}},
        ],
        "edges": [
            {"source": "behavior:test", "target": "hook:onTrigger", "kind": "HAS_HOOK"},
            {"source": "condition:key", "target": "rule:test", "kind": "GUARDS"},
            {"source": "condition:step", "target": "rule:test", "kind": "GUARDS"},
            {"source": "state:step", "target": "condition:step", "kind": "STATE_GUARD"},
            {"source": "hook:onTrigger", "target": "rule:test", "kind": "HAS_RULE"},
            {"source": "rule:test", "target": "effect:event", "kind": "EMITS"},
            {"source": "rule:test", "target": "effect:set", "kind": "EMITS"},
            {"source": "effect:event", "target": "target:event", "kind": "STARTS_EVENT"},
        ],
    }


def test_plain_projection_collapses_rule_scaffolding_but_keeps_semantic_nodes():
    result = build_plain_behavior_projection(_graph())

    assert result["available"] is True
    assert result["summary"]["flow_count"] == 1
    assert result["summary"]["collapsed_implementation_nodes"] == 1
    assert result["safety"]["evidence_preserved"] is True
    assert result["safety"]["collapsed_kinds"] == ["rule"]

    flow = result["flows"][0]
    assert flow["trigger"]["label"] == "Player interacts with this actor"
    assert [row["node_id"] for row in flow["collapsed_implementation_nodes"]] == ["rule:test"]
    visible_ids = {
        row["node_id"]
        for lane in ("requirements", "actions", "results")
        for row in flow[lane]
    }
    assert "rule:test" not in visible_ids
    assert "condition:key" in visible_ids
    assert "condition:step" in visible_ids
    assert "state:step" in visible_ids
    assert "effect:event" in visible_ids
    assert "effect:set" in visible_ids
    assert "target:event" in visible_ids


def test_plain_projection_recovers_upstream_guards_that_are_not_trigger_descendants():
    result = build_plain_behavior_projection(_graph())
    requirements = result["flows"][0]["requirements"]
    requirement_ids = [row["node_id"] for row in requirements]

    assert requirement_ids == ["condition:key", "condition:step", "state:step"]
    assert any("key item" in row["label"].lower() for row in requirements)
    assert any("character/game state" in row["label"].lower() for row in requirements)


def test_plain_projection_summary_uses_only_visible_extracted_labels():
    result = build_plain_behavior_projection(_graph())
    summary = result["flows"][0]["summary"]

    assert summary.startswith("Player interacts with this actor.")
    assert "CONDITIONAL" not in summary
    assert "Requires a key item" in summary
    assert "START EVENT" in summary.upper() or "START EVENT" in summary.replace("_", " ").upper()
    assert "runtime" not in summary.lower()


def test_plain_projection_falls_back_to_subject_when_no_hook_exists():
    graph = {
        "nodes": [
            {"id": "behavior:test", "kind": "subject", "label": "Test NPC", "meta": {}},
            {"id": "effect:spawn", "kind": "effect", "label": "SPAWN_ENTITY", "meta": {"effect": "SPAWN_ENTITY"}},
        ],
        "edges": [{"source": "behavior:test", "target": "effect:spawn", "kind": "EMITS"}],
    }

    result = build_plain_behavior_projection(graph)
    assert result["available"] is True
    assert result["flows"][0]["trigger"]["node_id"] == "behavior:test"
    assert result["summary"]["technical_node_count"] == 2
