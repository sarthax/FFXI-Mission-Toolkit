"""Per-step timeout_ms in native_steps: the rule mirrors XiHeadless ScenarioFileValidation.CheckStructure at the pinned
commit (number, Int32, 0..3600000, any action). Offline only."""
import copy

import pytest

from workbench.server_admin.feature_testing import catalog_view
from workbench.server_admin.feature_testing.typed_action_library import (
    export_native_scenario, review_native_steps, validate_native_steps)


def stored(*steps):
    return {"library_version": 1, "steps": list(steps)}


ACTION_ONLY = {"name": "wait", "do": {"wait_ms": 3000}}
CHECK_ONLY = {"name": "zone", "expect": {"zone": 235}}
BOTH = {"name": "go", "do": {"wait_ms": 3000}, "expect": {"zone": 235}}


@pytest.mark.parametrize("step", [ACTION_ONLY, CHECK_ONLY, BOTH])
@pytest.mark.parametrize("ms", [0, 1, 15000, 3600000])
def test_valid_timeouts_are_accepted_with_every_step_shape(step, ms):
    validate_native_steps(stored({**step, "timeout_ms": ms}))
    assert review_native_steps([{**step, "timeout_ms": ms}])["steps"][0]["step"]["timeout_ms"] == ms


@pytest.mark.parametrize("bad", [-1, 3600001, 2 ** 31, 1.5, 5.0, "5000", None, True, [1], {}])
def test_invalid_timeouts_are_rejected_not_dropped(bad):
    with pytest.raises(ValueError, match="invalid"):
        validate_native_steps(stored({**BOTH, "timeout_ms": bad}))
    assert review_native_steps([{**BOTH, "timeout_ms": bad}])["steps"][0]["status"] == "INVALID"


def test_steps_without_timeout_are_unchanged_and_other_unknown_fields_still_rejected():
    validate_native_steps(stored(ACTION_ONLY, CHECK_ONLY))
    assert "timeout_ms" not in review_native_steps([ACTION_ONLY])["steps"][0]["step"]
    assert review_native_steps([{**BOTH, "timeout": 5}])["steps"][0]["status"] == "UNSUPPORTED"


def test_preview_shows_the_timeout_on_the_check_line():
    lines = catalog_view.native_step_lines(stored({**BOTH, "timeout_ms": 15000}, ACTION_ONLY))
    assert any("(timeout 15000 ms)" in l["text"] for l in lines)
    assert not any("timeout" in l["text"] for l in catalog_view.native_step_lines(stored(BOTH)))


def test_export_passes_timeout_unchanged_and_adds_empty_expect_to_action_only_steps():
    out = export_native_scenario(stored({**ACTION_ONLY, "timeout_ms": 0, "note": "n"}, {**BOTH, "timeout_ms": 3600000}, CHECK_ONLY))
    assert out == [{"name": "wait", "timeout_ms": 0, "do": {"wait_ms": 3000}, "expect": {}},
                   {"name": "go", "timeout_ms": 3600000, "do": {"wait_ms": 3000}, "expect": {"zone": 235}},
                   {"name": "zone", "expect": {"zone": 235}}]


def test_mutation_export_does_not_mutate_input_and_rejects_invalid_value():
    value = stored({**BOTH, "timeout_ms": 5})
    before = copy.deepcopy(value)
    export_native_scenario(value)
    assert value == before
    value["steps"][0]["timeout_ms"] = 3600001  # boundary mutation must fail closed
    with pytest.raises(ValueError):
        export_native_scenario(value)
