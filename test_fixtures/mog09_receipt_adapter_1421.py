"""Offline, nonproduction, untrusted #1420 sanitized MOG-09 projection only.

No sockets, DB, gameplay, runner, API or independent-oracle claim.
"""
from __future__ import annotations
import json
from pathlib import Path

INPUT = Path(__file__).with_name("mog09_receipt_projection_1421.json")

def project(sample: dict | None) -> dict:
    if not isinstance(sample, dict):
        return {"status": "SOURCE_NOT_FOUND", "verdict": "UNKNOWN", "task_lifecycle": None,
                "independent_oracle": "NOT_ESTABLISHED", "steps": [], "reason": "SOURCE_NOT_FOUND"}
    assertions = sample.get("assertions")
    if not isinstance(assertions, list) or len(assertions) != 6 or any(not isinstance(a, dict) for a in assertions):
        return {"status": "INCOMPLETE", "verdict": "UNKNOWN", "task_lifecycle": None,
                "independent_oracle": "NOT_ESTABLISHED", "steps": [], "reason": "SIX_ASSERTIONS_NOT_AVAILABLE"}
    source_path = sample.get("source_path")
    if not isinstance(source_path, str) or not source_path.strip() or source_path.startswith("/") or ".." in source_path.split("/") or "\\\\" in source_path:
        return {"status": "INCOMPLETE", "verdict": "UNKNOWN", "task_lifecycle": None,
                "independent_oracle": "NOT_ESTABLISHED", "steps": [], "reason": "SOURCE_POINTER_MISSING_OR_UNSAFE"}
    steps = []
    for n, a in enumerate(assertions, 1):
        ok = a.get("runner_ok")
        steps.append({
            "step_number": n, "name": a.get("name", "Unknown assertion"),
            "expected": a.get("expected"), "observed": a.get("observed"),
            "runner_reported_ok": ok if isinstance(ok, bool) else None,
            "local_comparison": "MATCH" if ok is True else ("MISMATCH" if ok is False else "UNKNOWN"),
            "independent_oracle": "NOT_ESTABLISHED",
            "source_pointer": f"{source_path}#/results/0/evidence/assertions/{n-1}"
        })
    raw = sample.get("runner_verdict")
    return {
        "status": "UNREVIEWED_SANITIZED_SOURCE",
        "case_id": sample.get("case_id"),
        "sample_id": sample.get("sample_id"),
        "source_head": sample.get("source_head"),
        "runner_reported_verdict": raw if raw in ("PASS", "FAIL") else "UNKNOWN",
        "verdict": "UNKNOWN",
        "task_lifecycle": sample.get("task_lifecycle"),
        "independent_oracle": "NOT_ESTABLISHED",
        "source_integrity": "NOT_ESTABLISHED",
        "spec_revision": sample.get("spec_revision"),
        "reason": "RUNNER_REPORT_NOT_INDEPENDENTLY_AUTHENTICATED",
        "observations": sample.get("observations"),
        "steps": steps,
    }

def project_fixture(path: Path = INPUT) -> list[dict]:
    if not path.exists():
        return [project(None)]
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return [project(None)]
    if not isinstance(data, dict) or data.get("status") != "DERIVED_FROM_UNREVIEWED_1420_SANITIZED_REPORTS" or not isinstance(data.get("cases"), list) or any(not isinstance(s, dict) for s in data["cases"]):
        return [project(None)]
    return [project(s) for s in data.get("cases", [])] or [project(None)]

if __name__ == "__main__":
    print(json.dumps(project_fixture(), indent=2))
