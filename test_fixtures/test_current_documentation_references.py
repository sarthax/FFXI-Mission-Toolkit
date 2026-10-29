#!/usr/bin/env python3
"""Documentation navigation smoke test: current guides must exist and be linked.

Only checks explicit, maintained documentation entry points; this is not a
runtime route crawler or a claim that every module help link is tested.
"""
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
GUIDES = [
    "ROADMAP_HELP_SYNC_AUDIT_2026-10-17.md",
    "SYNTH_OPERATOR_GUIDE.md",
    "ASSAULT_TRACKER_OPERATOR_GUIDE.md",
    "RUN_GEO_OPERATOR_GUIDE.md",
    "VOIDWALKER_OPERATOR_GUIDE.md",
    "LIVE_CLIENT_3D_OPERATOR_GUIDE.md",
    "FEATURE_TRACE_OPERATOR_GUIDE.md",
]


def main():
    docs = ROOT / "docs" / "workbench"
    help_text = (ROOT / "gui" / "templates" / "help.html").read_text(encoding="utf-8")
    for name in GUIDES:
        path = docs / name
        assert path.is_file(), f"Missing current operator/audit guide: {path}"
        assert name in help_text, f"Global Help missing current guide: {name}"
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    current = (docs / "ROADMAP_CURRENT.md").read_text(encoding="utf-8")
    # The short current-priorities page links the history/audit pages rather than every guide.
    assert GUIDES[0] in readme
    for linked in ("archive/ROADMAP_CURRENT_PRE_COORDINATOR_RETIREMENT_20261027.md", "ROADMAP.md", "AUDIT_STATUS.md"):
        assert linked in current, f"ROADMAP_CURRENT.md must link {linked}"
    # Check local Markdown links in these curated guides, without following
    # URLs or treating code-formatted source paths as Markdown links.
    for name in GUIDES:
        file = docs / name
        body = file.read_text(encoding="utf-8")
        for dest in re.findall(r"\[[^\]]+\]\(([^)]+)\)", body):
            dest = dest.split("#", 1)[0]
            if not dest or "://" in dest or dest.startswith("/"):
                continue
            assert (file.parent / dest).exists(), f"Broken Markdown link in {name}: {dest}"
    print("current documentation references: PASS")


if __name__ == "__main__":
    main()
