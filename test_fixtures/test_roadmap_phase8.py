#!/usr/bin/env python3
"""Guard the durable/current Workbench roadmap reconciliation."""
from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    current_path = ROOT / "docs" / "workbench" / "ROADMAP_CURRENT.md"
    historical_path = ROOT / "docs" / "workbench" / "ROADMAP.md"
    assert current_path.is_file(), "missing authoritative ROADMAP_CURRENT.md"
    assert historical_path.is_file(), "missing historical ROADMAP.md"

    current = current_path.read_text(encoding="utf-8")
    historical = historical_path.read_text(encoding="utf-8")

    # The current roadmap is capability-oriented and explicitly authoritative.
    assert current.startswith("# Current Workbench Roadmap")
    assert "Authoritative repository: `sarthax/FFXI-Mission-Toolkit`" in current
    assert "Authoritative branch: `main`" in current
    assert "ROADMAP.md` remains the historical implementation ledger" in current

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
    assert "Plain Behavior is the default view" in current
    assert "BEHAVIOR_INSPECTOR_CLOSEOUT.md" in current
    assert "Persistent **client item DAT cache**" in current
    assert "Campaign/session manifest import support" in current
    assert "Progression transition bundles group trigger/event" in current
    assert "Native modern-LSB Nyzul floor-generation adapter remains future work" in current

    # Historical roadmap remains substantial rather than being overwritten by the current snapshot.
    assert len(historical) > 5000
    assert "Phase" in historical

    print("roadmap reconciliation self-test: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
