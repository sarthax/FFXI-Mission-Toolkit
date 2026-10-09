"""Capture integrity, provenance, lineage, and health services."""
from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone, timedelta

PARSER_VERSION = "capture-integrity-v1"

FORMAT_TARGETS = {
    "npclogger_db": (("capture_npc_entries","sqlite-row"),("capture_npc_history","sqlite-row")),
    "actionview_db": (("capture_actions","sqlite-row"),),
    "levelrange_db": (("capture_level_range","sqlite-row"),),
    "idview_simple": (("capture_events","block"),),
    "eventview_session_simple": (("capture_events","block"),),
    "eventview_session_raw": (("capture_raw_packets","block"),),
    "eventview": (("capture_eventview","block"),),
    "kitrack": (("capture_ki_events","block"),),
    "attackdelay": (("capture_attack_delay","block"),),
    "hptrack": (("capture_hp_events","line"),),
    "npclogger_lua": (("capture_npc_entries","line"),("capture_npc_path","line"),("capture_raw_packets","line")),
    "actionview_simple": (("capture_actions","line"),),
    "pathlog_csv": (("capture_npc_path","csv-row"),),
    "pc_pathlog_csv": (("capture_pc_path","csv-row"),),
    "widescan": (("capture_npc_entries","line"),("capture_level_range","line")),
    "packetlogger": (("capture_raw_packets","block"),),
    "packetdb": (("capture_raw_packets","sqlite-row"),("capture_chat_observations","sqlite-row")),
    "packeteer": (("capture_raw_packets","block"),),
    "ashita_packets": (("capture_raw_packets","line"),),
    "pcap": (("capture_structured_records","pcap-frame"),("capture_raw_packets","pcap-frame"),("capture_network_flows","pcap-flow"),("capture_network_ranges","pcap-tcp-range"),("capture_network_messages","pcap-tcp-message")),
    "pcapng": (("capture_structured_records","pcap-frame"),("capture_raw_packets","pcap-frame"),("capture_network_flows","pcap-flow"),("capture_network_ranges","pcap-tcp-range"),("capture_network_messages","pcap-tcp-message")),
    "caplog": (("capture_events","line"),("capture_hp_events","line"),("capture_eventview","line"),("capture_caplog_chat","line"),("capture_chat_observations","line")),
    "windower_logger": (("capture_chat_observations","line"),),
    "NPCLogger table/database Lua": (("capture_npc_entries","line"),("capture_npc_path","line"),("capture_raw_packets","line")),
    "EventView/IDView packet log": (("capture_events","block"),("capture_eventview","block")),
    "HPTrack": (("capture_hp_events","line"),),
    "KITrack": (("capture_ki_events","block"),),
    "PacketLogger/PacketViewer raw hex dump": (("capture_raw_packets","block"),),
    "CapLog": (("capture_events","line"),("capture_hp_events","line"),("capture_eventview","line"),("capture_caplog_chat","line"),("capture_chat_observations","line")),
    "missiontrack": (("capture_structured_records","block"),),
    "shopstock_buy_db": (("capture_structured_records","sqlite-row"),),
    "shopstock_sell_db": (("capture_structured_records","sqlite-row"),),
    "guildstock_db": (("capture_structured_records","sqlite-row"),),
    "weathertrack_db": (("capture_structured_records","sqlite-row"),),
    "poitrack_db": (("capture_structured_records","sqlite-row"),),
    "spawntrack_csv": (("capture_structured_records","csv-row"),),
    "checkparam_csv": (("capture_structured_records","csv-row"),),
    "crafttrack_csv": (("capture_structured_records","csv-row"),),
    "conquesttrack_csv": (("capture_structured_records","csv-row"),),
    "stattrack_csv": (("capture_structured_records","csv-row"),),
    "puppet_stattrack_csv": (("capture_structured_records","csv-row"),),
    "pricelog_simple": (("capture_structured_records","block"),),
    "pricelog_lua": (("capture_structured_records","block"),),
}


