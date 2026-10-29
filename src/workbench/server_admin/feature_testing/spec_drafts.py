"""Operator-authenticated, revisioned local test-definition drafts.

Drafts are design-only and cannot assign executable runners. Published source
contracts and the runner allowlist remain immutable through this interface.
"""
from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path

from .test_specifications import validate_spec, specification


def _path():
    raw = os.environ.get("MISSION_TOOLKIT_TEST_DRAFTS_DB", "")
    path = Path(raw) if raw else None
    if not path or not path.is_absolute() or not path.parent.is_dir():
        raise ValueError("MISSION_TOOLKIT_TEST_DRAFTS_DB must be an absolute path with existing parent")
    return path


def _db():
    conn = sqlite3.connect(str(_path()), timeout=5)
    conn.execute("""CREATE TABLE IF NOT EXISTS test_spec_drafts (
        feature_id TEXT NOT NULL, case_id TEXT NOT NULL,
        revision INTEGER NOT NULL, content TEXT NOT NULL,
        PRIMARY KEY (feature_id, case_id))""")
    return conn


def _validate_draft(payload):
    if not isinstance(payload, dict):
        raise ValueError("draft must be an object")
    spec = dict(payload)
    # Never let a design document claim a verified execution binding.
    if spec.get("execution_status") != "design_only" or spec.get("runner") != "unassigned":
        raise ValueError("drafts must remain design_only with unassigned runner")
    validate_spec(spec)
    if not all(c.isalnum() or c in "_-" for c in spec["feature_id"] + spec["case_id"]):
        raise ValueError("invalid draft identifiers")
    if specification(spec["feature_id"], spec["case_id"]) is not None:
        raise ValueError("published test specifications cannot be overwritten")
    return spec


def get_drafts(limit=100):
    with _db() as conn:
        rows=conn.execute("SELECT feature_id,case_id,revision,content FROM test_spec_drafts ORDER BY feature_id,case_id LIMIT ?",(limit,)).fetchall()
    return [{"feature_id":r[0],"case_id":r[1],"revision":r[2],"specification":json.loads(r[3])} for r in rows]


def get_draft(feature_id: str, case_id: str) -> dict | None:
    """One saved draft with its current revision, or None. Read-only."""
    with _db() as conn:
        row = conn.execute("SELECT revision,content FROM test_spec_drafts WHERE feature_id=? AND case_id=?",
                           (feature_id, case_id)).fetchone()
    return {"feature_id": feature_id, "case_id": case_id, "revision": row[0], "specification": json.loads(row[1])} if row else None


def save_draft(payload, expected_revision: int):
    spec=_validate_draft(payload)
    if type(expected_revision) is not int or expected_revision < 0:
        raise ValueError("expected_revision must be a nonnegative integer")
    serialized=json.dumps(spec, sort_keys=True, separators=(",", ":"))
    if len(serialized.encode("utf-8")) > 32768:
        raise ValueError("draft exceeds 32KiB")
    with _db() as conn:
        current=conn.execute("SELECT revision FROM test_spec_drafts WHERE feature_id=? AND case_id=?",
                             (spec["feature_id"],spec["case_id"])).fetchone()
        version=current[0] if current else 0
        if version != expected_revision:
            raise ValueError("revision conflict: refresh draft before saving")
        if version == 0:
            conn.execute("INSERT INTO test_spec_drafts VALUES (?,?,?,?)",
                         (spec["feature_id"],spec["case_id"],1,serialized))
        else:
            conn.execute("UPDATE test_spec_drafts SET revision=?,content=? WHERE feature_id=? AND case_id=?",
                         (version+1,serialized,spec["feature_id"],spec["case_id"]))
    return {"feature_id":spec["feature_id"],"case_id":spec["case_id"],"revision":version+1,
            "execution_enabled":False}
