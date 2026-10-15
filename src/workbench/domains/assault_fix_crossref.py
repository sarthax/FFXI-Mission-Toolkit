"""Conservative cross-reference of Assault issues to chronological Topaz fix-log sections.

Matches are leads, not proof of a fix; never auto-close a finding.
"""
from __future__ import annotations
import re
from pathlib import Path

FIX_LOG = Path(__file__).resolve().parents[3] / "data" / "assault" / "Assault_Fix_Log_topaz_release.md"
HEAD = re.compile(r"^(#{2,4})\s+(.+)$", re.M)
NUMBER = re.compile(r"\bmission\s*#?\s*(\d{1,2})\b", re.I)
BULLET = re.compile(r"(?m)^\s*[-*]\s+(?=[^\n])")
STOP = {"assault", "mission", "real", "fixed", "issue", "topaz", "client",
        "the", "and", "for", "with", "from", "this", "that", "into",
        "not", "was", "are", "have", "has", "zone", "npc", "mob"}
TOK = re.compile(r"[a-zA-Z][a-zA-Z0-9]{3,}")


def _words(s):
    return {t.casefold() for t in TOK.findall(s) if t.casefold() not in STOP}


def sections():
    source = FIX_LOG.read_text(encoding="utf-8")
    headings = list(HEAD.finditer(source))
    output = []
    for i, h in enumerate(headings):
        start = h.end()
        end = headings[i + 1].start() if i + 1 < len(headings) else len(source)
        output.append({"id": i + 1, "title": h.group(2).strip(),
                       "level": len(h.group(1)), "text": source[start:end].strip()})
    return output


def issue_bullets(comments):
    """Keep complete issue paragraphs, including indented continuation lines."""
    parts = BULLET.split(comments)
    if not len(parts) > 1:
        return []
    return [p.strip() for p in parts[1:] if p.strip()]


def correlate(missions, shared, *, log_sections=None):
    log = log_sections if log_sections is not None else sections()
    for mission in missions:
        name_words = _words(mission["name"])
        mission_number = mission["number"]
        relevant = []
        for entry in log:
            heading = entry["title"]
            explicit = {int(n) for n in NUMBER.findall(heading)}
            title_tokens = _words(heading)
            if (mission_number in explicit or
                    (not explicit and len(name_words) >= 2 and name_words <= title_tokens)):
                relevant.append(entry)
        mission["fix_log_entries"] = relevant
        mission["issue_crossrefs"] = []
        for number, bullet in enumerate(issue_bullets(mission["comments"]), 1):
            keywords = _words(bullet)
            # Only refer to an actual matched mission section. A generic word
            # overlap is a candidate for review, never proof that issue was fixed.
            candidates = []
            for entry in relevant:
                shared_words = keywords & _words(entry["title"] + " " + entry["text"])
                if len(shared_words) >= 2:
                    candidates.append({"section_id": entry["id"],
                                       "title": entry["title"],
                                       "matching_terms": sorted(shared_words)[:8],
                                       "assessment": "possible_related_fix"})
            mission["issue_crossrefs"].append({
                "id": number, "text": bullet, "candidates": candidates[:8],
                "resolution": "requires_review",
                "dsp_verified": False})
    # System-wide notes deliberately link by titled topic rather than
    # treating a mission heading as evidence for global infrastructure.
    for item in shared:
        words = _words(item["title"])
        item["fix_log_entries"] = [
            entry for entry in log if len(words & _words(entry["title"])) >= 2
        ][:30]
    return {"sections": log, "missions": missions, "shared": shared,
            "note": "Fix-log entries are historical Topaz evidence; no automatic closure or DSP validation."}
