"""Pure-Python contract checks for Voidwalker validation evidence."""
from workbench.domains.voidwalker_coverage import summarize


def test_missing_evidence_is_not_success():
    rows = [
        {"key": "105:1", "name": "One", "zone_id": 105, "zone": "Batallia_Downs",
         "validation_rec": {"areas": {"pop": "ok", "drops": "untested", "fight": "issue"}}},
        {"key": "105:2", "name": "Two", "zone_id": 105, "zone": "Batallia_Downs",
         "validation_rec": None},
    ]
    result = summarize(rows)
    assert result["spawns"] == 2
    assert result["checks"] == 12
    assert result["area_counts"]["pop"] == {"ok": 1, "issue": 0, "n/a": 0, "untested": 1}
    assert result["untested_checks"] == 10
    assert result["issue_checks"] == 1
    assert result["next_tests"][0]["key"] == "105:1"
    assert result["next_tests"][0]["issues"] == ["fight"]
    assert len(result["zones"]) == 1
    assert result["zones"][0]["untested_checks"] == 10


def test_fully_recorded_and_truncation():
    complete = {"areas": {a: "ok" for a in ("pop", "hint", "fight", "model", "drops", "upgrade")}}
    rows = [{"key": "1:1", "name": "Complete", "zone_id": 1, "zone": "Zone", "validation_rec": complete},
            {"key": "2:2", "name": "Unknown", "zone_id": 2, "zone": "Other",
             "validation_rec": {"areas": {"pop": "bogus"}}}]
    result = summarize(rows, limit=0)
    assert result["untested_checks"] == 6
    assert result["next_tests"] == []
    assert result["next_tests_total"] == 1
    assert result["truncated"] is True


if __name__ == "__main__":
    test_missing_evidence_is_not_success()
    test_fully_recorded_and_truncation()
    print("Voidwalker coverage evidence: PASS")
