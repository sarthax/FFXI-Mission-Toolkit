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

    current = Path("docs/workbench/ROADMAP_CURRENT.md").read_text(encoding="utf-8")
    # ROADMAP_CURRENT is a durable capability map, not the historical per-PR ledger. Assert the
    # current product families rather than headings from the superseded October-1 snapshot.
    current_sections = [
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
    missing_sections = [name for name in current_sections if name not in current]
    assert not missing_sections, f"ROADMAP_CURRENT.md missing current capability families: {missing_sections}"

    reconciled = re.search(
        r"Last fully reconciled against merged PR and branch history: \*\*(\d{4}-\d{2}-\d{2})\*\*",
        current,
    )
    assert reconciled, "ROADMAP_CURRENT.md must declare its last full reconciliation date"
    assert reconciled.group(1) >= "2026-10-03", "roadmap reconciliation date regressed before the current baseline"

    assert "`main` is the product baseline" in current
    assert "Clarified Flow is the default view" in current
    assert "BEHAVIOR_INSPECTOR_CLOSEOUT.md" in current
    assert "Persistent **client item DAT cache**" in current
    assert "Campaign/session manifest import support" in current
    assert "Progression transition bundles group trigger/event" in current
    assert "Native modern-LSB Nyzul floor-generation adapter remains future work" in current

    print("roadmap reconciliation self-test: PASS")


if __name__ == "__main__":
    main()
