"""R5 Voidwalker source-cited specification draft completeness and fail-closed tests."""
from __future__ import annotations
import json
from pathlib import Path

def _draft():
    root = Path(__file__).resolve().parents[1]
    return json.loads((root / "data/testing/domain_drafts/voidwalker.json").read_text(encoding="utf-8"))

def test_voidwalker_staging_specification_is_non_executable_and_source_pinned():
    data = _draft()
    assert not data["execution_enabled"]
    assert data["integration_status"] == "BLOCKED_SCHEMA_OWNER_REVIEW"
    assert data["source_revision"]["deployed"] == "UNKNOWN"
    cases = data["cases"]
    assert [x["case_id"] for x in cases] == [f"VWK-{i:02d}" for i in range(1, 8)]
    for c in cases:
        assert c["runner"] == "unassigned"
        assert c["execution_status"] == "design_only"
        assert c["lane"] == "needs-mutation"
        assert c["verdict"] == "NOT_RUN"
        assert not c["mutation"]["enabled"]
        assert c["mutation"]["owner_approval_required"]
        assert c["behavior"]["given"] and c["behavior"]["when"] and c["behavior"]["then"]
        assert [x["id"] for x in c["steps"]] == [f"{c['case_id']}-S{i:02d}" for i in range(1, 5)]
        assertion_ids = {a["id"] for a in c["assertions"]}
        assert len(assertion_ids) == len(c["assertions"])
        for step in c["steps"]:
            assert not step["execution_authorized"]
            assert set(step["assertion_ids"]) <= assertion_ids
            assert step["source_refs"] and step["expected"]
        assert c["blocking_gaps"] and c["oracle_sources"]
        assert any(a["oracle_state"] == "UNKNOWN" for a in c["assertions"])
        for source in c["oracle_sources"]:
            assert source["commit"] == data["source_revision"]["dsp_commit"]
            assert source["line_start"] > 0
            assert source["line_end"] >= source["line_start"]

def test_voidwalker_probabilistic_upgrade_and_cooldown_claims_are_guarded():
    cases = {c["case_id"]: c for c in _draft()["cases"]}
    assert "RNG" in cases["VWK-01"]["steps"][1]["expected"]
    assert "another candidate can still pop" in cases["VWK-05"]["steps"][1]["expected"]
    assert "zoning cleanup remains UNKNOWN" in cases["VWK-06"]["steps"][1]["expected"]
    assert "skill" in cases["VWK-07"]["name"].lower()
    assert all(not c["mutation"]["enabled"] for c in cases.values())
