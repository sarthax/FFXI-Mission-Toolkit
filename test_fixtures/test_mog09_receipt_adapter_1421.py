import importlib.util
import json
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("mog_adapter", ROOT / "mog09_receipt_adapter_1421.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
def main():
    cases = mod.project_fixture()
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
    with tempfile.TemporaryDirectory() as d:
        assert mod.project_fixture(Path(d)/"missing.json")[0]["verdict"]=="UNKNOWN"
    print("MOG-09 offline six-step prototype: 3 sanitized projections, missing-source refusal PASS")

if __name__=="__main__":
    main()
