"""Narrow, non-executing persisted progression observations."""
from __future__ import annotations
from datetime import datetime, timezone
from .database_diagnostics import _approved_connection, _VAR_NAME, decode_keyitems

def progression_snapshot(charid: int, names: list[str], include_keyitems: bool = True) -> dict:
    if not 1 <= len(names) <= 50 or len(set(names)) != len(names) or any(not _VAR_NAME.fullmatch(n) for n in names):
        raise ValueError("provide 1..50 unique named character variables")
    opened = _approved_connection(charid)
    result = {
        "charid": charid, "snapshot_kind": "persisted_db_not_live_memory",
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "source_revision": "UNKNOWN", "deployment_attestation": "UNKNOWN",
        "execution_enabled": False, "client_agreement": "UNKNOWN",
        "auth_scope": "approved_disposable_character", "jobs": {"status": "UNSUPPORTED"},
        "quests": {"status": "UNSUPPORTED"}, "currencies": {"status": "UNSUPPORTED"},
        "keyitems": {"status": "NOT_REQUESTED" if not include_keyitems else "UNKNOWN"},
    }
    if opened is None:
        return {**result, "configured": False, "status": "UNAVAILABLE", "complete": False, "vars": {}}
    conn, cursor = opened
    try:
        cursor.execute("SELECT charid FROM chars WHERE charid = %s", (charid,))
        character_row = cursor.fetchone()
        if character_row is None:
            conn.rollback()
            return {**result, "configured": True, "status": "UNKNOWN_CHARACTER",
                    "complete": False, "supported_fields_complete": False, "vars": {},
                    "keyitems": {"status": "UNKNOWN_CHARACTER" if include_keyitems else "NOT_REQUESTED"}}
        marks = ",".join(["%s"] * len(names))
        cursor.execute(f"SELECT varname, value FROM char_vars WHERE charid = %s AND varname IN ({marks})",
                       (charid, *names))
        rows = cursor.fetchall()
        found = {str(r["varname"] if isinstance(r, dict) else r[0]):
                 (r["value"] if isinstance(r, dict) else r[1]) for r in rows}
        keyitems = {"status": "NOT_REQUESTED"}
        if include_keyitems:
            cursor.execute("SELECT keyitems FROM chars WHERE charid = %s", (charid,))
            row = cursor.fetchone()
            if row is None:
                keyitems = {"status": "UNKNOWN_CHARACTER"}
            else:
                raw = row["keyitems"] if isinstance(row, dict) else row[0]
                decoded = decode_keyitems(raw)
                keyitems = {**decoded, "status": "COMPLETE" if decoded["blob_bytes"] == decoded["expected_bytes"] else "INCOMPLETE"}
        conn.rollback()
    except Exception:
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()
    vars_report = {n: {"found": n in found, "status": "PRESENT" if n in found else "ABSENT",
                       "value": found.get(n)} for n in names}
    complete = (not include_keyitems or keyitems["status"] == "COMPLETE")
    return {**result, "configured": True, "vars": vars_report, "keyitems": keyitems,
            "status": "COMPLETE_SUPPORTED_FIELDS" if complete else "INCOMPLETE",
            "complete": False, "supported_fields_complete": complete,
            "note": "job, quest and currency oracles unsupported until source schema verified; no gameplay or unlock assertion"}
