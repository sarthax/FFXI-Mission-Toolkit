"""#1410: a versioned, searchable catalog of design-only scenario revisions.

Distinct from the global Feature Catalog (Toolkit capabilities) and from the built-in published specifications. An entry
is a (feature_id, case_id) identity; its content only ever changes by adding a new immutable revision. A revision's
review state moves forward through append-only events (DRAFT, VALIDATED_DESIGN, PUBLISHED, ARCHIVED). Publishing is a
review decision recorded with a note; it never makes anything runnable: every revision must stay ``design_only`` with an
unassigned runner, and nothing here launches, schedules or evaluates a test.

Storage is the local authoring SQLite file that already holds spec drafts (``MISSION_TOOLKIT_TEST_DRAFTS_DB``); two
tables are created on first use. Revisions and events are protected against UPDATE and DELETE by triggers, so history
cannot be rewritten through this interface or by an accidental statement.
"""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from datetime import datetime, timezone

from .scenario_contract_v2 import base_spec_sha256
from .spec_drafts import _path, get_draft
from .test_specifications import validate_spec

STATES = ("DRAFT", "VALIDATED_DESIGN", "PUBLISHED", "ARCHIVED")
_NEXT = {"DRAFT": ("VALIDATED_DESIGN", "ARCHIVED"), "VALIDATED_DESIGN": ("PUBLISHED", "ARCHIVED"),
         "PUBLISHED": ("ARCHIVED",), "ARCHIVED": ()}
