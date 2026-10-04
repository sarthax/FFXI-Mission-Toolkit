from __future__ import annotations

from workbench.editors.character.transition_bundles import (
    annotate_transition_bundles,
    build_transition_bundle,
)


def _action() -> dict:
    return {
        "transition_id": "quest:7:13:step4",
        "trigger": "onTrigger",
        "event": {"zone": "GRAUBERG_S", "actor": "qm5", "event_id": 11},
        "effects": [
            {"effect": "SET_VAR", "subject": "quest_var:Prog", "value": 4},
            {"effect": "GRANT", "subject": "key_item:TEST_REWARD", "value": True},
            {"effect": "REMOVE", "subject": "key_item:TEST_KEY", "value": True},
            {"effect": "COMPLETE", "subject": "quest:FIRES_OF_DISCONTENT", "value": True},
            {"effect": "START", "subject": "quest:LIGHT_IN_THE_DARKNESS", "value": True},
        ],
        "conditions": [
            {
                "subject": "quest_var:Prog",
                "operator": "EQ",
                "expected": 3,
                "actual": 2,
                "resolved": True,
                "matches": False,
                "editor": "Variables",
                "runtime_only": False,
            },
            {
                "subject": "trade:item:1234",
                "operator": "HAS",
                "expected": True,
                "actual": None,
                "resolved": False,
                "matches": None,
                "editor": None,
                "runtime_only": True,
            },
        ],
        "eligibility": "BLOCKED",
        "progression": True,
        "progression_score": 4,
        "runtime_requirements": [],
        "implementation_status": "VERIFIED",
        "section_index": 2,
        "source_lines": [40, 62],
        "logical_event_chain": True,
    }


def test_transition_bundle_groups_progression_semantics_without_losing_evidence():
    bundle = build_transition_bundle(_action())

    assert bundle["trigger"] == "onTrigger"
    assert bundle["event"]["event_id"] == 11
    assert [row["effect"] for row in bundle["state_changes"]] == ["SET_VAR"]
    assert [row["effect"] for row in bundle["rewards"]] == ["GRANT"]
    assert [row["effect"] for row in bundle["removals"]] == ["REMOVE"]
    assert [row["effect"] for row in bundle["completion"]] == ["COMPLETE"]
    assert [row["effect"] for row in bundle["next_activation"]] == ["START"]
    assert len(bundle["preconditions"]) == 1
    assert len(bundle["runtime_requirements"]) == 1
    assert bundle["correction_targets"] == ["Variables"]
    assert bundle["why_blocked"] == [
        {
            "kind": "persisted_condition",
            "subject": "quest_var:Prog",
            "operator": "EQ",
            "expected": 3,
            "actual": 2,
            "editor": "Variables",
        },
        {
            "kind": "runtime_requirement",
            "subject": "trade:item:1234",
            "operator": "HAS",
            "expected": True,
            "actual": None,
            "editor": None,
        },
    ]


def test_progression_annotation_exposes_primary_and_current_bundles():
    action = _action()
    progression = {
        "available": True,
        "summary": {},
        "sections": [{"section_index": 2, "actions": [action]}],
        "unsectioned_actions": [],
        "current_actions": [action],
        "primary_action": action,
    }

    result = annotate_transition_bundles(progression)

    assert result["primary_bundle"] == action["transition_bundle"]
    assert result["current_bundles"] == [action["transition_bundle"]]
    assert result["summary"]["transition_bundle_count"] == 1
