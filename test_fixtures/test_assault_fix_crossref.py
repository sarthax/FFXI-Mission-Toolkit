"""Source preservation and conservative fix-log linkage."""
from pathlib import Path
from workbench.domains.assault_tracker import overview
from workbench.domains.assault_fix_crossref import correlate, sections, issue_bullets, FIX_LOG


def test_crossref_all_missions_and_source():
    tracker = overview()
    report = correlate(tracker["missions"], tracker["shared"])
    assert FIX_LOG.stat().st_size > 400000
    assert len(report["sections"]) > 50
    assert len(tracker["missions"]) == 50
    assert all("issue_crossrefs" in m and "fix_log_entries" in m for m in tracker["missions"])
    lamia = next(m for m in tracker["missions"] if m["number"] == 42)
    assert any("Lamia No.13" in item["title"] for item in lamia["fix_log_entries"])
    assert all(i["resolution"] == "requires_review" and not i["dsp_verified"]
               for m in tracker["missions"] for i in m["issue_crossrefs"])


def test_no_false_closure_from_unrelated_fix():
    missions = [{"number": 1, "name": "Sample Mission", "comments": "- Broken door stays closed."}]
    log = [{"id": 1, "title": "Unrelated monster fix", "text": "monster visual corrected"}]
    correlate(missions, [], log_sections=log)
    assert missions[0]["issue_crossrefs"][0]["candidates"] == []
    assert missions[0]["issue_crossrefs"][0]["resolution"] == "requires_review"


def test_issue_bullets_preserve_continuations():
    found = issue_bullets("- First issue\n  follow-up evidence\n- Second issue")
    assert len(found) == 2
    assert "follow-up evidence" in found[0]


def test_crossref_ui_contract():
    template = (Path(__file__).resolve().parents[1] / "gui/templates/domain_assault.html").read_text(encoding="utf-8")
    assert "mission.issue_crossrefs" in template
    assert "candidate.section_id" in template
    assert "tracker.fix_log.sections" in template
    assert "No matching mission fix-log passage" in template
