"""R5 gardening design draft checks: no execution, invented oracles, or unsafe slot actions."""
from __future__ import annotations

import json
from pathlib import Path


def _draft():
    root = Path(__file__).resolve().parents[1]
    return json.loads((root / "data/testing/domain_drafts/gardening.json").read_text(encoding="utf-8"))


def test_gardening_domain_specification_is_untouched_by_runners():
    data = _draft()
    assert data["execution_enabled"] is False
    assert data["integration_status"] == "BLOCKED_SCHEMA_OWNER_REVIEW"
    assert "NOT importable" in data["canonical_compatibility"]
    assert data["source_revision"]["deployed"] == "UNKNOWN"
    assert [c["case_id"] for c in data["cases"]] == [f"GARD-{i:02d}" for i in range(1, 10)]
    for case in data["cases"]:
        assert case["runner"] == "unassigned"
        assert case["execution_status"] == "design_only"
        assert case["lane"] == case["execution_lane"] == "needs-mutation"
        assert case["verdict"] == "NOT_RUN"
        assert case["mutation"]["enabled"] is False
        assert case["behavior"]["given"] and case["behavior"]["when"] and case["behavior"]["then"]
        assert [step["id"] for step in case["steps"]] == [
            f"{case['case_id']}-S{i:02d}" for i in range(1, 5)
        ]
        ids = {assertion["id"] for assertion in case["assertions"]}
        assert len(ids) == len(case["assertions"])
        for step in case["steps"]:
            assert set(step["assertion_ids"]) <= ids
            assert step["manual_execution_allowed"] is False
            assert step["oracle_refs"]
            assert step["expected"]
        assert case["blocking_gaps"]
        assert case["source_revision"]["deployed"] == "UNKNOWN"
        for oracle in case["oracle_sources"]:
            assert oracle["commit"] == data["source_revision"]["dsp_commit"]
            assert oracle["line_start"] > 0 and oracle["line_end"] >= oracle["line_start"]
            assert oracle["url"].startswith("https://github.com/")


def test_gardening_specification_collision_is_blocked():
    cases = {c["case_id"]: c for c in _draft()["cases"]}
    colliding = cases["GARD-09"]
    assert colliding["kind"] == "negative"
    assert "GARD-GM-01" in " ".join(colliding["blocking_gaps"])
    assert "BOTH safes" in colliding["steps"][1]["expected"]
    assert colliding["mutation"]["enabled"] is False
    assert "GARD-GM-01" in _draft()["capability_matrix"]["guard"]
    for case in cases.values():
        assert any("UNKNOWN" in a["expected"] for a in case["assertions"])
        assert "char_inventory" == case["readback"]["table"]
        assert "extra" in case["readback"]["columns"]
