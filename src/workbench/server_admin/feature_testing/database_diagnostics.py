"""Fixed-query DSP inventory snapshot for explicitly approved disposable characters.

Requires a dedicated SELECT-only MySQL user. No user-authored SQL is accepted.
"""
from __future__ import annotations
import os
import re


class DisallowedTestCharacter(ValueError):
    """Only an invalid caller-supplied character scope merits HTTP 400."""


def _approved_connection(charid: int):
    """Validate the approved-character allowlist and DB settings; return (conn, cursor) or None if unconfigured."""
    allowed = {int(s.strip()) for s in os.environ.get("MISSION_TOOLKIT_SUPERVISOR_TEST_CHARIDS", "").split(",") if s.strip().isdigit()}
    if not isinstance(charid, int) or charid <= 0 or charid not in allowed:
        raise DisallowedTestCharacter("character not approved for supervisor diagnostics")
    user = os.environ.get("MISSION_TOOLKIT_SUPERVISOR_DB_USER")
    password = os.environ.get("MISSION_TOOLKIT_SUPERVISOR_DB_PASSWORD")
    database = os.environ.get("MISSION_TOOLKIT_SUPERVISOR_DB_NAME")
    if not all((user, password, database)):
        return None
    port = int(os.environ.get("MISSION_TOOLKIT_SUPERVISOR_DB_PORT", "3306"))
    if not 1 <= port <= 65535:
        raise ValueError("invalid database port")
    conn, cursor = _open(user, password, database, port)
    try:
        cursor.execute("SET TRANSACTION READ ONLY")
        cursor.execute("START TRANSACTION")
    except Exception:
        # Setup can fail after opening the socket: never leak a cursor or
        # connection, and preserve the original database error for the
        # caller to classify or sanitize.
        for cleanup in (conn.rollback, cursor.close, conn.close):
            try:
                cleanup()
            except Exception:
                pass
        raise
    return conn, cursor


def inventory_snapshot(charid: int) -> dict:
    opened = _approved_connection(charid)
    if opened is None:
        return {"configured": False, "charid": charid, "items": []}
    conn, cursor = opened
    try:
        cursor.execute(
            "SELECT location, slot, itemId, quantity FROM char_inventory WHERE charid = %s ORDER BY location, slot LIMIT 100",
            (charid,),
        )
        items = cursor.fetchall()
        conn.rollback()
    finally:
        cursor.close()
        conn.close()
    return {"configured": True, "charid": charid, "items": items,
            "limit": 100, "snapshot_kind": "persisted_db_not_live_memory"}


_TABLE_BYTES = 128          # keyitems_table_t = bitset<512> keyList (64 B) + bitset<512> seenList (64 B)
_TABLES = 7                 # keyitems_t holds 7 tables (src/common/mmo.h); key item id = table*512 + bit
_VAR_NAME = re.compile(r"[A-Za-z0-9_\[\]]{1,30}")


def decode_keyitems(blob) -> dict:
    """Decode chars.keyitems (little-endian bitset words) into owned and seen key item ids."""
    data = bytes(blob or b"")
    owned, seen = [], []
    for table in range(_TABLES):
        base = table * _TABLE_BYTES
        for bit in range(512):
            byte, mask = bit // 8, 1 << (bit % 8)
            if base + byte < len(data) and data[base + byte] & mask:
                owned.append(table * 512 + bit)
            if base + 64 + byte < len(data) and data[base + 64 + byte] & mask:
                seen.append(table * 512 + bit)
    return {"owned": owned, "seen": seen, "blob_bytes": len(data), "expected_bytes": _TABLES * _TABLE_BYTES}


def key_items_snapshot(charid: int) -> dict:
    opened = _approved_connection(charid)
    if opened is None:
        return {"configured": False, "charid": charid, "owned": [], "seen": []}
    conn, cursor = opened
    try:
        cursor.execute("SELECT keyitems FROM chars WHERE charid = %s", (charid,))
        row = cursor.fetchone()
        conn.rollback()
    finally:
        cursor.close()
        conn.close()
    if not row:
        raise ValueError("character not found")
    value = row["keyitems"] if isinstance(row, dict) else row[0]
    return {"configured": True, "charid": charid, **decode_keyitems(value),
            "snapshot_kind": "persisted_db_not_live_memory"}


def char_vars_snapshot(charid: int, names) -> dict:
    """Read named char_vars only: fixed query, bounded name list, no wildcards."""
    names = [str(n) for n in names][:50]
    if not names or any(not _VAR_NAME.fullmatch(n) for n in names):
        raise ValueError("provide 1-50 variable names (letters, digits, _, [ ])")
    opened = _approved_connection(charid)
    if opened is None:
        return {"configured": False, "charid": charid, "vars": {}}
    conn, cursor = opened
    try:
        marks = ",".join(["%s"] * len(names))
        cursor.execute(f"SELECT varname, value FROM char_vars WHERE charid = %s AND varname IN ({marks})", (charid, *names))
        rows = cursor.fetchall()
        conn.rollback()
    finally:
        cursor.close()
        conn.close()
    found = {(r["varname"] if isinstance(r, dict) else r[0]): (r["value"] if isinstance(r, dict) else r[1]) for r in rows}
    return {"configured": True, "charid": charid, "vars": {n: found.get(n) for n in names},
            "snapshot_kind": "persisted_db_not_live_memory"}


def _open(user, password, database, port):
    """Connect with PyMySQL when present, else the MySQL Connector the Toolkit already ships."""
    try:
        import pymysql
    except ImportError:
        pymysql = None
    if pymysql is not None:
        conn = pymysql.connect(host="127.0.0.1", port=port, user=user, password=password,
                               database=database, connect_timeout=2, read_timeout=2,
                               write_timeout=2, autocommit=False,
                               cursorclass=pymysql.cursors.DictCursor)
        try:
            return conn, conn.cursor()
        except Exception:
            try:
                conn.close()
            except Exception:
                pass
            raise
    try:
        import mysql.connector
    except ImportError as exc:
        raise RuntimeError("no MySQL driver installed (PyMySQL or mysql-connector-python)") from exc
    conn = mysql.connector.connect(host="127.0.0.1", port=port, user=user, password=password,
                                   database=database, connection_timeout=2, autocommit=False)
    try:
        return conn, conn.cursor(dictionary=True)
    except Exception:
        try:
            conn.close()
        except Exception:
            pass
        raise
