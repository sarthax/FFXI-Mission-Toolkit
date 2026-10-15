"""Progress counts cannot silently treat missing reviews as passed or broken."""
from workbench.domains.assault_summary import summarize

def test_summary_by_zone_and_independent_review_stages():
    missions = [
        {"zone": "Periqia", "reviews": {"port": {"state": "validated"}},
         "issue_crossrefs": [
             {"reviews": {"topaz": {"state": "fixed", "evidence": "log"},
                          "dsp_port": {"state": "fixed", "evidence": "PR"},
                          "dsp_validation": {"state": "fixed", "evidence": "capture"}}},
             {"reviews": {"topaz": None, "dsp_port": {"state": "blocked"}, "dsp_validation": None}},
         ]},
        {"zone": "Ilrusi Atoll", "reviews": {}, "issue_crossrefs": [
            {"reviews": {"topaz": None, "dsp_port": None, "dsp_validation": None}}
        ]}
    ]
    result = summarize(missions)
    assert result["total"]["missions"] == 2
    assert result["total"]["issues"] == 3
    assert result["total"]["mission_port_validated"] == 1
    assert result["total"]["mission_validation_unreviewed"] == 2
    assert result["total"]["fully_reviewed_issues"] == 1
    assert result["total"]["remaining_issue_reviews"] == 2
    assert result["total"]["blocked_issues"] == 1
    assert result["zones"]["Ilrusi Atoll"]["issue_dsp_port_unreviewed"] == 1

def test_progress_ui():
    from pathlib import Path
    page=(Path(__file__).resolve().parents[1]/"gui/templates/domain_assault.html").read_text(encoding="utf-8")
    assert "Development progress" in page
    assert "tracker.progress.zones[zone]" in page
    assert page.index("Development progress") < page.index('class="assault-table-scroll"')
