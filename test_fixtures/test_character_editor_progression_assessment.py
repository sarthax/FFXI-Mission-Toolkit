from __future__ import annotations

from workbench.editors.character.progression_assessment import assess_progression


def _base(**overrides):
    data = {
        "available": True,
        "diagnosis": "CURRENT",
        "blockers": [],
        "primary_action": {},
        "primary_bundle": {},
        "current_actions": [],
        "current_bundles": [],
        "current_step": {"section_index": 1},
    }
    data.update(overrides)
    return data


def test_progression_assessment_ready_when_persisted_state_allows_primary_action():
    result = assess_progression(_base(
        primary_action={"eligibility": "MATCH"},
        primary_bundle={"eligibility": "MATCH", "runtime_requirements": []},
    ))
    assert result["assessment"]["state"] == "READY"
    assert result["assessment"]["tone"] == "ok"


def test_progression_assessment_distinguishes_runtime_wait_from_persisted_block():
    runtime = assess_progression(_base(
        primary_action={"eligibility": "PARTIAL"},
        primary_bundle={
            "eligibility": "PARTIAL",
            "runtime_requirements": [{"subject": "trade:item:1234"}],
            "why_blocked": [{"kind": "runtime_requirement", "subject": "trade:item:1234"}],
        },
        current_actions=[{"eligibility": "PARTIAL"}],
    ))
    assert runtime["assessment"]["state"] == "WAITING_RUNTIME"
    assert runtime["assessment"]["persisted_blockers"] == 0
    assert runtime["assessment"]["runtime_requirements"] == 1

    blocked = assess_progression(_base(
        blockers=[{
            "subject": "quest_var:Prog",
            "matches": False,
            "editor": "Variables",
        }],
    ))
    assert blocked["assessment"]["state"] == "BLOCKED_PERSISTED"
    assert blocked["assessment"]["correction_targets"] == ["Variables"]


def test_progression_assessment_completed_and_no_modeled_action():
    completed = assess_progression(_base(diagnosis="COMPLETED", current_step=None))
    assert completed["assessment"]["state"] == "COMPLETED"

    stalled = assess_progression(_base(primary_action={}, current_actions=[]))
    assert stalled["assessment"]["state"] == "NO_MODELED_ACTION"


def test_progression_assessment_handles_unavailable_model():
    result = assess_progression({"available": False, "reason": "No exact structural model"})
    assert result["assessment"]["state"] == "UNAVAILABLE"
    assert "No exact structural model" in result["assessment"]["summary"]
