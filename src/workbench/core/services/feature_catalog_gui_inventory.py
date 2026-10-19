"""Conservative static GUI control discovery, for documentation triage only.

No route invocation, browser execution or inferred runtime acceptance.
"""
from __future__ import annotations
import html
import re
from pathlib import Path
from workbench.core.services.feature_catalog import ROOT
from workbench.core.services.feature_catalog_gui_audit import SAMPLES

TAG = re.compile(r"<(button|form|a|summary)\b([^>]*)>(.*?)</\1>|<form\b([^>]*)>", re.I | re.S)
ATTR = re.compile(r"""([\w-]+)\s*=\s*["']([^"']*)["']""")
STRIP = re.compile(r"<[^>]*>|\{%.*?%\}|\{\{.*?\}\}", re.S)
SPACES = re.compile(r"\s+")
MAX_CONTROLS_PER_PAGE = 200

def _clean(value: str) -> str:
    return SPACES.sub(" ", html.unescape(STRIP.sub(" ", value))).strip()[:100]

def discover_controls(source: str) -> list[dict]:
    """Discover literal control candidates; template-generated controls remain incomplete."""
    rows, seen = [], set()
    for match in TAG.finditer(source):
        tag = match.group(1) or "form"
        attrs = dict(ATTR.findall(match.group(2) or match.group(4) or ""))
        label = _clean(match.group(3) or attrs.get("aria-label", "") or attrs.get("title", ""))
        target = attrs.get("href", "") if tag == "a" else attrs.get("action", "")
        if tag == "a" and (not target.startswith("/") or "{{" in target):
            continue
        if tag == "form" and not target.startswith("/"):
            continue
        if tag in ("button", "summary") and not label:
            continue
        if not label and not target:
            continue
        key = (tag, label, target)
        if key in seen:
            continue
        seen.add(key)
        rows.append({"kind":tag, "label":label, "target":target})
        if len(rows) >= MAX_CONTROLS_PER_PAGE:
            break
    return rows

def inventory_gui(root: Path = ROOT) -> dict:
    pages = []
    for module, relative, samples in SAMPLES:
        path = root / relative
        source = path.read_text(encoding="utf-8") if path.is_file() else ""
        controls = discover_controls(source)
        pages.append({"module":module, "template":relative, "controls":controls,
                      "count":len(controls), "curated_markers":len(samples),
                      "truncated":len(controls)>=MAX_CONTROLS_PER_PAGE})
    return {"pages":pages, "control_count":sum(p["count"] for p in pages),
            "note":"Static candidate inventory only. Candidate controls are not automatically classified as undocumented; dynamic Jinja controls and handlers require manual review."}
