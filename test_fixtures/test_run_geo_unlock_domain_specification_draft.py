"""Validate offline staged RUN/GEO unlock quest specifications."""
import json
from pathlib import Path


def test_run_geo_unlock_domain_draft_integrity():
    d=json.loads((Path(__file__).parents[1] / "data/testing/domain_drafts/run_geo_unlock.json").read_text(encoding="utf-8"))
    assert d["execution_enabled"] is False and d["integration_status"]=="BLOCKED_SCHEMA_OWNER_REVIEW"
    assert len(d["cases"])==8
    for i,c in enumerate(d["cases"],1):
        assert c["case_id"]==f"RG-{i:02d}"
        assert c["verdict"]=="NOT_RUN" and not c["execution_authorized"]
        assert c["lane"] in {"observe-now","needs-readback","needs-mutation","needs-deploy"}
        assert c["behavior"]["given"] and c["behavior"]["when"] and c["behavior"]["then"]
        assert c["oracle"]["expectation"] and c["oracle"]["source_refs"]
        assert c["readback"]["required"] and c["blocking_gaps"] and len(c["steps"])==4
        for s in c["steps"]:
            assert not s["execution_authorized"] and s["source_refs"] and s["expected"]
            assert all(x["commit"]==d["source_revision"]["dsp_commit"] and x["line_start"]>0 for x in s["source_refs"])
