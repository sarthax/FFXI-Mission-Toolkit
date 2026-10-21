"""Offline synthetic index validator, not gameplay evidence."""
import json
from pathlib import Path

def test_r5_readiness_index_integrity():
    x=json.loads((Path(__file__).parents[1]/"test_fixtures/r5_domain_readiness_audit_index.synthetic.json").read_text(encoding="utf-8"))
    a=x["case_index"]
    assert not x["execution_enabled"] and len(a)==73
    assert len(set(t["id"] for t in a))==73
    assert len(x["domains"])==9 and sum(t["n"] for t in x["domains"])==73
    assert all(t["steps"]==4 and t["verdict"].startswith("NOT_RUN") for t in a)
    assert {t["lane"] for t in a}<={"observe-now","needs-readback","needs-mutation","needs-deploy"}
    assert sum(t["lane"]=="observe-now" for t in a)==5
