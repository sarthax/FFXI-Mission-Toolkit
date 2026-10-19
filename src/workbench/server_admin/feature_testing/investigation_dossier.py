"""Read-only hypothesis dossier for one imported test run.

Search terms are derived from assertion identifiers, never model-provided paths,
SQL, commands, or arbitrary repository-wide prompts. Search hits are candidates,
not verified explanations of a runtime result.
"""
from __future__ import annotations

import re
from .failure_diagnostics import failure_summary
from .source_diagnostics import search_source

_SAFE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{2,63}$")
_STOP = {"expected", "observed", "result", "failure", "assertion", "status", "false", "true", "unknown"}


def investigation_dossier(records: list[dict], *, repository: str = "dsp") -> dict:
    if repository not in ("dsp", "headless", "toolkit"):
        raise ValueError("invalid research repository")
    if not records or len(records) > 25:
        raise ValueError("expected 1..25 imported records")
    run_ids = {row.get("run_id") for row in records}
    if len(run_ids) != 1:
        raise ValueError("dossier requires one exact run")
    summaries = [failure_summary(row) for row in records]
    failures = [s for s in summaries if s]
    terms = []
    for result in failures:
        for item in result["assertions"]:
            label = item["id"].strip('"')
            if _SAFE.fullmatch(label) and label.lower() not in _STOP and label not in terms:
                terms.append(label)
            if len(terms) >= 3:
                break
    evidence = []
    for term in terms[:3]:
        result = search_source(repository, term)
        evidence.append({"assertion_term": term, "repository": repository,
                         "configured": result["configured"],
                         "source_revision": result.get("source_revision", "unavailable"),
                         "matches": result["matches"][:8],
                         "truncated": result.get("truncated", False)})
    return {"run_id": records[0]["run_id"], "record_count": len(records),
            "problem_records": failures[:25], "searches": evidence,
            "hypotheses": [],
            "missing_evidence": (
                ["No failed or malformed assertion evidence found; no failure diagnosis can be made."]
                if not failures else
                ["Source snippets are unverified candidates; confirm DSP and XiHeadless checkout revisions.",
                 "No independent server-state or packet-level causal validation performed."]
            ),
            "next_validation": "Reproduce with a disposable character; compare pre/post server state and client observations against the specific assertion.",
            "conclusion": "No causal conclusion established by this read-only dossier.",
            "execution_enabled": False,
            "source": "imported_evidence_not_independently_authenticated"}
