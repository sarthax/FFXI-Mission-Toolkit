import importlib.util
import json
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("mog_adapter", ROOT / "mog09_receipt_adapter_1421.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
def main():
    data = mod.INPUT.read_text(encoding="utf-8")
    for forbidden in ("21833", "21836"):
        assert forbidden not in data
    cases = mod.project_fixture()
    assert all(forbidden not in json.dumps(c) for c in cases for forbidden in ("21833", "21836"))
    assert len(cases) == 3
    by = {c["sample_id"]: c for c in cases}
    bad = by["fail_obs-20261021T025326Z"]
    assert bad["runner_reported_verdict"] == "FAIL"
    assert len(bad["steps"]) == 6
    assert [s["runner_reported_ok"] for s in bad["steps"]] == [True]*4+[False,False]
    assert bad["task_lifecycle"] == "COMPLETED" and bad["verdict"] == "UNKNOWN"
    assert bad["observations"]["persisted_row_count"] == 0 and bad["observations"]["persistence_polls"] == 4
    assert [(s["expected"]["row_count"], s["observed"]["row_count"]) for s in bad["steps"][4:]] == [(0,8),(0,1)]
    for sample_id, bag_n, safe_n in (("pass_obs-20261019T065856Z",9,18),
                                      ("pass_obs-20261021T040036Z",8,1)):
        case = by[sample_id]
        assert case["runner_reported_verdict"] == "PASS"
        assert case["task_lifecycle"] is None
        assert len(case["steps"]) == 6 and all(s["runner_reported_ok"] is True for s in case["steps"])
        assert case["steps"][4]["expected"]["row_count"] == bag_n
        assert case["steps"][4]["observed"]["row_count"] == bag_n
        assert case["steps"][5]["expected"]["row_count"] == safe_n
        assert case["steps"][5]["observed"]["row_count"] == safe_n
    for case in cases:
        assert case["verdict"] == "UNKNOWN"
        assert case["independent_oracle"] == "NOT_ESTABLISHED"
        assert case["spec_revision"] is None
        assert case["source_integrity"] == "NOT_ESTABLISHED"
        assert all(s["source_pointer"].endswith(str(n)) for n,s in enumerate(case["steps"]))
        assert all(s["independent_oracle"] == "NOT_ESTABLISHED" for s in case["steps"])
    assert mod.project(None)["verdict"] == "UNKNOWN"
    assert mod.project({})["verdict"] == "UNKNOWN"
    for broken in ({"assertions":[None]*6}, {"assertions":[{}]*6},
                   {"assertions":[{"name":"x","runner_ok":True}]*6},
                   {"assertions":[{"name":"x","runner_ok":True}]*6,"source_path":"../unsafe"}):
        outcome=mod.project(broken)
        assert outcome["verdict"]=="UNKNOWN" and outcome["steps"]==[]
        assert "None#" not in json.dumps(outcome)
    with tempfile.TemporaryDirectory() as d:
        for raw in ("[]", "null", "{\"status\":\"DERIVED_FROM_UNREVIEWED_1420_SANITIZED_REPORTS\",\"cases\":null}",
                    "{\"status\":\"DERIVED_FROM_UNREVIEWED_1420_SANITIZED_REPORTS\",\"cases\":[null]}"):
            path=Path(d)/"malformed.json";path.write_text(raw)
            outcome=mod.project_fixture(path)
            assert outcome[0]["verdict"]=="UNKNOWN" and outcome[0]["steps"]==[]
    with tempfile.TemporaryDirectory() as d:
        assert mod.project_fixture(Path(d)/"missing.json")[0]["verdict"]=="UNKNOWN"
    print("MOG-09 offline six-step prototype: 3 sanitized projections, missing-source refusal PASS")

if __name__=="__main__":
    main()