def init_db(con: sqlite3.Connection) -> None:
    con.executescript("""
        CREATE TABLE IF NOT EXISTS capture_source_manifest (
            capture_id INTEGER NOT NULL,
            filename TEXT NOT NULL,
            sha256 TEXT NOT NULL,
            byte_size INTEGER NOT NULL,
            format_detected TEXT,
            parser_name TEXT,
            parser_version TEXT,
            row_count INTEGER,
            ingest_status TEXT NOT NULL,
            error TEXT,
            ingested_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY(capture_id, filename)
        );
        CREATE INDEX IF NOT EXISTS idx_capture_manifest_hash
            ON capture_source_manifest(sha256);
        CREATE TABLE IF NOT EXISTS capture_ingest_lineage (
            capture_id INTEGER NOT NULL,
            filename TEXT NOT NULL,
            target_table TEXT NOT NULL,
            parser_name TEXT,
            parser_version TEXT,
            locator_basis TEXT NOT NULL,
            row_count INTEGER,
            details_json TEXT NOT NULL DEFAULT '{}',
            PRIMARY KEY(capture_id, filename, target_table)
        );
        CREATE INDEX IF NOT EXISTS idx_capture_lineage_target
            ON capture_ingest_lineage(capture_id,target_table);
        CREATE TABLE IF NOT EXISTS capture_row_locators (
            capture_id INTEGER NOT NULL,
            filename TEXT NOT NULL,
            target_table TEXT NOT NULL,
            row_key TEXT NOT NULL,
            source_sha256 TEXT,
            locator_basis TEXT NOT NULL,
            start_line INTEGER,
            end_line INTEGER,
            start_offset INTEGER,
            end_offset INTEGER,
            details_json TEXT NOT NULL DEFAULT '{}',
            PRIMARY KEY(capture_id,filename,target_table,row_key)
        );
        CREATE INDEX IF NOT EXISTS idx_capture_row_locator_target
            ON capture_row_locators(capture_id,target_table);
        CREATE TABLE IF NOT EXISTS capture_source_artifacts (
            capture_id INTEGER NOT NULL,
            source_id TEXT NOT NULL,
            filename TEXT NOT NULL,
            sha256 TEXT NOT NULL,
            byte_size INTEGER NOT NULL,
            format_detected TEXT,
            parser_name TEXT,
            parser_version TEXT,
            row_count INTEGER,
            ingest_status TEXT NOT NULL,
            error TEXT,
            observed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY(capture_id,source_id)
        );
        CREATE INDEX IF NOT EXISTS idx_capture_source_artifact_hash
            ON capture_source_artifacts(sha256);
        CREATE INDEX IF NOT EXISTS idx_capture_source_artifact_name
            ON capture_source_artifacts(capture_id,filename);
        CREATE TABLE IF NOT EXISTS capture_content_manifest (
            capture_id INTEGER PRIMARY KEY,
            sha256 TEXT,
            file_count INTEGER NOT NULL DEFAULT 0,
            total_bytes INTEGER NOT NULL DEFAULT 0,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_capture_content_manifest_hash
            ON capture_content_manifest(sha256);
    """)
    con.commit()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def parser_targets(format_detected: str | None):
    return FORMAT_TARGETS.get(format_detected or "", ())


def _source_artifact_id(
    filename: str,
    digest: str,
    parser_name: str | None,
    parser_version: str,
    ingest_status: str,
) -> str:
    payload = "|".join([
        filename, digest, parser_name or "", parser_version, ingest_status,
    ])
    return "capture-source:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]


def recompute_content_manifest(con: sqlite3.Connection, capture_id: int) -> dict:
    """Compute path-independent identity from the CURRENT per-filename source manifest.

    Filenames are intentionally excluded from the fingerprint so moved/renamed/re-zipped copies
    of the same evidence set resolve to the same capture content identity. Auxiliary metadata
    (manifest.txt/OS cruft) is excluded; recognized, unrecognized, and failed primary inputs remain
    part of the identity so unexplained extra evidence cannot silently collapse into a duplicate.
    """
    init_db(con)
    rows = con.execute(
        """SELECT sha256,byte_size
           FROM capture_source_manifest
           WHERE capture_id=? AND ingest_status<>'AUXILIARY'
           ORDER BY sha256,byte_size""",
        (capture_id,),
    ).fetchall()
    payload = "\n".join(f"{digest}\0{int(size)}" for digest, size in rows).encode("utf-8")
    digest = hashlib.sha256(payload).hexdigest() if rows else None
    total_bytes = sum(int(size) for _, size in rows)
    con.execute(
        """INSERT OR REPLACE INTO capture_content_manifest
           (capture_id,sha256,file_count,total_bytes,updated_at)
           VALUES (?,?,?,?,CURRENT_TIMESTAMP)""",
        (capture_id,digest,len(rows),total_bytes),
    )
    return {
        "capture_id": capture_id,
        "sha256": digest,
        "file_count": len(rows),
        "total_bytes": total_bytes,
    }


