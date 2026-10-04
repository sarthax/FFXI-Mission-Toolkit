from __future__ import annotations

from workbench.devtools.behavior.plain_view import build_plain_behavior_projection


def _helper_graph() -> dict:
    return {
        "nodes": [
            {"id": "behavior:test", "kind": "subject", "label": "Test NPC", "meta": {}},
            {"id": "hook:onTrigger", "kind": "hook", "label": "onTrigger", "meta": {}},
            {"id": "rule:test", "kind": "rule", "label": "CONDITIONAL", "meta": {}},
            {"id": "effect:helper", "kind": "effect", "label": "CALL_SYSTEM_HELPER · xi.test.run", "meta": {"effect": "CALL_SYSTEM_HELPER"}},
            {"id": "shared-helper:xi.test.run", "kind": "shared_helper", "label": "xi.test.run", "meta": {"resolution_status": "RESOLVED"}},
            {"id": "shared-helper-call:xi.test.run:0", "kind": "helper_call", "label": "player:addKeyItem", "meta": {}},
            {"id": "shared-helper-callee:xi.test.run:0", "kind": "shared_helper_callee", "label": "xi.test.finish", "meta": {"status": "RESOLVED"}},
            {"id": "shared-helper-effect:xi.test.run:0", "kind": "helper_effect", "label": "GRANT_KEY_ITEM · TEST_KEY", "meta": {"impact_kind": "GRANT_KEY_ITEM", "value": "TEST_KEY"}},
        ],
        "edges": [
            {"source": "behavior:test", "target": "hook:onTrigger", "kind": "HAS_HOOK"},
            {"source": "hook:onTrigger", "target": "rule:test", "kind": "HAS_RULE"},
            {"source": "rule:test", "target": "effect:helper", "kind": "EMITS"},
            {"source": "effect:helper", "target": "shared-helper:xi.test.run", "kind": "CALLS_SHARED_HELPER"},
            {"source": "shared-helper:xi.test.run", "target": "shared-helper-call:xi.test.run:0", "kind": "HELPER_DIRECT_CALL"},
            {"source": "shared-helper:xi.test.run", "target": "shared-helper-callee:xi.test.run:0", "kind": "CALLS_NESTED_SHARED_HELPER"},
            {"source": "shared-helper:xi.test.run", "target": "shared-helper-effect:xi.test.run:0", "kind": "HELPER_DOWNSTREAM_EFFECT"},
        ],
    }


def test_plain_projection_identifies_helper_plumbing_separately_from_semantic_helper_evidence():
    result = build_plain_behavior_projection(_helper_graph())
    flow = result["flows"][0]
    visible = {row["node_id"] for lane in ("requirements", "actions", "results") for row in flow[lane]}

    # Resolved helper identity and its source-proven downstream effect are meaningful Plain View evidence.
    assert "shared-helper:xi.test.run" in visible
    assert "shared-helper-effect:xi.test.run:0" in visible

    # These are currently visible implementation-detail candidates; this fixture locks down the
    # distinction before we collapse them in the next implementation slice.
    assert "shared-helper-call:xi.test.run:0" in visible
    assert "shared-helper-callee:xi.test.run:0" in visible


def test_helper_projection_remains_explicitly_evidence_only():
    result = build_plain_behavior_projection(_helper_graph())
    assert result["safety"]["evidence_preserved"] is True
    assert "does not infer runtime outcomes" in result["safety"]["semantics"]
