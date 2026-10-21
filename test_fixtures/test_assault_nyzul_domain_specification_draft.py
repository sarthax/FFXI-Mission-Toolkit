"""R5 Assault/Nyzul staging specifications never authorize instance or GM actions."""
from __future__ import annotations
import json
from pathlib import Path

def _draft():
    return json.loads((Path(__file__).resolve().parents[1] / "data/testing/domain_drafts/assault_nyzul.json").read_text(encoding="utf-8"))

def test_assault_nyzul_design_cases_have_bound_steps_and_source():
    d = _draft()
    assert d["execution_enabled"] is False
    assert d["integration_status"] == "BLOCKED_SCHEMA_OWNER_REVIEW"
    assert d["source_revision"]["deployed"] == "UNKNOWN"
    ids = [c["case_id"] for c in d["cases"]]
    assert ids == ["ASLT-01", "ASLT-02", "ASLT-03", "ASLT-04", "NYZ-01", "NYZ-02"]
    for c in d["cases"]:
        assert c["execution_status"] == "design_only"
        assert c["runner"] == "unassigned"
        assert c["lane"] == "needs-mutation"
        assert c["verdict"] == "NOT_RUN"
        assert not c["mutation"]["enabled"]
        assert [s["id"] for s in c["steps"]] == [f"{c['case_id']}-S{i:02d}" for i in range(1, 5)]
        ids = {a["id"] for a in c["assertions"]}
        assert len(ids) == len(c["assertions"])
        for step in c["steps"]:
            assert not step["execution_authorized"]
            assert set(step["assertion_ids"]) <= ids
            assert step["expected"] and step["source_refs"]
        assert c["behavior"]["then"] and c["blocking_gaps"]
        assert any(a["oracle_status"] == "UNKNOWN" for a in c["assertions"])
        for src in c["oracle_sources"]:
            assert src["commit"] == d["source_revision"]["dsp_commit"]

def test_nyzul_debug_helpers_are_not_gameplay_oracles():
    c = {case["case_id"]: case for case in _draft()["cases"]}
    assert "GM warpassault bypasses" in c["ASLT-01"]["steps"][1]["expected"]
    assert "forces progress=15" in c["NYZ-01"]["steps"][1]["expected"]
    assert "outside 1..100 rejected" in c["NYZ-02"]["steps"][1]["expected"]
    assert all("Debug complete" in x["mutation"]["guard"] for x in c.values())
