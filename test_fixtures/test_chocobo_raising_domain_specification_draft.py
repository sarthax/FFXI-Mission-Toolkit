"""Static checks for unexecuted Chocobo Raising staging; no live access."""
import json
from pathlib import Path


def test_chocobo_raising_domain_draft_integrity():
    d=json.loads((Path(__file__).parents[1] / "data/testing/domain_drafts/chocobo_raising.json").read_text(encoding="utf-8"))
    assert d["execution_enabled"] is False and d["integration_status"]=="BLOCKED_SCHEMA_OWNER_REVIEW"
    assert d["source_revision"]["dsp_branch"]=="feature/chocobo-raising-core"
    assert len(d["cases"])==9
    for i,c in enumerate(d["cases"],1):
        assert c["case_id"]==f"CHO-{i:02d}"
        assert c["lane"]=="needs-deploy"
        assert c["additional_gates"] and c["verdict"]=="NOT_RUN" and not c["execution_authorized"]
        assert c["behavior"]["given"] and c["behavior"]["when"] and c["behavior"]["then"]
        assert c["oracle"]["expectation"] and c["oracle"]["source_refs"]
        assert c["readback"]["required"] and c["blocking_gaps"]
        assert len(c["steps"])==4
        for s in c["steps"]:
            assert s["source_refs"] and s["expected"] and s["assertion_ids"] and not s["execution_authorized"]
            assert all(x["commit"]==d["source_revision"]["dsp_commit"] and x["line_start"]>0 for x in s["source_refs"])
