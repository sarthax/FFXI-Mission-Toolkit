#!/usr/bin/env python3
"""Documentation regression: historical Phase 8 and current roadmap inventory stay coherent."""
import re
from pathlib import Path


def main():
    text = Path("docs/workbench/ROADMAP.md").read_text(encoding="utf-8")
    heading = "### Phase 8 — Evidence-aware LLM Research & Agent Layer (P1)"
    assert text.count("### Phase 8") == 1, "ROADMAP.md must contain exactly one Phase 8 section"
    assert text.count(heading) == 1, "canonical Phase 8 heading missing"
    phase = text.split(heading, 1)[1].split("## Feature Trace architecture", 1)[0]
    required = [
        "ResearchSession",
        "Typed Workbench tool registry",
        "Bounded source crawler",
        "Semantic search/indexing",
        "Long-context feature artifact bundles",
        "Research-plan execution",
        "FindingProposal",
        "Permission profiles",
        "Budget/timeout/tool-call limits",
        "no-direct-write guarantees",
    ]
    missing = [item for item in required if item not in phase]
    assert not missing, f"Phase 8 missing required roadmap concepts: {missing}"

    guide = Path("docs/guides/ROADMAP.md").read_text(encoding="utf-8")
    gui = Path("gui/templates/roadmap.html").read_text(encoding="utf-8")
    assert "Current authoritative status — 2026-09-27" in guide
    assert "Remaining core Workbench capabilities" in guide
    assert "Older Toolkit features still not implemented by the rework" in guide
    assert "Current reconciled status" in gui
    assert "Product features outside the recent Workbench scope" in gui
    assert "Unified remaining-feature inventory" in text

    archive = Path("docs/workbench/archive/ROADMAP_CURRENT_PRE_COORDINATOR_RETIREMENT_20261027.md").read_text(encoding="utf-8")
    # The long capability map was archived when the coordinator was retired (2026-10-27); the
    # archive must keep it intact so that history is not lost.
    archive_sections = [
        "Core Workbench architecture",
        "Server environments and runtime context",
        "Character Editor",
        "Feature Trace / Implementation Path",
        "Behavior Inspector / scripted behavior",
        "Mission / quest extraction",
        "Entity / Event / CSID research",
        "Character/client DAT assets and Item Editor",
        "Zone Editor / spatial viewers",
        "Capture ingestion and evidence",
        "Packet / protocol research",
        "Video / OCR / temporal evidence",
        "Research Sessions and wiki/reference evidence",
        "Package / migration / validation",
        "CI / regression safety",
        "Highest-value next work",
    ]
    missing_sections = [name for name in archive_sections if name not in archive]
    assert not missing_sections, f"archived roadmap missing capability families: {missing_sections}"

    reconciled = re.search(
        r"Last fully reconciled against merged PR and branch history: \*\*(\d{4}-\d{2}-\d{2})\*\*",
        archive,
    )
    assert reconciled, "archived roadmap must declare its last full reconciliation date"
    assert reconciled.group(1) >= "2026-10-06", "roadmap reconciliation date regressed before the archive closeout baseline"

    assert "`main` is the product baseline" in archive
    assert "Clarified Flow is the default view" in archive
    assert "BEHAVIOR_INSPECTOR_CLOSEOUT.md" in archive
    assert "Persistent **client item DAT cache**" in archive
    assert "Campaign/session manifest import support" in archive
    assert "Progression transition bundles group trigger/event" in archive
    assert "Native modern-LSB Nyzul adapter parses" in archive
    assert "Evidence-backed contradiction dossiers" in archive
    assert "PR #545 merged evidence-backed lobby/search/map classification" in archive
    assert "Final Phase D source-layout ownership cleanup is complete" in archive
    assert "historical root `settings.py` and `gui_server.py` compatibility surfaces are retired" in archive

    current = Path("docs/workbench/ROADMAP_CURRENT.md").read_text(encoding="utf-8")
    # ROADMAP_CURRENT.md is now the short priorities-and-gates page, not the capability map.
    for heading in (
        "# Mission Toolkit — current roadmap",
        "## Product outcomes — actual work still open",
        "## Recently reconciled backlog",
        "## Working and review rules",
    ):
        assert heading in current, f"ROADMAP_CURRENT.md missing section: {heading}"
    refreshed = re.search(r"\*\*Status refreshed (\d{4}-\d{2}-\d{2})", current)
    assert refreshed, "ROADMAP_CURRENT.md must declare when its status was last refreshed"
    assert refreshed.group(1) >= "2026-10-28", "current roadmap refresh date regressed before the coordinator retirement"
    priorities = re.findall(r"^\| \*\*(P0|P1|Ongoing)\*\* \|", current, re.M)
    assert "P0" in priorities, "current roadmap must list at least one P0 outcome"
    assert "archive/ROADMAP_CURRENT_PRE_COORDINATOR_RETIREMENT_20261027.md" in current, "current roadmap must link the preserved historical roadmap"
    assert "An **open/draft** PR is not merged functionality" in current

    print("roadmap reconciliation self-test: PASS")


if __name__ == "__main__":
    main()
