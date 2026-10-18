"""Standalone Assault zone next-action coverage (no DSP runtime required)."""
from pathlib import Path
from workbench.domains.assault_readiness import assess_all
from workbench.domains.assault_summary import summarize

def run():
    rows = [
        {"number": 1, "zone": "Periqia", "reviews": {}, "issue_crossrefs": [], "shared_dependencies": []},
        {"number": 2, "zone": "Periqia", "reviews": {"implementation": {"state": "validated"}, "port": {"state": "validated"}, "validation": {"state": "pending"}}, "issue_crossrefs": [], "shared_dependencies": []},
        {"number": 3, "zone": "Ilrusi Atoll", "reviews": {"implementation": {"state": "blocked"}}, "issue_crossrefs": [], "shared_dependencies": []},
    ]
    assess_all(rows)
    result = summarize(rows)
    assert result["zones"]["Periqia"]["next_implementation_review"] == 1
    assert result["zones"]["Periqia"]["next_live_test"] == 1
    assert result["zones"]["Ilrusi Atoll"]["next_resolve_blocker"] == 1
    assert result["total"]["next_live_test"] == 1
    assert result["total"]["missions"] == 3
    page = (Path(__file__).resolve().parents[1] / "gui/templates/domain_assault.html").read_text(encoding="utf-8")
    assert 'next_dependency_review' in page
    assert 'next_live_test' in page
    assert 'readiness_zone={{ zone|urlencode }}' in page
    print("Assault zone next-action dashboard: PASS")

if __name__ == "__main__":
    run()