def content_identity(con: sqlite3.Connection, capture_id: int) -> dict | None:
    init_db(con)
    row = con.execute(
        """SELECT capture_id,sha256,file_count,total_bytes,updated_at
           FROM capture_content_manifest WHERE capture_id=?""",
        (capture_id,),
    ).fetchone()
    if not row:
        return None
    return {
        "capture_id": row[0], "sha256": row[1], "file_count": row[2],
        "total_bytes": row[3], "updated_at": row[4],
    }


def _table_exists(con: sqlite3.Connection, table: str) -> bool:
    return bool(con.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone())


def _bounded_rows(con: sqlite3.Connection, sql: str, args: tuple, limit: int = 5000):
    return con.execute(sql + " LIMIT ?", args + (limit,)).fetchall()


def _capture_overlap_tokens(con: sqlite3.Connection, capture_id: int) -> dict[str, set[str]]:
    """Build conservative normalized evidence tokens for partial-session overlap checks.

    Timestamps are deliberately excluded so the same underlying session can still correlate when
    two tools started at different wall-clock offsets. Tokens are capped per family to bound GUI
    health checks on very large captures.
    """
    families: dict[str, set[str]] = {}

    def add(name: str, rows) -> None:
        tokens = set()
        for row in rows:
            payload = json.dumps(list(row), sort_keys=False, separators=(",", ":"), default=str)
            tokens.add(hashlib.sha256(payload.encode("utf-8")).hexdigest())
        if tokens:
            families[name] = tokens

    if _table_exists(con, "capture_events"):
        add("events", _bounded_rows(
            con,
            """SELECT zone_db,direction,opcode,opcode_name,entity_id,event_hex,option,message_id,params_raw
               FROM capture_events WHERE capture_id=? ORDER BY zone_db,seq""",
            (capture_id,),
        ))
    if _table_exists(con, "capture_eventview"):
        add("eventview", _bounded_rows(
            con,
            """SELECT zone_db,direction,opcode,packet_class,gp_command,entity_id,mes_num,message_number,fields_json
               FROM capture_eventview WHERE capture_id=? ORDER BY zone_db,seq""",
            (capture_id,),
        ))
    if _table_exists(con, "capture_ki_events"):
        add("key_items", _bounded_rows(
            con,
            """SELECT event_type,keyitem_id,keyitem_name,zone_name,x,y,z
               FROM capture_ki_events WHERE capture_id=? ORDER BY seq""",
            (capture_id,),
        ))
    if _table_exists(con, "capture_actions"):
        add("actions", _bounded_rows(
            con,
            """SELECT actor,actor_name,action_type,animation,category,message,name
               FROM capture_actions WHERE capture_id=? ORDER BY action_key""",
            (capture_id,),
        ))
    if _table_exists(con, "capture_raw_packets"):
        # Raw packet bytes are powerful overlap evidence but can contain common heartbeat/status
        # packets. Keep only non-trivial payloads and still require strong containment below.
        rows = _bounded_rows(
            con,
            """SELECT direction,opcode,raw_hex
               FROM capture_raw_packets
               WHERE capture_id=? AND LENGTH(COALESCE(raw_hex,''))>=24
               ORDER BY seq""",
            (capture_id,),
        )
        add("raw_packets", rows)
    return families


