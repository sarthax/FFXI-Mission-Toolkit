#!/usr/bin/env python3
"""Unified Workbench UI framework contract."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "gui" / "templates"
ALLOWLIST = ROOT / "docs" / "workbench" / "UI_LEGACY_TEMPLATE_ALLOWLIST.txt"
ARCHETYPES = {"browser", "detail", "workbench", "editor", "dashboard"}


def _allowlisted() -> set[str]:
    names = set()
    for line in ALLOWLIST.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        name, sep, reason = line.partition("|")
        assert sep and reason.strip(), f"legacy template entry needs a reason: {line!r}"
        names.add(name.strip())
    return names


def main() -> None:
    base = (TEMPLATES / "base.html").read_text(encoding="utf-8")
    wrapper = (TEMPLATES / "workbench_page.html").read_text(encoding="utf-8")

    for token in (
        "--wb-page-pad-y", "--wb-page-pad-x", "--wb-section-gap", "--wb-panel-gap",
        "--wb-toolbar-h", "--wb-control-h", "--wb-sidebar-sm", "--wb-sidebar-md",
        "--wb-inspector-w", "--wb-table-row-y",
    ):
        assert token in base, token
    for primitive in (
        ".wb-page-header", ".wb-page-actions", ".wb-filter-row",
        ".wb-layout-one", ".wb-layout-two", ".wb-layout-three",
        ".wb-empty", ".wb-loading", ".wb-error",
    ):
        assert primitive in base, primitive

    assert '{% extends "base.html" %}' in wrapper
    for block in (
        "page_archetype", "page_width", "page_class", "page_heading", "page_subtitle",
        "page_status", "page_actions", "page_help", "page_notices", "page_body",
    ):
        assert f"block {block}" in wrapper, block

    allow = _allowlisted()
    seen_legacy = set()
    adopted = {}
    for path in sorted(TEMPLATES.glob("*.html")):
        if path.name in {"base.html", "workbench_page.html"}:
            continue
        text = path.read_text(encoding="utf-8")
        if '{% extends "workbench_page.html" %}' in text:
            match = re.search(r"{% block page_archetype %}\s*([a-z]+)\s*{% endblock %}", text)
            assert match, f"{path.name}: unified pages must declare page_archetype"
            assert match.group(1) in ARCHETYPES, (path.name, match.group(1))
            assert path.name not in allow, f"{path.name}: migrated page still in legacy allowlist"
            adopted[path.name] = match.group(1)
        elif '{% extends "base.html" %}' in text:
            assert path.name in allow, (
                f"{path.name}: direct base.html page must migrate to workbench_page.html "
                "or be explicitly grandfathered with a reason"
            )
            seen_legacy.add(path.name)

    assert allow == seen_legacy, f"stale/missing legacy entries: allow={allow - seen_legacy}, seen={seen_legacy - allow}"
    assert adopted["sql.html"] == "browser"
    assert adopted["validation_dashboard.html"] == "dashboard"
    assert adopted["research_evidence.html"] == "detail"

    print(f"Unified UI framework contract: PASS ({len(adopted)} adopted, {len(allow)} legacy)")


if __name__ == "__main__":
    main()
