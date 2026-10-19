"""Normalize imported MOG-09 assertions without inferring uncaptured data."""
from workbench.server_admin.feature_testing.normalized_evidence import (
    normalize_mog09, evaluate_imported_mog09,
)


def sample():
    names = [
        ("session established for expected character", 21836, 21836),
        ("precondition: Safe holds furnishings with nonzero aura (stored, not installed)", ">=1", [216]),
        ("active KI equals oracle for empty layout", 0, 0),
        ("aura breakdown all zero", [0]*8, [0]*8),
        ("client bag equals persisted char_inventory location 0", [[1,42,1]], [[1,42,1]]),
        ("client Mog Safe equals persisted char_inventory location 1", [[7,216,1]], [[7,216,1]]),
    ]
    return {"feature_id":"moghancement", "case_id":"MOG-09", "verdict":"PASS",
            "evidence":{"assertions":[{"name":n,"expected":e,"observed":o,"ok":True} for n,e,o in names],
                        "observations":{"client_key_items":[387],"provenance":{"charid":21836}}}}


def test_all_six_are_recomputed_but_not_independently_authenticated():
    record=sample()
    result=evaluate_imported_mog09(record)
    assert result["evaluation"]["verdict"]=="PASS"
    assert len(result["evaluation"]["assertions"])==6
    assert result["normalization"]["missing_fields"]==[]
    assert result["normalization"]["evidence_authenticated"] is False
    assert "installed_layout" not in result["normalization"]["observations"]
    assert "client_key_items" not in result["normalization"]["observations"]
    assert record["evidence"]["assertions"][0]["name"]=="session established for expected character"


def test_missing_assertion_blocks_without_substitution():
    record=sample()
    record["evidence"]["assertions"].pop()
    result=evaluate_imported_mog09(record)
    assert result["evaluation"]["verdict"]=="BLOCKED"
    assert "client_safe" in result["normalization"]["missing_fields"]
    assert "db_safe" in result["normalization"]["missing_fields"]


def test_reported_pass_is_not_accepted_when_values_mismatch():
    record=sample()
    record["evidence"]["assertions"][2]["observed"]=387
    result=evaluate_imported_mog09(record)
    assert result["recorded_verdict"]=="PASS"
    assert result["evaluation"]["verdict"]=="FAIL"


def test_invalid_case_refused():
    import pytest
    record=sample()
    record["case_id"]="MOG-01"
    with pytest.raises(ValueError):
        normalize_mog09(record)
