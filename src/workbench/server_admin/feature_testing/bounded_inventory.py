"""Bounded persisted inventory observation; no live-memory or furnishing claims."""
from __future__ import annotations
from datetime import datetime, timezone
import base64
from .database_diagnostics import _approved_connection

# DSP inventory location identifiers; never accept arbitrary containers.
_LOCATIONS = {0: "inventory", 1: "mog_safe", 10: "mog_safe_2"}
_MAX_PAGE = 100
_MAX_EXTRA_BYTES = 4096
_MAX_RESPONSE_EXTRA_BYTES = 65536

def inventory_snapshot_v2(charid: int, location: int, cursor: int = 0, limit: int = 100) -> dict:
    if location not in _LOCATIONS:
        raise ValueError("unsupported container location")
    if not isinstance(cursor, int) or cursor < 0 or cursor > 100000:
        raise ValueError("invalid page cursor")
    if not isinstance(limit, int) or not 1 <= limit <= _MAX_PAGE:
        raise ValueError("limit must be 1..100")
    opened = _approved_connection(charid)
    basic = {
        "charid": charid, "location": location, "container": _LOCATIONS[location],
        "snapshot_kind": "persisted_db_not_live_memory", "client_agreement": "UNKNOWN",
        "source_revision": "UNKNOWN", "source_attested": False,
        "observed_at": datetime.now(timezone.utc).isoformat(), "execution_enabled": False,
        "scope": "approved_test_character", "authorization": "supervisor_bearer_and_charid_allowlist",
    }
    if opened is None:
        return {**basic, "configured": False, "status": "UNAVAILABLE", "complete": False,
                "items": [], "row_count": 0, "total_rows": None, "has_more": None, "next_cursor": None}
    conn, db = opened
    try:
        db.execute("SELECT charid FROM chars WHERE charid = %s", (charid,))
        exists = db.fetchone() is not None
        if not exists:
            conn.rollback()
            return {**basic, "configured": True, "status": "UNKNOWN_CHARACTER", "complete": False,
                    "items": [], "row_count": 0, "total_rows": None, "has_more": None, "next_cursor": None}
        db.execute("SELECT COUNT(*) AS n FROM char_inventory WHERE charid = %s AND location = %s", (charid, location))
        count_row = db.fetchone()
        total = int(count_row["n"] if isinstance(count_row, dict) else count_row[0])
        db.execute("SELECT location, slot, itemId, quantity, extra FROM char_inventory "
                   "WHERE charid = %s AND location = %s ORDER BY slot LIMIT %s OFFSET %s",
                   (charid, location, limit + 1, cursor))
        rows = db.fetchall()
        conn.rollback()
    except Exception as exc:
        conn.rollback()
        raise RuntimeError("inventory observation unavailable (database read failed)") from exc
    finally:
        db.close()
        conn.close()
    selected = rows[:limit]
    items = []
    for row in selected:
        location_value, slot, item_id, quantity, extra = (
            (row["location"], row["slot"], row["itemId"], row["quantity"], row["extra"])
            if isinstance(row, dict) else row
        )
        raw = bytes(extra) if extra is not None else None
        if raw is not None and len(raw) > _MAX_EXTRA_BYTES:
            return {**basic, "configured": True, "status": "INCOMPLETE_OVERSIZED_EXTRA",
                    "complete": False, "items": [], "row_count": 0, "total_rows": total,
                    "has_more": None, "next_cursor": None, "truncated": True,
                    "limit": limit, "page_offset": cursor, "max_extra_bytes": _MAX_EXTRA_BYTES}
        if sum(len(item["extra_base64"] or "") for item in items) + (4 * ((len(raw) + 2) // 3) if raw is not None else 0) > _MAX_RESPONSE_EXTRA_BYTES:
            return {**basic, "configured": True, "status": "INCOMPLETE_RESPONSE_BUDGET",
                    "complete": False, "items": [], "row_count": 0, "total_rows": total,
                    "has_more": None, "next_cursor": None, "truncated": True,
                    "limit": limit, "page_offset": cursor, "max_response_extra_bytes": _MAX_RESPONSE_EXTRA_BYTES}
        items.append({
            "location": int(location_value), "slot": int(slot), "itemId": int(item_id),
            "quantity": int(quantity), "extra_base64": base64.b64encode(raw).decode("ascii") if raw is not None else None,
            "extra_present": raw is not None,
            "furnishing_installed": "UNKNOWN", "augment_decode": "UNSUPPORTED",
        })
    inconsistent = (cursor > total or (cursor < total and not selected) or
                    cursor + len(selected) > total or
                    (len(rows) > limit and cursor + limit >= total))
    if inconsistent:
        return {**basic, "configured": True, "status": "INCOMPLETE_INCONSISTENT_PAGE",
                "complete": False, "items": [], "row_count": 0, "total_rows": total,
                "has_more": None, "next_cursor": None, "truncated": True}
    has_more = cursor + len(selected) < total or len(rows) > limit
    complete = cursor == 0 and not has_more and len(selected) == total
    return {**basic, "configured": True, "status": "COMPLETE" if complete else "INCOMPLETE",
            "complete": complete, "items": items, "row_count": len(items), "total_rows": total,
            "has_more": has_more, "next_cursor": cursor + len(items) if has_more else None,
            "page_offset": cursor, "limit": limit, "truncated": has_more,
            "furnishing_metadata": "UNSUPPORTED_UNTIL_SOURCE_VERIFIED",
            "consistency": "single_read_only_transaction_not_live_memory"}