def find_partial_capture_overlaps(con: sqlite3.Connection, capture_id: int) -> list[dict]:
    """Find strong partial/overlapping-session candidates without declaring identity.

    A candidate must either share evidence from at least two normalized families, or have a large
    and highly-contained raw-packet overlap by itself. This intentionally favors false negatives
    over false positives because repeated FFXI packets/events can occur across unrelated sessions.
    """
    target = _capture_overlap_tokens(con, capture_id)
    if not target:
        return []
    target_ids = set().union(*target.values()) if target else set()
    if not target_ids:
        return []

    capture_rows = con.execute(
        "SELECT capture_id,capture_label,source_path FROM captures WHERE capture_id<>? ORDER BY capture_id",
        (capture_id,),
    ).fetchall()
    out = []
    for other_id, label, source_path in capture_rows:
        other = _capture_overlap_tokens(con, int(other_id))
        if not other:
            continue
        shared_by_family = {}
        for family in sorted(set(target) & set(other)):
            shared = len(target[family] & other[family])
            if shared:
                shared_by_family[family] = shared
        if not shared_by_family:
            continue

        target_total = sum(len(v) for v in target.values())
        other_total = sum(len(v) for v in other.values())
        shared_total = sum(shared_by_family.values())
        family_count = len(shared_by_family)
        target_containment = shared_total / max(target_total, 1)
        other_containment = shared_total / max(other_total, 1)

        raw_shared = shared_by_family.get("raw_packets", 0)
        multi_family_strong = (
            family_count >= 2 and shared_total >= 4 and
            max(target_containment, other_containment) >= 0.20
        )
        raw_only_strong = (
            family_count == 1 and raw_shared >= 20 and
            min(target_containment, other_containment) >= 0.50
        )
        if not (multi_family_strong or raw_only_strong):
            continue

        out.append({
            "capture_id": int(other_id),
            "capture_label": label,
            "source_path": source_path,
            "shared_by_family": shared_by_family,
            "shared_total": shared_total,
            "target_observations": target_total,
            "other_observations": other_total,
            "target_containment": round(target_containment, 4),
            "other_containment": round(other_containment, 4),
            "basis": "normalized_runtime_evidence",
        })
    out.sort(key=lambda r: (-r["shared_total"], -max(r["target_containment"], r["other_containment"]), r["capture_id"]))
    return out


def _parse_locator_timestamp(value: str | None):
    if not value:
        return None
    value = str(value).strip()
    for fmt, kind in (
        ("%Y-%m-%d %H:%M:%S", "datetime"),
        ("%Y-%m-%dT%H:%M:%S", "datetime"),
        ("%H:%M:%S", "time"),
    ):
        try:
            return datetime.strptime(value, fmt), kind
        except ValueError:
            pass
    return None


