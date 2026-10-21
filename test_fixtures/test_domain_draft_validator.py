"""Pure synthetic domain-linter regression; never execute staged actions."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
spec = importlib.util.spec_from_file_location("domain_offline", ROOT / "tools/validate_domain_drafts.py")
import sys
validator = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = validator
spec.loader.exec_module(validator)

SHA = "a" * 40
SRC = {"repository": "sarthax/darkstar-to-valhalla",
       "commit": SHA, "path": "scripts/synthetic.lua", "line_start": 1,
       "line_end": 3,
       "url": "https://github.com/sarthax/darkstar-to-valhalla/blob/" +
              SHA + "/scripts/synthetic.lua#L1-L3"}
CASE = {"case_id": "SYN-01", "feature_id": "synthetic", "runner": "unassigned",
        "execution_status": "design_only", "verdict": "NOT_RUN",
        "lane": "needs-readback", "mutation": "none",
        "behavior": {"given": ["UNKNOWN baseline"], "when": ["read only"],
                     "then": ["UNKNOWN pending server observation"]},
        "oracle": {"expectation": "UNKNOWN", "source_refs": [SRC]},
        "readback": {"required": ["synthetic_state"]},
        "steps": [{"id": f"SYN-01-S{i:02d}", "expected": "UNKNOWN",
                   "assertion_ids": [f"SYN-01-a{i}"], "source_refs": [SRC],
                   "execution_authorized": False} for i in range(1, 5)]}
DOC = {"schema_version": 1, "execution_enabled": False,
       "integration_status": "BLOCKED_SCHEMA_OWNER_REVIEW",
       "canonical_target": "data/testing/test_specifications.json",
       "source_revision": {"dsp_commit": SHA, "deployed": "UNKNOWN"},
       "cases": [CASE]}
META = {"cases": 1, "sha": SHA}


def validate(doc):
    return validator.validate_domain("synthetic", doc, META)


def test_synthetic_positive():
    assert validate(deepcopy(DOC)) == [("SYN-01", "needs-readback")]


@pytest.mark.parametrize("kind", [
    "bdd", "source", "steps", "unsafe", "runner", "alias",
    "unknown", "readback", "v2", "deployment"])
def test_synthetic_negative(kind):
    d = deepcopy(DOC)
    c = d["cases"][0]
    if kind == "bdd":
        c["behavior"]["given"] = []
    elif kind == "source":
        c["steps"][0]["source_refs"][0]["commit"] = "b" * 40
    elif kind == "steps":
        c["steps"][1]["id"] = c["steps"][0]["id"]
    elif kind == "unsafe":
        c["execution_authorized"] = True
    elif kind == "runner":
        c["runner"] = "xiheadless_observation_v1"
    elif kind == "alias":
        c["execution_lane"] = "needs-mutation"
    elif kind == "unknown":
        c["oracle"]["expectation"] = "Expected"
        c["behavior"] = {k: ["Expected"] for k in ("given", "when", "then")}
        for s in c["steps"]:
            s["expected"] = "Expected"
    elif kind == "readback":
        c["readback"]["required"] = []
    elif kind == "v2":
        c["contract_v2"] = {"contract_version": 2,
            "step_requirements": [{"step_id": "SYN-01-S02",
                                   "execution_gate": "approved"}]}
    else:
        d["source_revision"]["deployed"] = "YES"
    with pytest.raises(validator.ValidationError):
        validate(d)


def test_gardening_compatibility_alias():
    c = deepcopy(CASE)
    c["lane"] = "needs-mutation"
    c["execution_lane"] = "needs-mutation"
    assert validator.lane_of(c) == "needs-mutation"
    c["execution_lane"] = "needs-readback"
    with pytest.raises(validator.ValidationError):
        validator.lane_of(c)


def test_narrow_observe_now_index():
    m = json.loads((ROOT / "test_fixtures/r6_domain_validation_manifest.synthetic.json").read_text())
    assert m["expected_total"] == 73
    assert m["expected_lanes"] == {
        "observe-now": 5, "needs-readback": 2,
        "needs-mutation": 57, "needs-deploy": 9}
    assert set(m["expected_observe_now"]) == {
        "MOG-09", "VOID-01", "VOID-02", "RG-01", "RG-06"}


# Single case/unit-scale simulation of a pinned PR snapshot (no Git, DSP or network).
def _synthetic_reconciled():
    pr_head = "b" * 40
    entry = {
        "scenario_id": "SYN-01", "domain": "synthetic", "domain_pr": 999,
        "declared_lane": "needs-readback", "audited_lane": "needs-readback",
        "source_revision": SHA, "expected_behavior": "UNKNOWN",
        "source_refs": [{k: SRC[k] for k in
                         ("repository", "commit", "path", "line_start", "line_end")}],
        "runner_state": "unassigned", "verdict": "NOT_RUN_IN_THIS_AUDIT",
        "v2_import": "BLOCKED_REVIEWED_MAPPER_REQUIRED",
        "permissions": ["server_read_grant"],
        "blocking_gaps": ["synthetic readback absent"],
        "readback_missing": ["synthetic_state"]
    }
    matrix = {"artifact_type": "R5_domain_readiness_audit_not_canonical",
              "execution_enabled": False, "import_allowed": False,
              "counts": {"cases": 1, "lanes": {"needs-readback": 1}},
              "source": {"principal_readiness_pr": 1292,
                         "domain_pr_head_snapshot": [{
                             "domain": "synthetic", "pr": 999, "head_sha": pr_head,
                             "source_revision": SHA, "case_count": 1}]},
              "cases": [entry]}
    manifest = {"expected_total": 1, "expected_lanes": {"needs-readback": 1},
                "domains": [{"name": "synthetic", "pr": 999,
                             "sha": SHA, "cases": 1}]}
    return matrix, manifest, {"synthetic": pr_head}


def test_matrix_reconciliation_synthetic_positive(tmp_path):
    (tmp_path / "synthetic.json").write_text(json.dumps(DOC))
    m, manifest, heads = _synthetic_reconciled()
    result = validator.validate_reconciled_matrix(m, manifest, tmp_path, heads)
    assert result["cases"] == 1
    assert result["source_authenticity"] == "NOT_ATTESTED"


@pytest.mark.parametrize("fault,expected_message", [
    ("head", "STALE_SOURCE_PR_HEAD_REAUDIT_REQUIRED"),
    ("lane", "MATRIX_LANE_OR_DOMAIN_DRIFT"),
    ("source", "MATRIX_PINNED_SOURCE_REF_DRIFT"),
    ("oracle", "EXPECTED_TEXT_CHANGED_REAUDIT_REQUIRED"),
    ("import", "imported or promoted"),
    ("permit", "missing readback/permission"),
    ("duplicate", "duplicate, added or missing case IDs"),
    ("pinned", "source PR metadata stale"),
])
def test_matrix_reconciliation_negative(tmp_path, fault, expected_message):
    (tmp_path / "synthetic.json").write_text(json.dumps(DOC))
    matrix, manifest, heads = _synthetic_reconciled()
    entry = matrix["cases"][0]
    if fault == "head":
        heads["synthetic"] = "c" * 40
    elif fault == "lane":
        entry["audited_lane"] = "observe-now"
    elif fault == "source":
        entry["source_refs"][0]["line_start"] = 3
    elif fault == "oracle":
        entry["expected_behavior"] = "PASS proven by code"
    elif fault == "import":
        entry["v2_import"] = "READY"
    elif fault == "permit":
        entry["readback_missing"] = []
    elif fault == "duplicate":
        matrix["cases"].append(deepcopy(entry))
    else:
        matrix["source"]["domain_pr_head_snapshot"][0]["source_revision"] = "d" * 40
    with pytest.raises(validator.ValidationError, match=expected_message):
        validator.validate_reconciled_matrix(matrix, manifest, tmp_path, heads)


def test_duplicate_staged_assertion_ids_do_not_become_v2_oracles():
    doc = deepcopy(DOC)
    doc["cases"][0]["assertions"] = [
        {"id": "SYN-01-a1", "expected": "UNKNOWN"},
        {"id": "SYN-01-a1", "expected": "UNKNOWN"},
    ]
    with pytest.raises(validator.ValidationError, match="duplicate staged assertion ID"):
        validate(doc)
