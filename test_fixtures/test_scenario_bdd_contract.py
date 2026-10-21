"""BDD extension stays declarative, reference-safe, and backward compatible."""
import copy
import json
from pathlib import Path

import pytest

from workbench.server_admin.feature_testing.test_specifications import validate_spec


ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "data" / "testing" / "test_specifications.json"


def cases():
    return {x["case_id"]: x for x in json.loads(CATALOG.read_text(encoding="utf-8"))["specifications"]}


def test_existing_legacy_and_bdd_examples_validate():
    for spec in cases().values():
        assert validate_spec(copy.deepcopy(spec)) == spec


def test_optional_narrative_absent_is_legacy_compatible():
    spec = copy.deepcopy(cases()["MOG-09"])
    for field in ("purpose", "rationale", "behavior", "steps", "authoring"):
        spec.pop(field, None)
    assert validate_spec(spec) == spec


@pytest.mark.parametrize("mutation", [
    lambda s: s["steps"][1].update(id=s["steps"][0]["id"]),
    lambda s: s["steps"][0].update(assertion_ids=["invented_assertion"]),
    lambda s: s["steps"][0].update(evidence_refs=["unobserved_packet"]),
    lambda s: s["behavior"].update(then=[]),
    lambda s: s["authoring"].update(review_required="false"),
    lambda s: s.update(execute_now=True),
])
def test_invalid_bdd_contract_fails_closed(mutation):
    spec = copy.deepcopy(cases()["MOG-09"])
    mutation(spec)
    with pytest.raises(ValueError):
        validate_spec(spec)


def test_bdd_steps_do_not_change_assertion_contract():
    spec = cases()["MOG-09"]
    assert [x["id"] for x in spec["assertions"]] == [
        "expected_character", "safe_contains_furnishing", "empty_layout_ki",
        "zero_aura", "bag_matches_persisted", "safe_matches_persisted",
    ]
    assert [step["assertion_ids"][0] for step in spec["steps"]] == [
        x["id"] for x in spec["assertions"]
    ]