def clock_discontinuities(con: sqlite3.Connection, capture_id: int) -> dict:
    """Inspect timestamp-bearing exact locators in original physical source order.

    Midnight rollover for time-only clocks is treated as normal. Backward jumps larger than one
    second, and timestamp-format changes inside the same source file, are reported for review but
    never auto-corrected.
    """
    if not _table_exists(con, "capture_row_locators"):
        return {"status": "UNKNOWN", "streams": 0, "timestamped_rows": 0, "discontinuities": []}

    rows = con.execute(
        """SELECT filename,start_line,start_offset,details_json
           FROM capture_row_locators
           WHERE capture_id=?
           ORDER BY filename,COALESCE(start_line,2147483647),COALESCE(start_offset,9223372036854775807)""",
        (capture_id,),
    ).fetchall()

    by_file: dict[str, list[dict]] = {}
    for filename, start_line, start_offset, details_json in rows:
        try:
            details = json.loads(details_json or "{}")
        except json.JSONDecodeError:
            details = {}
        ts_raw = details.get("timestamp")
        parsed = _parse_locator_timestamp(ts_raw)
        if not parsed:
            continue
        dt, kind = parsed
        by_file.setdefault(filename, []).append({
            "raw": ts_raw, "dt": dt, "kind": kind,
            "line": start_line, "offset": start_offset,
        })

    discontinuities = []
    timestamped_rows = 0
    for filename, stream in by_file.items():
        timestamped_rows += len(stream)
        prev = None
        day_offset = 0
        prev_kind = None
        for item in stream:
            dt = item["dt"]
            kind = item["kind"]
            if prev_kind is not None and kind != prev_kind:
                discontinuities.append({
                    "filename": filename,
                    "type": "clock_format_change",
                    "previous_kind": prev_kind,
                    "current_kind": kind,
                    "line": item["line"],
                    "timestamp": item["raw"],
                })
                prev = None
                day_offset = 0
            if kind == "time":
                current_seconds = dt.hour * 3600 + dt.minute * 60 + dt.second
                current = current_seconds + day_offset
                if prev is not None and current < prev:
                    # A late-night -> early-morning transition is a legitimate midnight rollover.
                    prev_day_seconds = prev % 86400
                    if prev_day_seconds >= 20 * 3600 and current_seconds <= 4 * 3600:
                        day_offset += 86400
                        current = current_seconds + day_offset
                    elif prev - current > 1:
                        discontinuities.append({
                            "filename": filename,
                            "type": "backward_clock_jump",
                            "line": item["line"],
                            "previous_seconds": prev,
                            "current_seconds": current,
                            "delta_seconds": round(current - prev, 3),
                            "timestamp": item["raw"],
                        })
                prev = current
            else:
                current = dt.replace(tzinfo=None)
                if isinstance(prev, datetime) and current < prev - timedelta(seconds=1):
                    discontinuities.append({
                        "filename": filename,
                        "type": "backward_clock_jump",
                        "line": item["line"],
                        "previous_timestamp": prev.isoformat(sep=" "),
                        "current_timestamp": current.isoformat(sep=" "),
                        "delta_seconds": (current - prev).total_seconds(),
                        "timestamp": item["raw"],
                    })
                prev = current
            prev_kind = kind

    return {
        "status": "ISSUES" if discontinuities else ("COMPLETE" if timestamped_rows else "UNKNOWN"),
        "streams": len(by_file),
        "timestamped_rows": timestamped_rows,
        "discontinuities": discontinuities,
        "basis": "timestamp-bearing exact row locators in physical source order",
    }


