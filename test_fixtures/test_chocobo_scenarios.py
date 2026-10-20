import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SC = ROOT / "docs/workbench/chocobo_audit/TEST_SCENARIOS.json"


def test_scenarios_wellformed_and_untested_without_evidence():
    data = json.loads(SC.read_text(encoding="utf-8"))
    ids = [s["id"] for s in data["scenarios"]]
    assert len(ids) == len(set(ids)) and ids
    for s in data["scenarios"]:
        assert s["state"] in {"untested", "passed", "failed"}
        if s["state"] == "passed":
            assert any(e.split(":")[0] in {"test", "runtime", "capture"} for e in s["evidence"])
