"""Synthetic tests for deterministic declarative assertion evaluation."""
from copy import deepcopy
from workbench.server_admin.feature_testing.test_specifications import specification
from workbench.server_admin.feature_testing.assertion_engine import evaluate


def sample():
    return {"session": 21836, "stored_furnishings": [216],
            "gm_active_ki": 0, "gm_aura": [0]*8,
            "client_bag": [[0, 65535, 10], [1, 12636, 1]],
            "db_bag": [[1, 12636, 1], [0, 65535, 10]],
            "client_safe": [[7, 216, 1]], "db_safe": [[7, 216, 1]],
            "client_key_items": [387]}


def test_mog09_all_six_assertions_evaluate():
    result = evaluate(specification("moghancement", "MOG-09"), sample(),
                      context={"approved_charid": 21836})
    assert result["verdict"] == "PASS"
    assert len(result["assertions"]) == 6
    assert {x["status"] for x in result["assertions"]} == {"PASS"}
    assert result["execution_enabled"] is False


def test_missing_expected_reference_or_observation_never_passes():
    obs = sample()
    obs.pop("db_safe")
    result = evaluate(specification("moghancement", "MOG-09"), obs)
    assert result["verdict"] == "BLOCKED"
    assert sum(x["status"] == "BLOCKED" for x in result["assertions"]) >= 2


def test_mismatch_is_fail_even_if_other_assertions_blocked():
    obs = sample()
    obs["gm_active_ki"] = 387
    obs.pop("db_safe")
    result = evaluate(specification("moghancement", "MOG-09"), obs,
                      context={"approved_charid": 21836})
    assert result["verdict"] == "FAIL"
    assert any(x["status"] == "FAIL" for x in result["assertions"])


def test_duplicate_slots_or_malformed_rows_block_not_pass():
    obs = sample()
    obs["client_bag"] = [[0, 65535, 10], [0, 65535, 10]]
    result = evaluate(specification("moghancement", "MOG-09"), obs,
                      context={"approved_charid": 21836})
    assert next(a for a in result["assertions"] if a["id"] == "bag_matches_persisted")["status"] == "BLOCKED"


def test_design_only_inventory_is_evaluable_but_not_executable():
    obs = sample()
    result = evaluate(specification("inventory_observation", "INV-OBS-01"), obs)
    assert result["verdict"] == "PASS"
    assert result["execution_enabled"] is False
    assert result["source"].startswith("deterministic_evaluation")


def test_boolean_is_not_accepted_as_integer_character_id():
    obs = sample()
    obs["session"] = True
    result = evaluate(specification("moghancement", "MOG-09"), obs,
                      context={"approved_charid": 21836})
    assert result["verdict"] == "BLOCKED"