def find_exact_capture_duplicates(con: sqlite3.Connection, capture_id: int) -> list[dict]:
    identity = content_identity(con, capture_id)
    if not identity or not identity.get("sha256"):
        return []
    old_factory = con.row_factory
    con.row_factory = sqlite3.Row
    try:
        rows = con.execute(
            """SELECT m.capture_id,m.sha256,m.file_count,m.total_bytes,
                      c.capture_label,c.source_path
               FROM capture_content_manifest m
               JOIN captures c ON c.capture_id=m.capture_id
               WHERE m.sha256=? AND m.capture_id<>?
               ORDER BY m.capture_id""",
            (identity["sha256"], capture_id),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        con.row_factory = old_factory


def record_source_file(
    con: sqlite3.Connection,
    capture_id: int,
    filename: str,
    data: bytes,
    *,
    format_detected: str | None,
    parser_name: str | None = None,
    row_count: int | None = None,
    error: str | None = None,
) -> dict:
    init_db(con)
    digest = sha256_bytes(data)
    if format_detected in {"manifest", "benign"}:
        status = "AUXILIARY"
    else:
        status = "FAILED" if error else ("RECOGNIZED" if format_detected else "UNRECOGNIZED")
    parser_name = parser_name or format_detected
    con.execute(
        """INSERT OR REPLACE INTO capture_source_manifest
           (capture_id,filename,sha256,byte_size,format_detected,parser_name,parser_version,
            row_count,ingest_status,error,ingested_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP)""",
        (capture_id,filename,digest,len(data),format_detected,parser_name,PARSER_VERSION,
         row_count,status,error),
    )
    source_id = _source_artifact_id(filename,digest,parser_name,PARSER_VERSION,status)
    con.execute(
        """INSERT OR REPLACE INTO capture_source_artifacts
           (capture_id,source_id,filename,sha256,byte_size,format_detected,parser_name,
            parser_version,row_count,ingest_status,error,observed_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP)""",
        (capture_id,source_id,filename,digest,len(data),format_detected,parser_name,
         PARSER_VERSION,row_count,status,error),
    )
    recompute_content_manifest(con,capture_id)
    con.execute(
        "DELETE FROM capture_ingest_lineage WHERE capture_id=? AND filename=?",
        (capture_id,filename),
    )
    targets = parser_targets(format_detected)
    for target_table, locator_basis in targets:
        con.execute(
            """INSERT INTO capture_ingest_lineage
               (capture_id,filename,target_table,parser_name,parser_version,locator_basis,row_count,details_json)
               VALUES (?,?,?,?,?,?,?,?)""",
            (capture_id,filename,target_table,parser_name,PARSER_VERSION,locator_basis,row_count,
             json.dumps({"source_sha256":digest,"precision":"file_to_record_family"},sort_keys=True)),
        )
    con.commit()
    return {
        "filename":filename,"sha256":digest,"byte_size":len(data),"format_detected":format_detected,
        "parser_name":parser_name,"parser_version":PARSER_VERSION,"row_count":row_count,
        "ingest_status":status,"error":error,"source_id":source_id,
        "content_manifest":content_identity(con,capture_id),
    }


def record_row_locator(
    con: sqlite3.Connection,
    capture_id: int,
    filename: str,
    target_table: str,
    row_key: str,
    locator_basis: str,
    *,
    source_sha256: str | None = None,
    start_line: int | None = None,
    end_line: int | None = None,
    start_offset: int | None = None,
    end_offset: int | None = None,
    details: dict | None = None,
) -> None:
    """Attach one normalized capture row to the exact source span that produced it.

    Parsers must only call this when their physical source format exposes deterministic row,
    line, block, or byte boundaries. Missing precision stays NULL instead of being inferred.
    """
    if not con.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='capture_row_locators'"
    ).fetchone():
        init_db(con)
    if source_sha256 is None:
        row = con.execute(
            "SELECT sha256 FROM capture_source_manifest WHERE capture_id=? AND filename=?",
            (capture_id, filename),
        ).fetchone()
        source_sha256 = row[0] if row else None
    con.execute(
        """INSERT OR REPLACE INTO capture_row_locators
           (capture_id,filename,target_table,row_key,source_sha256,locator_basis,
            start_line,end_line,start_offset,end_offset,details_json)
           VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (
            capture_id, filename, target_table, str(row_key), source_sha256, locator_basis,
            start_line, end_line, start_offset, end_offset,
            json.dumps(details or {}, sort_keys=True),
        ),
    )


def canonical_row_key(row_key) -> str:
    if isinstance(row_key, str):
        try:
            parsed = json.loads(row_key)
        except (TypeError, json.JSONDecodeError):
            return row_key
        if isinstance(parsed, (dict, list)):
            return json.dumps(parsed, sort_keys=True)
        return row_key
    if isinstance(row_key, (dict, list)):
        return json.dumps(row_key, sort_keys=True)
    return str(row_key)


def find_row_locators(
    con: sqlite3.Connection,
    capture_id: int,
    target_table: str,
    row_key,
) -> list[dict]:
    """Return exact source locator(s) for one normalized capture row.

    Multiple rows are preserved when an older database still contains overlapping locator
    ownership; callers should surface that ambiguity rather than silently choosing one.
    """
    if not con.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='capture_row_locators'"
    ).fetchone():
        return []
    key = canonical_row_key(row_key)
    old_factory = con.row_factory
    con.row_factory = sqlite3.Row
    try:
        rows = con.execute(
            """SELECT capture_id,filename,target_table,row_key,source_sha256,locator_basis,
                      start_line,end_line,start_offset,end_offset,details_json
               FROM capture_row_locators
               WHERE capture_id=? AND target_table=? AND row_key=?
               ORDER BY filename""",
            (int(capture_id), target_table, key),
        ).fetchall()
        out = []
        for row in rows:
            item = dict(row)
            try:
                item["details"] = json.loads(item.pop("details_json") or "{}")
            except json.JSONDecodeError:
                item["details"] = {}
                item.pop("details_json", None)
            out.append(item)
        return out
    finally:
        con.row_factory = old_factory


def schema_capture_tables(con: sqlite3.Connection) -> list[str]:
    tables=[]
    for (name,) in con.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall():
        if name.startswith("sqlite_") or name == "captures":
            continue
        try:
            cols={row[1] for row in con.execute(f'PRAGMA table_info("{name}")').fetchall()}
        except sqlite3.DatabaseError:
            continue
        if "capture_id" in cols:
            tables.append(name)
    return tables


def delete_capture_rows(con: sqlite3.Connection, capture_id: int, explicit_tables) -> dict:
    """Delete every capture-owned row, including future capture_id tables omitted from registry."""
    discovered=set(schema_capture_tables(con))
    tables=sorted(discovered | set(explicit_tables))
    counts={}
    for table in tables:
        exists=con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",(table,)).fetchone()
        if not exists:
            continue
        cols={r[1] for r in con.execute(f'PRAGMA table_info("{table}")').fetchall()}
        if "capture_id" not in cols:
            continue
        cur=con.execute(f'DELETE FROM "{table}" WHERE capture_id=?',(capture_id,))
        counts[table]=cur.rowcount
    cur=con.execute("DELETE FROM captures WHERE capture_id=?",(capture_id,))
    counts["captures"]=cur.rowcount
    con.commit()
    return counts


def _table_count(con, table, capture_id):
    if not con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",(table,)).fetchone():
        return 0
    return con.execute(f'SELECT COUNT(*) FROM "{table}" WHERE capture_id=?',(capture_id,)).fetchone()[0]


def capture_health(con: sqlite3.Connection, capture_id: int) -> dict:
    init_db(con)
    con.row_factory=sqlite3.Row
    cap=con.execute("SELECT * FROM captures WHERE capture_id=?",(capture_id,)).fetchone()
    if not cap:
        return {"status":"NOT_FOUND","capture_id":capture_id}

    manifest=[dict(r) for r in con.execute(
        "SELECT * FROM capture_source_manifest WHERE capture_id=? ORDER BY filename",(capture_id,)
    ).fetchall()]
    source_files=[dict(r) for r in con.execute(
        "SELECT * FROM capture_source_files WHERE capture_id=? ORDER BY filename",(capture_id,)
    ).fetchall()] if con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='capture_source_files'").fetchone() else []

    total=len(manifest) or len(source_files)
    recognized=sum(1 for r in manifest if r["ingest_status"]=="RECOGNIZED")
    failed=sum(1 for r in manifest if r["ingest_status"]=="FAILED")
    unrecognized=sum(1 for r in manifest if r["ingest_status"]=="UNRECOGNIZED")
    auxiliary=sum(1 for r in manifest if r["ingest_status"]=="AUXILIARY")
    hashed=sum(1 for r in manifest if r.get("sha256"))
    parser_lineage=_table_count(con,"capture_ingest_lineage",capture_id)
    exact_row_locators=_table_count(con,"capture_row_locators",capture_id)

    raw_packets=_table_count(con,"capture_raw_packets",capture_id)
    eventview=_table_count(con,"capture_eventview",capture_id)
    video_obs=_table_count(con,"capture_video_observations",capture_id)
    npc_entries=_table_count(con,"capture_npc_entries",capture_id)
    npc_hist=_table_count(con,"capture_npc_history",capture_id)
    key_evidence=_table_count(con,"capture_key_evidence",capture_id)
    anchors=_table_count(con,"capture_alignment_anchors",capture_id)
    structured_records=_table_count(con,"capture_structured_records",capture_id)

    directions=[]
    if raw_packets:
        directions=[r[0] for r in con.execute(
            "SELECT DISTINCT direction FROM capture_raw_packets WHERE capture_id=? ORDER BY direction",
            (capture_id,),
        ).fetchall() if r[0]]

    capture_identity=content_identity(con,capture_id)
    exact_duplicates=find_exact_capture_duplicates(con,capture_id)
    partial_overlaps=find_partial_capture_overlaps(con,capture_id)
    clock_diag=clock_discontinuities(con,capture_id)

    duplicate_hashes=[]
    for row in con.execute(
        """SELECT sha256,COUNT(DISTINCT capture_id) AS captures
           FROM capture_source_manifest
           WHERE sha256 IN (SELECT sha256 FROM capture_source_manifest WHERE capture_id=?)
           GROUP BY sha256 HAVING COUNT(DISTINCT capture_id)>1""",(capture_id,)
    ).fetchall():
        duplicate_hashes.append({"sha256":row[0],"capture_count":row[1]})

    dimensions={}
    dimensions["source_integrity"]={
        "status":"COMPLETE" if total and hashed==total else ("PARTIAL" if total else "UNKNOWN"),
        "files":total,"hashed":hashed,
    }
    dimensions["parser_coverage"]={
        "status":"ISSUES" if failed or unrecognized else ("COMPLETE" if total and recognized==total else ("PARTIAL" if total else "UNKNOWN")),
        "recognized":recognized,"failed":failed,"unrecognized":unrecognized,"auxiliary":auxiliary,
    }
    dimensions["lineage"]={
        "status":"COMPLETE" if total and parser_lineage>=recognized else ("PARTIAL" if parser_lineage else "UNKNOWN"),
        "lineage_records":parser_lineage,
        "exact_row_locators":exact_row_locators,
        "precision":"exact_rows_available" if exact_row_locators else "file_to_record_family",
    }
    dimensions["client_context"]={
        "status":"COMPLETE" if cap["client_build"] else "UNKNOWN",
        "client_build":cap["client_build"],"capturer":cap["capturer"],"is_retail":cap["is_retail"],
    }
    dimensions["packet_evidence"]={
        "status":"COMPLETE" if raw_packets and len(directions)>=2 else ("PARTIAL" if raw_packets or eventview or video_obs else "UNKNOWN"),
        "raw_packets":raw_packets,"eventview":eventview,"video_ocr":video_obs,"directions":directions,
    }
    dimensions["entity_evidence"]={
        "status":"COMPLETE" if npc_entries and npc_hist else ("PARTIAL" if npc_entries else "UNKNOWN"),
        "npc_entries":npc_entries,"history_rows":npc_hist,
    }
    structured_families=[]
    if structured_records:
        structured_families=[r[0] for r in con.execute(
            "SELECT DISTINCT family FROM capture_structured_records WHERE capture_id=? ORDER BY family",
            (capture_id,),
        ).fetchall()]
    dimensions["structured_logger_evidence"]={
        "status":"COMPLETE" if structured_records else "UNKNOWN",
        "records":structured_records,
        "families":structured_families,
        "basis":"optional capture/logger families; absence is not a capture-quality failure",
    }
    dimensions["timeline_alignment"]={
        "status":"COMPLETE" if anchors>=2 else ("PARTIAL" if anchors==1 else "UNKNOWN"),
        "anchors":anchors,"key_evidence":key_evidence,
    }
    dimensions["duplicate_source"]={
        "status":"ISSUES" if duplicate_hashes else "COMPLETE",
        "duplicate_hashes":duplicate_hashes,
    }
    dimensions["capture_identity"]={
        "status":"ISSUES" if exact_duplicates else ("COMPLETE" if capture_identity and capture_identity.get("sha256") else "UNKNOWN"),
        "sha256":capture_identity.get("sha256") if capture_identity else None,
        "file_count":capture_identity.get("file_count") if capture_identity else 0,
        "total_bytes":capture_identity.get("total_bytes") if capture_identity else 0,
        "exact_duplicates":exact_duplicates,
        "basis":"path-independent current non-auxiliary source set",
    }
    dimensions["session_overlap"]={
        "status":"PARTIAL" if partial_overlaps else ("COMPLETE" if capture_identity else "UNKNOWN"),
        "candidates":partial_overlaps,
        "basis":"conservative normalized-runtime-evidence containment; candidates require review",
    }
    dimensions["clock_continuity"]=clock_diag

    issue_count=sum(1 for d in dimensions.values() if d["status"]=="ISSUES")
    partial_count=sum(1 for d in dimensions.values() if d["status"]=="PARTIAL")
    overall="ISSUES" if issue_count else ("PARTIAL" if partial_count else "COMPLETE")
    if not total and not (raw_packets or eventview or video_obs or npc_entries):
        overall="UNKNOWN"

    return {
        "status":"OK","capture_id":capture_id,"overall":overall,
        "dimensions":dimensions,"source_manifest":manifest,
        "content_identity":capture_identity,
        "source_artifact_count":_table_count(con,"capture_source_artifacts",capture_id),
        "generated_at":datetime.now(timezone.utc).isoformat(),
    }
