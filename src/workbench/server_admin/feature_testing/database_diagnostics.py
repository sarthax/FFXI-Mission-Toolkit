"""Fixed-query DSP inventory snapshot for explicitly approved disposable characters.

Requires a dedicated SELECT-only MySQL user. No user-authored SQL is accepted.
"""
from __future__ import annotations
import os


def inventory_snapshot(charid: int) -> dict:
    allowed = {int(s.strip()) for s in os.environ.get("MISSION_TOOLKIT_SUPERVISOR_TEST_CHARIDS", "").split(",") if s.strip().isdigit()}
    if not isinstance(charid, int) or charid <= 0 or charid not in allowed:
        raise ValueError("character not approved for supervisor diagnostics")
    user = os.environ.get("MISSION_TOOLKIT_SUPERVISOR_DB_USER")
    password = os.environ.get("MISSION_TOOLKIT_SUPERVISOR_DB_PASSWORD")
    database = os.environ.get("MISSION_TOOLKIT_SUPERVISOR_DB_NAME")
    if not all((user, password, database)):
        return {"configured": False, "charid": charid, "items": []}
    try:
        import pymysql
    except ImportError as exc:
        raise RuntimeError("optional PyMySQL dependency not installed") from exc
    port = int(os.environ.get("MISSION_TOOLKIT_SUPERVISOR_DB_PORT", "3306"))
    if not 1 <= port <= 65535:
        raise ValueError("invalid database port")
    with pymysql.connect(host="127.0.0.1", port=port, user=user, password=password,
                         database=database, connect_timeout=2, read_timeout=2,
                         write_timeout=2, autocommit=False,
                         cursorclass=pymysql.cursors.DictCursor) as conn:
        with conn.cursor() as cursor:
            cursor.execute("SET TRANSACTION READ ONLY")
            cursor.execute("START TRANSACTION")
            cursor.execute(
                "SELECT location, slot, itemId, quantity FROM char_inventory WHERE charid = %s ORDER BY location, slot LIMIT 100",
                (charid,),
            )
            items = cursor.fetchall()
        conn.rollback()
    return {"configured": True, "charid": charid, "items": items,
            "limit": 100, "snapshot_kind": "persisted_db_not_live_memory"}
