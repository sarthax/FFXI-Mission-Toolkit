"""Static safety and provenance tests for the Moghancement R5 staging catalog."""
from __future__ import annotations
import json
from pathlib import Path

def _draft():
    return json.loads((Path(__file__).resolve().parents[1] / "data/testing/domain_drafts/moghancement.json").read_text(encoding="utf-8"))

def test_moghancement_r5_design_staging_and_existing_runner_is_preserved():
    data = _draft()
    assert data["execution_enabled"] is False
    assert data["integration_status"] == "BLOCKED_SCHEMA_OWNER_REVIEW"
    assert data["source_revision"]["deployed"] == "UNKNOWN"
    assert "MOG-09 (verified_runner)" in data["existing_runner"]
    cases = data["cases"]
    assert [x["case_id"] for x in cases] == [f"MOG-{n:02d}" for n in range(1, 15)]
    for case in cases:
        assert case["execution_status"] == "design_only"
        assert case["runner"] == "unassigned"
        assert case["verdict"] == "NOT_RUN_IN_THIS_DOMAIN_EXPANSION"
        assert not case["mutation"]["enabled"]
        assert case["steps"] and len(case["steps"]) == 4
        ids = {a["id"] for a in case["assertions"]}
        assert len(ids) == 4
        assert [s["id"] for s in case["steps"]] == [f"{case['case_id']}-S{i:02d}" for i in range(1, 5)]
        assert all(not s["execution_authorized"] and s["oracle_refs"] and
                   set(s["assertion_ids"]) <= ids for s in case["steps"])
        assert case["behavior"]["given"] and case["behavior"]["when"] and case["behavior"]["then"]
        assert case["oracle_sources"]
        assert all(s["commit"] == data["source_revision"]["dsp_commit"] for s in case["oracle_sources"])
        assert any(a["oracle_status"].startswith("UNKNOWN") for a in case["assertions"])
        assert case["readback"]["missing"]
        assert case["toolkit_oracle"]["limitation"].startswith("Predicts server")

def test_mog_staging_keeps_narrow_mog09_and_blocks_gm_mutation():
    cases = {case["case_id"]: case for case in _draft()["cases"]}
    assert cases["MOG-09"]["lane"] == "observe-now"
    assert "xiheadless_observation_v1" in cases["MOG-09"]["legacy_canonical_runner"]
    assert "assumption" in cases["MOG-09"]["behavior"]["then"][0]
    assert "first" in cases["MOG-14"]["behavior"]["then"][0]
    assert "outside isFurnitureKeyItem" in cases["MOG-12"]["behavior"]["then"][0]
    assert all(not case["mutation"]["enabled"] for case in cases.values())
