#!/usr/bin/env python3
"""Documentation regression: Phase 8 must remain single and complete."""
from pathlib import Path

def main():
    text=Path("docs/workbench/ROADMAP.md").read_text(encoding="utf-8")
    heading="### Phase 8 — Evidence-aware LLM Research & Agent Layer (P1)"
    assert text.count("### Phase 8") == 1, "ROADMAP.md must contain exactly one Phase 8 section"
    assert text.count(heading) == 1, "canonical Phase 8 heading missing"
    phase=text.split(heading,1)[1].split("## Feature Trace architecture",1)[0]
    required=[
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
    missing=[item for item in required if item not in phase]
    assert not missing,f"Phase 8 missing required roadmap concepts: {missing}"
    print("roadmap Phase 8 consolidation self-test: PASS")

if __name__=="__main__":
    main()
