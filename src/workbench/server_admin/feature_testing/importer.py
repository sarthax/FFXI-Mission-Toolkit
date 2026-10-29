"""Local-only JSON evidence importer. Does not call DSP, headless, or GM APIs.

Invoke from a trusted local process: python -m
workbench.server_admin.feature_testing.importer --catalog ... --database ... --report ...
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sqlite3

from .results import append_result, check_reason_class

_SHA = re.compile(r"^[0-9a-fA-F]{40}$")
IMPORT_CONTEXT_KEY = "import_context"  # written only by this importer; a report may not carry it
CONTEXT_VERSION = 1
_CONTEXT_TEXT = ("environment_fingerprint", "fixture_context")  # optional, runner-supplied, compared for equality only
_FIELDS = ("run_id", "case_id", "feature_id", "stage", "verdict", "observed_at",
           "dsp_commit", "headless_commit", "toolkit_commit", "evidence")


def validate_report(report: dict, catalog: dict) -> list[dict]:
    if not isinstance(report, dict) or report.get("schema_version") != 1:
        raise ValueError("unsupported report schema")
    rows = report.get("results")
    if not isinstance(rows, list) or not 1 <= len(rows) <= 1000:
        raise ValueError("results must contain 1..1000 records")
    known = {f["id"]: {case["id"] for case in f.get("cases", [])}
             for f in catalog.get("features", [])}
    seen = set()
    for row in rows:
        if not isinstance(row, dict) or set(row) != set(_FIELDS):
            raise ValueError("unexpected or missing result fields")
        if row["feature_id"] not in known or row["case_id"] not in known[row["feature_id"]]:
            raise ValueError("result references unknown feature or scenario")
        for field in ("dsp_commit", "headless_commit", "toolkit_commit"):
            if not isinstance(row[field], str) or not _SHA.fullmatch(row[field]):
                raise ValueError(f"invalid {field}; full git SHA required")
        if not isinstance(row["observed_at"], str):
            raise ValueError("timestamp missing")
        try:
            date = datetime.fromisoformat(row["observed_at"].replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("invalid timestamp") from exc
        if date.tzinfo is None or date.utcoffset() != timezone.utc.utcoffset(date):
            raise ValueError("UTC timestamp required")
        if row["verdict"] == "PASS" and not {
            "assertions", "observations"
        }.issubset(row["evidence"] if isinstance(row["evidence"], dict) else {}):
            raise ValueError("PASS requires assertions and observations; never infer PASS from a log")
        # reason_class is optional; when present it must be one of the known values.
        check_reason_class(row["verdict"], row["evidence"])
        evidence = row["evidence"] if isinstance(row["evidence"], dict) else {}
        if IMPORT_CONTEXT_KEY in evidence:
            raise ValueError(f"evidence.{IMPORT_CONTEXT_KEY} is reserved for the importer and cannot be supplied")
        for key in _CONTEXT_TEXT:
            if key in evidence and (not isinstance(evidence[key], str) or not evidence[key].strip()
                                    or len(evidence[key]) > 256):
                raise ValueError(f"evidence.{key} must be a non-empty string of at most 256 characters")
        identity = (row["run_id"], row["case_id"], row["stage"])
        if identity in seen:
            raise ValueError("duplicate result identity in report")
        seen.add(identity)
    return rows


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def import_context(row: dict, report_schema_version: int, spec: dict | None) -> dict:
    """Facts the importer can establish itself, stored beside the report's own evidence (no schema change).

    ``definition_sha256`` is the fingerprint of the published specification as it stood at import time (None when
    there is no specification for the case); it lets a later comparison tell whether two runs tested the same
    definition. ``record_sha256`` hashes the record exactly as imported, before this context was added, so a stored
    row can later be checked against the report it came from. Neither says anything about the run itself.
    """
    from .scenario_contract_v2 import base_spec_sha256
    return {"version": CONTEXT_VERSION,
            "definition_sha256": base_spec_sha256(spec) if spec is not None else None,
            "report_schema_version": report_schema_version,
            "record_sha256": hashlib.sha256(_canonical(row).encode("utf-8")).hexdigest()}


def import_report(db_path: str | Path, catalog_path: str | Path, report_path: str | Path) -> int:
    """Validate entire report first; commit all rows in one transaction or none."""
    raw_path = Path(report_path)
    if raw_path.stat().st_size > 5_000_000:
        raise ValueError("report too large")
    report = json.loads(raw_path.read_text(encoding="utf-8"))
    catalog = json.loads(Path(catalog_path).read_text(encoding="utf-8"))
    rows = validate_report(report, catalog)
    from .test_specifications import specification
    rows = [{**row, "evidence": {**row["evidence"], IMPORT_CONTEXT_KEY: import_context(
        row, report["schema_version"], specification(row["feature_id"], row["case_id"]))}} for row in rows]
    target = Path(db_path)
    if not target.is_absolute():
        raise ValueError("database path must be absolute")
    # Stage into a temporary SQLite database, including duplicate/size checks,
    # then use one transaction on the target for atomic persistence.
    from .results import init_db, VERDICTS, STAGES
    for row in rows:
        if row["verdict"] not in VERDICTS or row["stage"] not in STAGES:
            raise ValueError("invalid verdict or stage")
        if any(not isinstance(row[k], str) or not row[k].strip() or len(row[k]) > 256
               for k in _FIELDS if k != "evidence"):
            raise ValueError("invalid field")
        if not isinstance(row["evidence"], dict) or not row["evidence"]:
            raise ValueError("empty evidence")
        if len(json.dumps(row["evidence"])) > 262144:
            raise ValueError("evidence too large")
    init_db(target)
    with sqlite3.connect(str(target)) as conn:
        for row in rows:
            conn.execute("INSERT INTO feature_test_results VALUES (?,?,?,?,?,?,?,?,?,?)",
                         tuple(row[k] for k in _FIELDS if k != "evidence")
                         + (json.dumps(row["evidence"], sort_keys=True),))
    return len(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Import trusted offline feature test reports")
    parser.add_argument("--database", required=True, type=Path)
    parser.add_argument("--catalog", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()
    print(f"Imported {import_report(args.database, args.catalog, args.report)} evidence records")


if __name__ == "__main__":
    main()
