"""Validate staged Salvage BDD specifications; no gameplay execution."""
import json
from pathlib import Path


def test_salvage_domain_draft_integrity():
    x = json.loads((Path(__file__).parents[1] / "data/testing/domain_drafts/salvage.json").read_text(encoding="utf-8"))
    assert x["execution_enabled"] is False
    assert x["integration_status"] == "BLOCKED_SCHEMA_OWNER_REVIEW"
    assert len(x["cases"]) == 7
    for i, c in enumerate(x["cases"], 1):
        assert c["case_id"] == f"SAL-{i:02d}"
        assert c["verdict"] == "NOT_RUN" and not c["execution_authorized"]
        assert c["lane"] in {"observe-now", "needs-readback", "needs-mutation", "needs-deploy"}
        assert len(c["steps"]) == 4 and c["behavior"]["given"] and c["behavior"]["when"] and c["behavior"]["then"]
        assert c["oracle"]["source_refs"] and c["oracle"]["expectation"]
        assert c["readback"]["required"] and c["blocking_gaps"]
        for s in c["steps"]:
            assert s["source_refs"] and s["expected"] and s["assertion_ids"]
            assert not s["execution_authorized"]
            assert all(v["commit"] == x["source_revision"]["dsp_commit"] and v["line_start"] > 0 for v in s["source_refs"])
