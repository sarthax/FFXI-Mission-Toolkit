"""Check R5 missions/quests design for source and safety constraints."""
from __future__ import annotations
import json
from pathlib import Path

def _draft():
    return json.loads((Path(__file__).resolve().parents[1] / "data/testing/domain_drafts/missions_quests.json").read_text(encoding="utf-8"))

def test_mq_design_cases_non_executable_and_source_pinned():
    d = _draft()
    assert not d["execution_enabled"]
    assert d["integration_status"] == "BLOCKED_SCHEMA_OWNER_REVIEW"
    assert [x["case_id"] for x in d["cases"]] == [f"MQ-{n:02d}" for n in range(1, 6)]
    for c in d["cases"]:
        assert c["runner"] == "unassigned" and c["execution_status"] == "design_only"
        assert c["verdict"] == "NOT_RUN" and not c["mutation"]["enabled"]
        assert c["lane"] == "needs-mutation"
        assert [s["id"] for s in c["steps"]] == [f"{c['case_id']}-S{n:02d}" for n in range(1, 5)]
        assertion_ids = {a["id"] for a in c["assertions"]}
        assert len(assertion_ids) == 4
        assert all(not s["execution_authorized"] and s["oracle_sources"] and
                   set(s["assertion_ids"]) <= assertion_ids for s in c["steps"])
        assert any(a["oracle_status"] == "UNKNOWN" for a in c["assertions"])
        assert c["oracle_sources"]
        assert all(o["commit"] == d["source_revision"]["dsp_commit"] for o in c["oracle_sources"])
        assert c["blocking_gaps"]

def test_repeat_reward_claim_not_falsely_assumed_safe():
    c = _draft()["cases"][-1]
    assert c["case_id"] == "MQ-05"
    assert "possible" in c["behavior"]["then"][0]
    assert "including completed" in c["behavior"]["then"][0]
    assert c["verdict"] == "NOT_RUN"
