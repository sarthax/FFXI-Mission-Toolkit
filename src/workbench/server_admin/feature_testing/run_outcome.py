"""#1408: a plain-language account of what one stored result does and does not say.

Pure and read-only. It looks at a result record the importer already stored (and, when there is one, the runner job
row for the same run) and states, in words, the verdict, why a BLOCKED or UNKNOWN result is that way, how much
structured evidence backs it, and the runner job's progress as a separate fact. It never decides a verdict, never
promotes a record, and never invents a cause: a missing reason stays "no reason recorded".
"""
from __future__ import annotations

from .results import UNCLASSIFIED, reason_class

_MAX_NOTE = 300
_REASONS = {
    "ENVIRONMENT": "the test environment was not available",
    "FIXTURE_ABSENT": "a required fixture was not present",
    "ORACLE_UNKNOWN": "there is no established way to decide pass or fail",
    "OTHER": "another cause, described in the note if one was recorded",
    UNCLASSIFIED: "no reason was recorded for this result",
}
_MEANING = {
    "PASS": "The imported checks were satisfied. This is what the report says; nothing independent has confirmed it.",
    "FAIL": "At least one imported check did not match its expectation.",
    "BLOCKED": "The run could not be carried out, so no determination about the behavior was made.",
    "UNKNOWN": "No determination was reached. This is not a pass and not a failure.",
    "SKIPPED": "The run was skipped. Nothing was checked.",
}
_JOB_MEANING = {
    "QUEUED": "waiting to start", "RUNNING": "in progress", "COMPLETED": "finished running",
    "ERROR": "stopped with an error", "INTERRUPTED": "interrupted before it finished",
}


def _assertions(evidence: object) -> tuple[int, int, int, int]:
    """(total, ok, not ok, unclear) over structured assertion rows; non-row items are ignored, not counted."""
    rows = evidence.get("assertions") if isinstance(evidence, dict) else None
    rows = [r for r in rows if isinstance(r, dict)] if isinstance(rows, list) else []
    ok = sum(1 for r in rows if r.get("ok") is True)
    bad = sum(1 for r in rows if r.get("ok") is False)
    return len(rows), ok, bad, len(rows) - ok - bad


def describe_outcome(record: dict, job: dict | None = None) -> dict:
    """Summarise one stored result. ``job`` is the runner job row for the same run, if one is known."""
    verdict = record.get("verdict")
    evidence = record.get("evidence")
    total, ok, bad, unclear = _assertions(evidence)
    out: dict = {"verdict": verdict, "meaning": _MEANING.get(verdict, "Unrecognised verdict; treat as UNKNOWN."),
                 "assertion_total": total, "assertion_ok": ok, "assertion_failed": bad, "assertion_unclear": unclear,
                 "warnings": [], "reason": None, "note": None, "job": None}
    if verdict in ("BLOCKED", "UNKNOWN"):
        cls = reason_class(record)
        out["reason"] = {"class": cls, "text": _REASONS[cls]}
        note = evidence.get("note") if isinstance(evidence, dict) else None
        if isinstance(note, str) and note.strip():
            out["note"] = note.strip()[:_MAX_NOTE]
    if total == 0:
        out["warnings"].append("This record has no structured checks, so nothing in it can be compared with an expectation.")
    if verdict == "PASS" and total and (bad or unclear):
        out["warnings"].append("The verdict is PASS but not every recorded check is marked as passing; "
                               "review the checks before relying on it.")
    if verdict == "FAIL" and total and not bad:
        out["warnings"].append("The verdict is FAIL but no recorded check is marked as failing.")
    if isinstance(job, dict):
        status = job.get("status")
        out["job"] = {"status": status, "meaning": _JOB_MEANING.get(status, "an unrecognised state"),
                      "phase": job.get("phase"), "error_recorded": bool(job.get("error")),
                      "verdict_agrees": job.get("verdict") in (None, verdict)}
    return out


# A run can contain several independently recorded case/stage verdicts. Never collapse
# these into a fabricated overall PASS or infer gameplay from a finished runner job.
_RUN_VERDICT_ORDER = ("FAIL", "BLOCKED", "UNKNOWN", "SKIPPED", "PASS", "UNRECOGNIZED")


def summarize_run(records: list[dict], job: dict | None = None) -> dict:
    """Read-only run overview: count imported verdicts, never issue a new verdict.

    Deliberately excludes account, character and raw job/evidence fields. A missing
    or unexpected verdict is visible as UNRECOGNIZED, never silently treated as PASS.
    """
    counts = dict.fromkeys(_RUN_VERDICT_ORDER, 0)
    scenarios = set()
    for record in records:
        verdict = record.get("verdict")
        key = verdict if isinstance(verdict, str) and verdict in counts else "UNRECOGNIZED"
        counts[key] += 1
        scenarios.add((record.get("feature_id"), record.get("case_id")))
    presented = [{"verdict": name, "count": counts[name]}
                 for name in _RUN_VERDICT_ORDER if counts[name]]
    linked_job = None
    if isinstance(job, dict):
        status = job.get("status")
        # Do not echo untrusted job status, account, character, error or phase data.
        if status in _JOB_MEANING:
            linked_job = {"status": status, "meaning": _JOB_MEANING[status]}
        else:
            linked_job = {"status": "UNKNOWN", "meaning": "status not recognized"}
    return {"record_count": len(records), "scenario_count": len(scenarios),
            "verdict_counts": presented, "mixed_recorded_verdicts": len(presented) > 1,
            "job": linked_job}
