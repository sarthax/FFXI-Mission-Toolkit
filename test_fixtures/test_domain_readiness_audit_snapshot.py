"""Static, no-network structural audit of the 73 R5 domain readiness records."""
import json
from pathlib import Path

ROOT=Path(__file__).parents[1]
PATH=ROOT/"docs"/"workbench"/"SCENARIO_DOMAIN_READINESS_MATRIX_2026-10-21.json"


def test_domain_readiness_matrix_synthetic_validation():
    data=json.loads(PATH.read_text(encoding="utf-8"))
    assert data["artifact_type"]=="R5_domain_readiness_audit_not_canonical"
    assert data["execution_enabled"] is False and data["import_allowed"] is False
    assert data["counts"]["domains"]==9 and data["counts"]["cases"]==73
    assert data["counts"]["lanes"]=={
        "needs-mutation":57,"observe-now":5,"needs-readback":2,"needs-deploy":9,
    }
    cases=data["cases"]
    ids=[c["scenario_id"] for c in cases]
    assert len(ids)==len(set(ids))==73
    assert sorted(data["counts"]["read_only_candidates"])==sorted([
        "MOG-09","RG-01","RG-06","VOID-01","VOID-02",
    ])
    assert len(data["issues"])>=9
    issue_ids={x["id"] for x in data["issues"]}
    for c in cases:
        assert c["audited_lane"] in {"observe-now","needs-readback","needs-mutation","needs-deploy"}
        assert c["declared_lane"]==c["audited_lane"]
        assert c["expected_behavior"] and c["source_refs"] and c["blocking_gaps"]
        assert c["source_revision"] and c["verdict"]=="NOT_RUN_IN_THIS_AUDIT"
        assert c["v2_import"]=="BLOCKED_REVIEWED_MAPPER_REQUIRED"
        assert c["permissions"] and set(c["proposed_issues"]).issubset(issue_ids)
        assert all(r["path"] and len(r["commit"])==40 and
                   0<r["line_start"]<=r["line_end"] for r in c["source_refs"])
        if c["audited_lane"]=="needs-deploy":
            assert c["domain"]=="chocobo_raising"
        if c["audited_lane"]=="observe-now":
            assert c["scenario_id"] in data["counts"]["read_only_candidates"]


def test_audit_is_not_an_execution_input():
    d=json.loads(PATH.read_text(encoding="utf-8"))
    assert "specifications" not in d
    assert "runner" not in d
    assert all(c["v2_import"].startswith("BLOCKED") for c in d["cases"])
