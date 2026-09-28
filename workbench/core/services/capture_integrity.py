"""Capture integrity, provenance, lineage, and health services."""
from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone

PARSER_VERSION = "capture-integrity-v1"

FORMAT_TARGETS = {
    "npclogger_db": (("capture_npc_entries","sqlite-row"),("capture_npc_history","sqlite-row")),
    "actionview_db": (("capture_actions","sqlite-row"),),
    "levelrange_db": (("capture_level_range","sqlite-row"),),
    "idview_simple": (("capture_events","block"),),
    "eventview": (("capture_eventview","block"),),
    "kitrack": (("capture_ki_events","line"),),
    "attackdelay": (("capture_attack_delay","line"),),
    "hptrack": (("capture_hp_events","line"),),
    "npclogger_lua": (("capture_npc_entries","line"),("capture_npc_path","line")),
    "actionview_simple": (("capture_actions","line"),),
    "pathlog_csv": (("capture_npc_path","csv-row"),),
    "pc_pathlog_csv": (("capture_pc_path","csv-row"),),
    "widescan": (("capture_npc_entries","line"),),
    "packetlogger": (("capture_raw_packets","block"),),
    "caplog": (("capture_events","line"),("capture_hp_events","line"),("capture_eventview","line"),("capture_caplog_chat","line")),
    "NPCLogger table/database Lua": (("capture_npc_entries","line"),("capture_npc_path","line")),
    "EventView/IDView packet log": (("capture_events","block"),("capture_eventview","block")),
    "HPTrack": (("capture_hp_events","line"),),
    "KITrack": (("capture_ki_events","line"),),
    "PacketLogger/PacketViewer raw hex dump": (("capture_raw_packets","block"),),
    "CapLog": (("capture_events","line"),("capture_hp_events","line"),("capture_eventview","line"),("capture_caplog_chat","line")),
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

    directions=[]
    if raw_packets:
        directions=[r[0] for r in con.execute(
            "SELECT DISTINCT direction FROM capture_raw_packets WHERE capture_id=? ORDER BY direction",
            (capture_id,),
        ).fetchall() if r[0]]

    capture_identity=content_identity(con,capture_id)
    exact_duplicates=find_exact_capture_duplicates(con,capture_id)

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
