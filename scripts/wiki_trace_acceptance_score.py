"""Read-only operator acceptance scorecard for Wiki ↔ Feature Trace.

Accepts a JSON array of observed cases. Does not access the local database,
assert gameplay truth, or convert offline fixtures into live acceptance.

Run: python scripts/wiki_trace_acceptance_score.py observations.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

CASES = ("medusa", "absolute-virtue", "wrong-source", "duplicate-heading")
METRICS = ("identity_correct", "locator_correct", "navigation_correct", "review_only")
STATES = {"PASS", "FAIL", "BLOCKED", "NOT_RUN"}


def summarize(observations: list[dict]) -> dict:
    if not isinstance(observations, list):
        raise ValueError("Expected a JSON array of observed cases")
    seen = set()
    result = []
    for row in observations:
        if not isinstance(row, dict):
            raise ValueError("Each case must be an object")
        case = row.get("case")
        if case not in CASES or case in seen:
            raise ValueError(f"Unknown or repeated case: {case!r}")
        seen.add(case)
        status = row.get("status", "NOT_RUN")
        if status not in STATES:
            raise ValueError(f"Invalid status for {case}: {status!r}")
        checks = row.get("checks") or {}
        if not isinstance(checks, dict) or any(k not in METRICS or not isinstance(v, bool) for k,v in checks.items()):
            raise ValueError(f"Invalid checks for {case}")
        clicks = row.get("clicks")
        if clicks is not None and (type(clicks) is not int or clicks < 0):
            raise ValueError(f"Invalid click count for {case}")
        if status in ("PASS", "FAIL"):
            if set(checks) != set(METRICS):
                raise ValueError(f"Observed {case} requires all four checks")
            if not row.get("environment") or not row.get("source_revision"):
                raise ValueError(f"Observed {case} requires environment and source revision")
            if clicks is None:
                raise ValueError(f"Observed {case} requires measured clicks")
            if status == "PASS" and not all(checks.values()):
                raise ValueError(f"PASS case has failing checks: {case}")
            if status == "FAIL" and all(checks.values()):
                raise ValueError(f"FAIL case contains no failed check: {case}")
        result.append({"case":case,"status":status,"checks":checks,"clicks":clicks})
    counts={state:sum(row["status"] == state for row in result) for state in sorted(STATES)}
    return {"case_count":len(result),"counts":counts,
            "all_passed":len(result)==len(CASES) and counts["PASS"]==len(CASES),
            "observations":result}


def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    if len(args)!=1:
        raise SystemExit("Usage: python scripts/wiki_trace_acceptance_score.py observations.json")
    data=json.loads(Path(args[0]).read_text(encoding="utf-8"))
    print(json.dumps(summarize(data),indent=2,ensure_ascii=False))


if __name__ == "__main__":
    main()
