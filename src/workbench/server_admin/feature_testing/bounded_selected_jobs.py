"""Persisted selected-job/level readback for approved test characters only.

Repository schema evidence: darkstar-to-valhalla/sql/char_stats.sql.
This is never a live job/unlock, quest, currency, or combat oracle.
"""
from __future__ import annotations

from datetime import datetime, timezone
from .database_diagnostics import _approved_connection

_FIELDS = ("mjob", "sjob", "mlvl", "slvl")


def selected_jobs_snapshot(charid: int) -> dict:
    """Bounded fixed-SELECT observation, with no implicit schema/deployment attestation."""
    try:
        opened = _approved_connection(charid)
    except ValueError:
        raise  # Includes disallowed disposable character IDs.
    except Exception as exc:
        raise RuntimeError("selected-jobs observation unavailable (database connection failed)") from exc

    base = {
        "charid": charid,
        "snapshot_kind": "persisted_db_not_live_memory",
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "source_revision": "UNKNOWN",
        "deployment_attestation": "UNKNOWN",
        "schema_revision": "UNKNOWN",
        "client_agreement": "UNKNOWN",
        "authorization_scope": "approved_disposable_character",
        "execution_enabled": False,
        "complete": False,  # Full progression contract remains unsupported.
        "supported_fields_complete": False,
        "selected_jobs": None,
        "job_unlock_status": "UNSUPPORTED",
        "quest_status": "UNSUPPORTED",
        "currencies": "UNSUPPORTED",
        "note": "Selected persisted database fields only; no live-memory or unlock inference.",
    }
    if opened is None:
        return {**base, "configured": False, "status": "UNAVAILABLE"}

    conn, cursor = opened
    try:
        cursor.execute("SELECT charid FROM chars WHERE charid = %s", (charid,))
        if cursor.fetchone() is None:
            return {**base, "configured": True, "status": "UNKNOWN_CHARACTER"}

        cursor.execute(
            "SELECT mjob, sjob, mlvl, slvl FROM char_stats WHERE charid = %s LIMIT 2",
            (charid,),
        )
        rows = cursor.fetchall()
        if not rows:
            return {**base, "configured": True, "status": "INCOMPLETE_MISSING_CHAR_STATS"}
        if len(rows) != 1:
            return {**base, "configured": True, "status": "INCOMPLETE_AMBIGUOUS_CHAR_STATS"}

        row = rows[0]
        fields = {key: row.get(key) for key in _FIELDS} if isinstance(row, dict) else (
            dict(zip(_FIELDS, row)) if isinstance(row, (tuple, list)) and len(row) == len(_FIELDS) else {}
        )
        # Source SQL declares all four as UNSIGNED TINYINT; preserve zero literally.
        # Reject strings/booleans/NULLs/floats rather than inventing coercions or meaning.
        if not all(type(fields.get(key)) is int and 0 <= fields[key] <= 255 for key in _FIELDS):
            return {**base, "configured": True, "status": "INCOMPLETE_INVALID_PERSISTED_FIELDS"}

        return {
            **base, "configured": True, "status": "PERSISTED_FIELDS_OBSERVED",
            "supported_fields_complete": True,
            "selected_jobs": {
                "main_job_id": fields["mjob"], "support_job_id": fields["sjob"],
                "main_level": fields["mlvl"], "support_level": fields["slvl"],
            },
        }
    except Exception as exc:
        raise RuntimeError("selected-jobs observation unavailable (database SELECT/schema failed)") from exc
    finally:
        try:
            conn.rollback()
        finally:
            cursor.close()
            conn.close()