MAX_SPEC_BYTES = 32768
MAX_TAGS = 10
_ID = re.compile(r"[A-Za-z0-9_-]{1,120}")
_TAG = re.compile(r"[a-z0-9][a-z0-9_-]{0,31}")
_SOURCE = re.compile(r"(draft|import|manual):[^\x00-\x1f\x7f]{0,248}|manual")
_NOTE_MAX = 300
RUN_AVAILABILITY = "UNAVAILABLE"  # a catalog entry never grants a run; see #1412 for the separate, gated path


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _db() -> sqlite3.Connection:
    conn = sqlite3.connect(str(_path()), timeout=5)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS test_catalog_revisions (
            feature_id TEXT NOT NULL, case_id TEXT NOT NULL, revision INTEGER NOT NULL,
            content TEXT NOT NULL, content_sha256 TEXT NOT NULL, base_spec_sha256 TEXT NOT NULL,
            source TEXT NOT NULL, tags TEXT NOT NULL, created_at TEXT NOT NULL,
            PRIMARY KEY (feature_id, case_id, revision));
        CREATE TABLE IF NOT EXISTS test_catalog_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT, feature_id TEXT NOT NULL, case_id TEXT NOT NULL,
            revision INTEGER NOT NULL, state TEXT NOT NULL, note TEXT NOT NULL, at TEXT NOT NULL);
        CREATE TRIGGER IF NOT EXISTS test_catalog_revisions_no_update BEFORE UPDATE ON test_catalog_revisions
            BEGIN SELECT RAISE(ABORT, 'catalog revisions are immutable'); END;
        CREATE TRIGGER IF NOT EXISTS test_catalog_revisions_no_delete BEFORE DELETE ON test_catalog_revisions
            BEGIN SELECT RAISE(ABORT, 'catalog revisions are immutable'); END;
        CREATE TRIGGER IF NOT EXISTS test_catalog_events_no_update BEFORE UPDATE ON test_catalog_events
            BEGIN SELECT RAISE(ABORT, 'catalog events are append-only'); END;
        CREATE TRIGGER IF NOT EXISTS test_catalog_events_no_delete BEFORE DELETE ON test_catalog_events
            BEGIN SELECT RAISE(ABORT, 'catalog events are append-only'); END;
    """)
    return conn


def _check_identity(feature_id: object, case_id: object) -> None:
    if not (isinstance(feature_id, str) and isinstance(case_id, str) and _ID.fullmatch(feature_id) and _ID.fullmatch(case_id)):
        raise ValueError("invalid feature or case identifier")


def _check_spec(payload: object) -> dict:
    if not isinstance(payload, dict):
        raise ValueError("specification must be an object")
    spec = dict(payload)
    if spec.get("execution_status") != "design_only" or spec.get("runner") != "unassigned":
        raise ValueError("catalog revisions must remain design_only with an unassigned runner")
    validate_spec(spec)
    _check_identity(spec["feature_id"], spec["case_id"])
    return spec


def _clean_tags(tags: object) -> list[str]:
    if tags is None:
        return []
    if not isinstance(tags, (list, tuple)) or len(tags) > MAX_TAGS:
        raise ValueError(f"tags must be a list of at most {MAX_TAGS}")
    cleaned = []
    for tag in tags:
        if not isinstance(tag, str) or not _TAG.fullmatch(tag):
            raise ValueError("a tag is lowercase letters, digits, - or _, at most 32 characters")
        if tag not in cleaned:
            cleaned.append(tag)
    return sorted(cleaned)


def _row_state(conn: sqlite3.Connection, feature_id: str, case_id: str, revision: int) -> str:
    row = conn.execute("SELECT state FROM test_catalog_events WHERE feature_id=? AND case_id=? AND revision=? "
                       "ORDER BY id DESC LIMIT 1", (feature_id, case_id, revision)).fetchone()
    return row[0] if row else "DRAFT"


def add_revision(payload: object, *, source: str, tags: object = None, expected_latest: int = 0) -> dict:
    """Add the next immutable revision of an entry. ``expected_latest`` is the revision the caller last saw (0 for new)."""
    spec = _check_spec(payload)
    if not isinstance(source, str) or not _SOURCE.fullmatch(source):
        raise ValueError("source must be 'manual' or start with 'draft:', 'import:' or 'manual:' (at most 256 characters)")
    if type(expected_latest) is not int or expected_latest < 0:
        raise ValueError("expected_latest must be a nonnegative integer")
    cleaned = _clean_tags(tags)
    serialized = json.dumps(spec, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    if len(serialized.encode("utf-8")) > MAX_SPEC_BYTES:
        raise ValueError("specification exceeds 32KiB")
    feature_id, case_id = spec["feature_id"], spec["case_id"]
    with _db() as conn:
        latest = conn.execute("SELECT MAX(revision) FROM test_catalog_revisions WHERE feature_id=? AND case_id=?",
                              (feature_id, case_id)).fetchone()[0] or 0
        if latest != expected_latest:
            raise ValueError("revision conflict: the entry changed; refresh before adding a revision")
        revision = latest + 1
        at = _now()
        conn.execute("INSERT INTO test_catalog_revisions VALUES (?,?,?,?,?,?,?,?,?)",
                     (feature_id, case_id, revision, serialized, hashlib.sha256(serialized.encode("utf-8")).hexdigest(),
                      base_spec_sha256(spec), source, json.dumps(cleaned), at))
        conn.execute("INSERT INTO test_catalog_events (feature_id, case_id, revision, state, note, at) VALUES (?,?,?,?,?,?)",
                     (feature_id, case_id, revision, "DRAFT", "", at))
    return {"feature_id": feature_id, "case_id": case_id, "revision": revision, "state": "DRAFT",
            "execution_enabled": False, "run_availability": RUN_AVAILABILITY}


def add_from_draft(feature_id: str, case_id: str, draft_revision: int, *, tags: object = None,
                   expected_latest: int | None = None) -> dict:
    """Add the saved draft as the next catalog revision. The content comes from the stored draft, never from the caller.

    ``draft_revision`` is the saved-draft revision the caller looked at; if the draft has moved on, nothing is added.
    The source recorded is ``draft:<feature>/<case>@r<revision>``. A draft whose content already equals the latest
    catalog revision is refused rather than added again.
    """
    _check_identity(feature_id, case_id)
    if type(draft_revision) is not int or draft_revision < 1:
        raise ValueError("draft_revision must be a positive integer")
    draft = get_draft(feature_id, case_id)
    if draft is None:
        raise ValueError("no such saved draft")
    if draft["revision"] != draft_revision:
        raise ValueError("draft conflict: the saved draft changed (now revision %d); refresh the draft list" % draft["revision"])
    serialized = json.dumps(draft["specification"], sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    digest = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
    with _db() as conn:
        latest = conn.execute("SELECT revision, content_sha256 FROM test_catalog_revisions WHERE feature_id=? AND case_id=? "
                              "ORDER BY revision DESC LIMIT 1", (feature_id, case_id)).fetchone()
    if latest and latest[1] == digest:
        raise ValueError("this saved draft is already the latest catalog revision (r%d); nothing to add" % latest[0])
    return add_revision(draft["specification"], source=f"draft:{feature_id}/{case_id}@r{draft_revision}", tags=tags,
                        expected_latest=(latest[0] if latest else 0) if expected_latest is None else expected_latest)


def record_state(feature_id: str, case_id: str, revision: int, state: str, note: str = "") -> dict:
    """Move a revision forward one review step. Publishing needs a reviewer note; nothing here grants a run."""
    _check_identity(feature_id, case_id)
    if state not in STATES or type(revision) is not int or revision < 1:
        raise ValueError("unknown state or revision")
    if not isinstance(note, str) or len(note) > _NOTE_MAX or re.search(r"[\x00-\x08\x0b-\x1f\x7f]", note):
        raise ValueError(f"note must be text of at most {_NOTE_MAX} characters")
    note = note.strip()
    with _db() as conn:
        row = conn.execute("SELECT content FROM test_catalog_revisions WHERE feature_id=? AND case_id=? AND revision=?",
                           (feature_id, case_id, revision)).fetchone()
        if row is None:
            raise ValueError("no such revision")
        current = _row_state(conn, feature_id, case_id, revision)
        if state not in _NEXT[current]:
            raise ValueError(f"a {current} revision cannot move to {state}")
        if state in ("VALIDATED_DESIGN", "PUBLISHED"):
            _check_spec(json.loads(row[0]))  # a stored revision is re-checked against today's rules before it advances
        if state == "PUBLISHED" and not note:
            raise ValueError("publishing records a reviewer decision: a note is required")
        conn.execute("INSERT INTO test_catalog_events (feature_id, case_id, revision, state, note, at) VALUES (?,?,?,?,?,?)",
                     (feature_id, case_id, revision, state, note, _now()))
    return {"feature_id": feature_id, "case_id": case_id, "revision": revision, "state": state,
            "execution_enabled": False, "run_availability": RUN_AVAILABILITY}


def _summary(conn: sqlite3.Connection, feature_id: str, case_id: str) -> dict:
    revisions = conn.execute("SELECT revision, content, tags, created_at FROM test_catalog_revisions "
                             "WHERE feature_id=? AND case_id=? ORDER BY revision", (feature_id, case_id)).fetchall()
    states = {r[0]: _row_state(conn, feature_id, case_id, r[0]) for r in revisions}
    latest = revisions[-1]
    spec = json.loads(latest[1])
    published = [rev for rev, st in states.items() if st == "PUBLISHED"]
    return {"feature_id": feature_id, "case_id": case_id, "name": spec.get("name"), "purpose": spec.get("purpose"),
            "tags": json.loads(latest[2]), "latest_revision": latest[0], "latest_state": states[latest[0]],
            "current_published_revision": max(published) if published else None,
            "revision_count": len(revisions), "updated_at": latest[3],
            "execution_enabled": False, "run_availability": RUN_AVAILABILITY}


def list_entries(*, q: str = "", feature_id: str = "", tag: str = "", state: str = "", limit: int = 100,
                 offset: int = 0) -> dict:
    """Search entries by text (name, purpose, case id, tags), feature, tag and the latest revision's state."""
    if not (isinstance(limit, int) and 1 <= limit <= 200 and isinstance(offset, int) and 0 <= offset <= 10000):
        raise ValueError("invalid paging")
    if state and state not in STATES:
        raise ValueError("unknown state")
    needle = q.strip().lower()
    with _db() as conn:
        keys = conn.execute("SELECT DISTINCT feature_id, case_id FROM test_catalog_revisions ORDER BY feature_id, case_id").fetchall()
        entries = [_summary(conn, f, c) for f, c in keys[:2000]]
    def keep(entry: dict) -> bool:
        if feature_id and entry["feature_id"] != feature_id:
            return False
        if tag and tag not in entry["tags"]:
            return False
        if state and entry["latest_state"] != state:
            return False
        if needle:
            haystack = " ".join([entry["case_id"], entry["name"] or "", entry["purpose"] or "", " ".join(entry["tags"])]).lower()
            return needle in haystack
        return True
    matched = [e for e in entries if keep(e)]
    return {"entries": matched[offset:offset + limit], "total": len(matched), "execution_enabled": False,
            "run_availability": RUN_AVAILABILITY}


def get_entry(feature_id: str, case_id: str) -> dict | None:
    """One entry with every revision (including its content hash and source) and its full state history."""
    _check_identity(feature_id, case_id)
    with _db() as conn:
        rows = conn.execute("SELECT revision, content, content_sha256, base_spec_sha256, source, tags, created_at "
                            "FROM test_catalog_revisions WHERE feature_id=? AND case_id=? ORDER BY revision",
                            (feature_id, case_id)).fetchall()
        if not rows:
            return None
        events = conn.execute("SELECT revision, state, note, at FROM test_catalog_events WHERE feature_id=? AND case_id=? "
                              "ORDER BY id", (feature_id, case_id)).fetchall()
        summary = _summary(conn, feature_id, case_id)
    revisions = [{"revision": r[0], "specification": json.loads(r[1]), "content_sha256": r[2], "base_spec_sha256": r[3],
                  "source": r[4], "tags": json.loads(r[5]), "created_at": r[6],
                  "events": [{"state": e[1], "note": e[2], "at": e[3]} for e in events if e[0] == r[0]]} for r in rows]
    return {**summary, "revisions": revisions}
