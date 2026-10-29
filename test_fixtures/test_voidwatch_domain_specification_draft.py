"""Static contract assertions for offline, design-only Voidwatch draft; no runtime runner."""
import json
from pathlib import Path


def test_voidwatch_domain_draft_integrity():
    d = json.loads((Path(__file__).parents[1] / "data/testing/domain_drafts/voidwatch.json").read_text(encoding="utf-8"))
    assert d["execution_enabled"] is False
    assert d["integration_status"] == "BLOCKED_SCHEMA_OWNER_REVIEW"
    assert len(d["cases"]) == 8
    ids = [c["case_id"] for c in d["cases"]]
    assert ids == [f"VOID-{i:02}" for i in range(1, 9)]
    for c in d["cases"]:
        assert c["verdict"] == "NOT_RUN" and not c["execution_authorized"]
        assert c["lane"] in {"observe-now","needs-readback","needs-mutation","needs-deploy"}
        assert c["behavior"]["given"] and c["behavior"]["when"] and c["behavior"]["then"]
        assert c["oracle"]["expectation"] and c["oracle"]["source_refs"]
        assert c["readback"]["required"] and c["blocking_gaps"]
        assert len(c["steps"]) == 4
        for step in c["steps"]:
            assert not step["execution_authorized"]
            assert step["expected"] and step["source_refs"] and step["assertion_ids"]
            for source in step["source_refs"]:
                assert source["commit"] == d["source_revision"]["dsp_commit"]
                assert 0 < source["line_start"] <= source["line_end"]
