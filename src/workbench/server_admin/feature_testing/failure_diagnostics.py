"""Bounded, read-only summaries of imported assertion failures.

Imported verdicts and individual assertion verdicts are separate signals.
Never interpret absent or malformed assertion data as successful evidence.
"""
from __future__ import annotations

import json

_MAX_ITEMS = 20
_MAX_TEXT = 500


def _compact(value):
    try:
        encoded = json.dumps(value, ensure_ascii=False, default=str)
    except (ValueError, TypeError):
        return "[unavailable]"
    return encoded if len(encoded) <= _MAX_TEXT else encoded[:_MAX_TEXT] + "…[truncated]"


def failure_summary(row: dict) -> dict | None:
    evidence = row.get("evidence") or {}
    if not isinstance(evidence, dict):
        evidence = {}
    raw = evidence.get("assertions")
    failures = []
    incomplete = False
    if isinstance(raw, list):
        for index, assertion in enumerate(raw):
            if not isinstance(assertion, dict):
                incomplete = True
                continue
            status = assertion.get("verdict")
            ok = assertion.get("ok")
            failed = status in ("FAIL", "BLOCKED") or ok is False
            if status not in ("PASS", "FAIL", "BLOCKED", "SKIPPED", None) or (status is None and not isinstance(ok, bool)):
                incomplete = True
            if failed:
                failures.append({
                    "id": _compact(assertion.get("id", assertion.get("name", index))),
                    "verdict": status if status in ("FAIL", "BLOCKED") else "FAIL",
                    "expected": _compact(assertion.get("expected")),
                    "observed": _compact(assertion.get("observed")),
                    "reason": _compact(assertion.get("reason", assertion.get("error"))),
                })
    elif raw is not None:
        incomplete = True
    evaluation = evidence.get("evaluation")
    if evaluation is not None and not isinstance(evaluation, dict):
        incomplete = True
    verdict = row.get("verdict")
    if verdict not in ("FAIL", "BLOCKED") and not failures and not incomplete:
        return None
    selected = failures[:_MAX_ITEMS]
    return {
        "run_id": row["run_id"], "feature_id": row["feature_id"],
        "case_id": row["case_id"], "stage": row["stage"],
        "verdict": verdict, "observed_at": row["observed_at"],
        "assertions": selected, "assertion_failures_total": len(failures),
        "assertions_truncated": len(failures) > _MAX_ITEMS,
        "incomplete_evidence": incomplete,
        "evaluation": {k: _compact(v) for k, v in list(evaluation.items())[:_MAX_ITEMS]} if isinstance(evaluation, dict) else {},
        "evidence_status": "imported_not_independently_authenticated",
    }
