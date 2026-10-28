#!/usr/bin/env python3
import hashlib
import importlib.util
import json
from pathlib import Path

P = Path(__file__).resolve().parents[1] / "tools" / "scenario_native_draft_import_1410.py"
spec = importlib.util.spec_from_file_location("native_draft_1410", P)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

def candidate(steps, path="scenarios/scenario_positive.json", **kw):
    raw = json.dumps(steps).encode()
    return m.preview(raw, source_path=path, source_sha=hashlib.sha256(raw).hexdigest(), **kw)

def rejected(fn):
    try:
        fn()
    except ValueError:
        return
    raise AssertionError("unsafe input was accepted")

def main():
    x = candidate([{"name":"observe","expect":{"zone":235}},
                   {"name":"talk","do":{"talk_npc":17743873},"expect":{"event_active":True}}])
    assert x["status"] == "DRAFT_ONLY" and x["admission"] == "BLOCKED"
    assert x["independent_oracle_verdict"] == "UNKNOWN"
    assert not x["execution_enabled"] and not x["publish_enabled"]
    assert len(x["steps"]) == 2 and all(s["verdict"] == "UNKNOWN" for s in x["steps"])
    a06 = candidate([{"name":"A06 faulty movement","do":{"walk_to":{"x":1,"z":2}},"expect":{"zone":235}}],
                    path="docs/evidence/A06-1-probe/scenario.json", expected_failure=True)
    assert a06["expected_failure_claim"] and any("fault-injection" in b for b in a06["blockers"])
    noapproval = candidate([{"name":"A06 fault case","expect":{"zone":235}}],path="A06/scenario.json")
    assert any("owner review" in b for b in noapproval["blockers"])
    unknown = candidate([{"name":"unrecognized","do":{"warp_to":1},"expect":{"bad_stat":7}}])
    assert len(unknown["blockers"]) >= 3
    for steps in ([], {}, [{"name":"a"},{"name":"a"}], [{"name":"x","do":[],"expect":{}}],
                  [{"name":"x","expect":[] }], [{"name":"x","timeout_ms":True}]):
        rejected(lambda steps=steps: candidate(steps))
    valid = json.dumps([{"name":"normal","expect":{"zone":235}}]).encode()
    rejected(lambda:m.preview(valid,source_path="../escape",source_sha=hashlib.sha256(valid).hexdigest()))
    rejected(lambda:m.preview(valid,source_path="normal.json",source_sha="0"*64))
    rejected(lambda:m.preview(valid,source_path="normal.json",source_sha=hashlib.sha256(valid).hexdigest(),repo_sha="unreviewed"))
    rejected(lambda:m.preview(b"not json",source_path="bad.json",source_sha=hashlib.sha256(b"not json").hexdigest()))
    report = m.inventory([],source_root=Path("."))
    assert report["source_files_examined"] == 0 and report["candidate_previews"] == 0
    print("native draft #1410: positive, negative, A06 and fail-closed tests PASS")

if __name__ == "__main__":
    main()
