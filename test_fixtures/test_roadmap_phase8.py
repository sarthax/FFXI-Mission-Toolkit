#!/usr/bin/env python3
"""Documentation regression: historical Phase 8 and current roadmap inventory stay coherent."""
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

    current = Path("docs/workbench/ROADMAP_CURRENT.md").read_text(encoding="utf-8")
    current_sections = [
        "Core Workbench architecture, evidence model and source adapters",
        "Feature Trace, Implementation Path and implementation discovery",
        "Mission / quest extraction and dependency closure",
        "Generic scripted behavior / Behavior Inspector",
        "Acquisition / obtainability / crafting closure",
        "Capture ingestion, integrity and provenance",
        "Capture graph linkage, correlation and Evidence Search",
        "Video OCR, screenshots and capture/video evidence alignment",
        "PCAP/network/lobby protocol research",
        "Client snapshots, DAT inspection, item editing and client migration",
        "Research Sessions and evidence-aware research",
        "Wiki/reference evidence",
        "Packages, migration and validation",
        "Zone Editor, spatial viewers and development workspaces",
        "Packet tools",
        "Named domains / system workspaces",
        "Shared shell, navigation and UX",
        "Superseded / deprecated history intentionally excluded",
    ]
    missing_sections = [name for name in current_sections if name not in current]
    assert not missing_sections, f"ROADMAP_CURRENT.md missing capability families: {missing_sections}"
    for pr in ("PR #74", "PR #85", "PR #103", "PR #125", "PR #154", "PR #180", "PR #183"):
        assert pr in current, f"ROADMAP_CURRENT.md must document superseded history boundary for {pr}"
    assert "merged `main`" in current
    assert "Search/cache TCP decoder" in current
    assert "Generalized new-item DAT allocation/injection" in current
    assert "Salvage reconstruction compiler path" in current

    print("roadmap reconciliation self-test: PASS")


if __name__ == "__main__":
    main()
