"""Tracker migration regression: all Topaz comments retained; DSP state independent."""
from pathlib import Path
from workbench.domains.assault_tracker import overview, TRACKER

def test_assault_tracker_full_import():
    data = overview()
    missions = data["missions"]
    assert len(missions) == 50
    assert {m["number"] for m in missions} == set(range(1, 51))
    assert len({(m["zone"], m["rank"]) for m in missions}) == 50
    assert len(data["shared"]) >= 4
    assert any("appraisal" in s["comments"].lower() for s in data["shared"])
    assert any("navmeshes" in s["comments"].lower() for s in data["shared"])
    assert next(m for m in missions if m["number"] == 42)["name"] == "Lamia No.13"
    for mission in missions:
        assert mission["comments"]
        assert mission["dsp_validation"] == "not_verified"
        if mission["number"] % 10 == 0 or (mission["number"] - 1) % 10 >= 4:
            assert mission["dsp_port"] == "pending_review"

def test_assault_domain_ui():
    template = (Path(__file__).resolve().parents[1] / "gui/templates/domain_assault.html").read_text(encoding="utf-8")
    assert 'href="#assault-{{ hit.number }}"' in template
    assert "mission.comments" in template
    assert "section.comments" in template
    assert "dsp_validation" in template
    assert TRACKER.exists()
