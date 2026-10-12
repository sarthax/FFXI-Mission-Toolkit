from workbench.editors.character.bounded_progression import build_bounded_progression


def _action(name, score=4, eligibility="MATCH"):
    return {
        "transition_id": name,
        "trigger": "onTrigger",
        "progression": True,
        "progression_score": score,
        "eligibility": eligibility,
        "effects": [{"effect": "SET_VAR", "subject": "quest_var:Prog", "value": 1}],
    }


def _section(index, eligibility="MATCH", actions=None):
    return {
        "section_index": index,
        "eligibility": eligibility,
        "conditions": [],
        "actions": actions or [_action(f"step-{index}")],
        "source_lines": [index * 10, index * 10 + 5],
    }


def test_bounded_projection_limits_default_view_to_previous_current_next():
    sections = [
        _section(0),
        _section(1),
        _section(2),
        _section(3),
        _section(4),
    ]
    progression = {
        "available": True,
        "sections": sections,
        "current_step": sections[2],
    }

    bounded = build_bounded_progression(progression)

    assert [row["relation"] for row in bounded["steps"]] == ["previous", "current", "next"]
    assert [row["section_index"] for row in bounded["steps"]] == [1, 2, 3]
    assert bounded["visible_step_count"] == 3
    assert bounded["max_visible_steps"] == 3
    assert bounded["trace_policy"] == "on_demand"
    assert bounded["trace_scope"] == "selected_step_or_edge"


def test_blocked_alternatives_are_counted_not_expanded():
    sections = [
        _section(0, "BLOCKED"),
        _section(1, "BLOCKED"),
        _section(2, "MATCH"),
        _section(3, "BLOCKED"),
        _section(4, "MATCH"),
        _section(5, "BLOCKED"),
    ]
    progression = {
        "available": True,
        "sections": sections,
        "current_step": sections[2],
    }

    bounded = build_bounded_progression(progression)

    assert bounded["next"]["section_index"] == 4
    assert {row["section_index"] for row in bounded["steps"]} == {1, 2, 4}
    assert bounded["blocked_alternatives"] == 2


def test_projection_prefers_highest_value_progression_action_per_step():
    low = _action("dialogue", score=1)
    high = _action("persistent", score=4)
    section = _section(2, actions=[low, high])
    bounded = build_bounded_progression({
        "available": True,
        "sections": [section],
        "current_step": section,
    })

    assert bounded["current"]["primary_action"]["transition_id"] == "persistent"
    assert bounded["current"]["action_count"] == 2


def test_unavailable_progression_stays_bounded_and_read_only():
    bounded = build_bounded_progression({"available": False, "reason": "no exact model"})
    assert bounded == {
        "available": False,
        "steps": [],
        "blocked_alternatives": 0,
        "trace_policy": "on_demand",
    }


def test_visible_layer_preserves_branching_and_equivalent_routes():
    branch_a = _action("branch-a", score=4)
    branch_b = _action("branch-b", score=4)
    alternate = _action("alternate-same-outcome", score=3)
    section = _section(2, actions=[branch_a, branch_b, alternate])
    bounded = build_bounded_progression({
        "available": True,
        "sections": [section],
        "current_step": section,
    })

    current = bounded["current"]
    assert current["has_alternatives"] is True
    assert current["action_count"] == 3
    assert {row["transition_id"] for row in current["actions"]} == {
        "branch-a", "branch-b", "alternate-same-outcome",
    }
    assert bounded["bound_unit"] == "progression_layers"
    assert bounded["preserves_visible_alternative_routes"] is True
