"""SQLite-backed, append-only feature testing evidence records.

Storage is local and is never populated with fabricated demonstration results.
Only trusted local importers should call append_result; no public write route.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

# UNKNOWN: a run produced no usable determination. It is recorded explicitly, never inferred from a missing row
# and never promoted to PASS. The column has no SQL CHECK; this set is the only gate.
VERDICTS = frozenset({"PASS", "FAIL", "BLOCKED", "SKIPPED", "UNKNOWN"})
# Optional controlled cause for a BLOCKED or UNKNOWN result: evidence["reason_class"]. Validated only when present.
BLOCK_REASON_CLASSES = frozenset({"ENVIRONMENT", "FIXTURE_ABSENT", "ORACLE_UNKNOWN", "OTHER"})
UNCLASSIFIED = "UNCLASSIFIED"  # read-side label for historical rows that predate reason_class
STAGES = frozenset({"key_item", "modifier", "behavior", "mechanics", "gameplay"})


def reason_class(record: dict) -> str | None:
    """Optional cause of a BLOCKED/UNKNOWN record; ``UNCLASSIFIED`` when none was recorded.

    Returns None for other verdicts.
    """
    if record.get("verdict") not in ("BLOCKED", "UNKNOWN"):
        return None
    evidence = record.get("evidence")
    value = evidence.get("reason_class") if isinstance(evidence, dict) else None
    return value if value in BLOCK_REASON_CLASSES else UNCLASSIFIED


def check_reason_class(verdict: str, evidence: object) -> None:
    """If ``evidence.reason_class`` is present it must be a known value; it is never required."""
    if isinstance(evidence, dict) and "reason_class" in evidence \
            and evidence["reason_class"] not in BLOCK_REASON_CLASSES:
        raise ValueError("invalid reason_class; expected one of " + ", ".join(sorted(BLOCK_REASON_CLASSES)))


def init_db(path: str | Path) -> None:
    with sqlite3.connect(str(path)) as db:
        db.execute("""CREATE TABLE IF NOT EXISTS feature_test_results (
            run_id TEXT NOT NULL, case_id TEXT NOT NULL, feature_id TEXT NOT NULL,
            stage TEXT NOT NULL, verdict TEXT NOT NULL, observed_at TEXT NOT NULL,
            dsp_commit TEXT NOT NULL, headless_commit TEXT NOT NULL,
            toolkit_commit TEXT NOT NULL, evidence_json TEXT NOT NULL,
            PRIMARY KEY (run_id, case_id, stage))""")


def append_result(path: str | Path, result: dict) -> None:
    fields = ("run_id", "case_id", "feature_id", "stage", "verdict",
              "observed_at", "dsp_commit", "headless_commit", "toolkit_commit", "evidence")
    if any(k not in result for k in fields):
        raise ValueError("result missing required evidence fields")
    if result["verdict"] not in VERDICTS or result["stage"] not in STAGES:
        raise ValueError("invalid stage or verdict")
    if any(not isinstance(result[k], str) or not result[k].strip() or len(result[k]) > 256
           for k in fields if k != "evidence"):
        raise ValueError("invalid record identifier or revision")
    evidence = result["evidence"]
    if not isinstance(evidence, dict) or not evidence:
        raise ValueError("structured evidence required; empty run cannot pass")
    check_reason_class(result["verdict"], evidence)
    payload = json.dumps(evidence, separators=(",", ":"), sort_keys=True)
    if len(payload) > 262144:
        raise ValueError("evidence too large")
    init_db(path)
    with sqlite3.connect(str(path)) as db:
        db.execute("""INSERT INTO feature_test_results VALUES (?,?,?,?,?,?,?,?,?,?)""",
                   tuple(result[k] for k in fields if k != "evidence") + (payload,))


def recent_results(path: str | Path, *, feature_id: str | None = None,
                   case_id: str | None = None, limit: int = 100) -> list[dict]:
    if not isinstance(limit, int) or not 1 <= limit <= 500:
        raise ValueError("limit must be 1..500")
    if not Path(path).is_file():
        return []
    query = "SELECT * FROM feature_test_results WHERE 1=1"
    args: list = []
    for name, value in (("feature_id", feature_id), ("case_id", case_id)):
        if value is not None:
            query += f" AND {name} = ?"
            args.append(value)
    query += " ORDER BY observed_at DESC, run_id DESC LIMIT ?"
    args.append(limit)
    with sqlite3.connect(str(path)) as db:
        db.row_factory = sqlite3.Row
        rows = db.execute(query, args).fetchall()
    return [{**dict(r), "evidence": json.loads(r["evidence_json"])} for r in rows]


def results_for_run(path: str | Path, run_id: str, *, limit: int = 25) -> list[dict]:
    """Exact run lookup, independent of the global recent-history window."""
    if not isinstance(run_id, str) or not run_id.strip() or len(run_id) > 256:
        raise ValueError("invalid run identifier")
    if not isinstance(limit, int) or not 1 <= limit <= 25:
        raise ValueError("limit must be 1..25")
    if not Path(path).is_file():
        return []
    with sqlite3.connect(str(path)) as db:
        db.row_factory = sqlite3.Row
        rows = db.execute(
            "SELECT * FROM feature_test_results WHERE run_id = ? ORDER BY observed_at DESC, case_id, stage LIMIT ?",
            (run_id, limit + 1),
        ).fetchall()
    if len(rows) > limit:
        raise ValueError("run exceeds supervisor evidence record limit")
    results = []
    for row in rows:
        record = dict(row)
        try:
            evidence = json.loads(record.pop("evidence_json"))
        except (TypeError, ValueError) as exc:
            raise ValueError("invalid stored evidence JSON") from exc
        if not isinstance(evidence, dict):
            raise ValueError("invalid stored evidence object")
        results.append({**record, "evidence": evidence})
    return results
