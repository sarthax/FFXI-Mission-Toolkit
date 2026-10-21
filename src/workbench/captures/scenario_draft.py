"""Read-only capture-index -> OBSERVED draft preview (Issue #1262).

This is intentionally *not* the canonical scenario schema, a packet decoder, an
oracle, an evidence importer, or an execution path. It only reads already-indexed
capture rows, preserving ambiguity and exact source locators where available.
"""
from __future__ import annotations

import re
import sqlite3

from workbench.core.contracts.capture_row_locators import find_row_locators
from workbench.runtime.interaction_reconstruction import reconstruct_interaction_candidates

_SHA256 = re.compile(r"^[0-9a-f]{64}$", re.IGNORECASE)
# Fixed, allowlisted columns and table names: never interpolate caller-supplied SQL.
_SOURCES = (
    ("capture_events",
     "zone_db,seq,direction,opcode,opcode_name,entity_id,entity_name,event_hex,option,message_id",
     "zone_db,seq", "ZONE_SEQUENCE"),
    ("capture_eventview",
     "zone_db,seq,ts,direction,opcode,packet_class,gp_command,entity_id,mes_num,message_number",
     "zone_db,seq", "ZONE_SEQUENCE"),
    ("capture_ki_events",
     "seq,ts,event_type,keyitem_id,keyitem_name,zone_name",
     "seq", "CAPTURE_TABLE_SEQUENCE"),
    ("capture_raw_packets",
     "seq,ts,direction,opcode,zone_id,is_injected,is_blocked,source_format,source_native_id",
     "seq", "CAPTURE_TABLE_SEQUENCE"),
)


def _exists(con: sqlite3.Connection, name: str) -> bool:
    return con.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone() is not None


def _source_locator(con: sqlite3.Connection, capture_id: int, table: str, key: dict) -> dict:
    """Carry locator evidence, never silently choose among conflicting sources."""
    if not _exists(con, "capture_row_locators"):
        locators = []
    else:
        locators = find_row_locators(con, capture_id, table, key)
    refs = []
    for locator in locators:
        filename = locator["filename"]
        manifest = None
        if _exists(con, "capture_source_manifest"):
            cur = con.execute(
                """SELECT sha256,parser_name,parser_version,ingest_status
                   FROM capture_source_manifest WHERE capture_id=? AND filename=?""",
                (capture_id, filename),
            )
            found = cur.fetchone()
            if found:
                manifest = dict(zip(("sha256", "parser_name", "parser_version", "ingest_status"), found))
        digest = locator.get("source_sha256")
        matched = bool(
            manifest and isinstance(digest, str)
            and _SHA256.fullmatch(digest) and manifest["sha256"] == digest
            and manifest["ingest_status"] == "RECOGNIZED"
        )
        precise = locator.get("start_line") is not None or locator.get("start_offset") is not None
        refs.append({
            "filename": filename,
            "source_sha256": digest,
            "source_manifest": manifest,
            "locator_basis": locator.get("locator_basis"),
            "start_line": locator.get("start_line"),
            "end_line": locator.get("end_line"),
            "start_offset": locator.get("start_offset"),
            "end_offset": locator.get("end_offset"),
            "manifest_verified": matched,
            "precise_span": precise,
        })
    if len(refs) != 1:
        status = "AMBIGUOUS" if refs else "UNRESOLVED"
    elif refs[0]["manifest_verified"] and refs[0]["precise_span"]:
        status = "LOCATED_SOURCE_SPAN"
    elif refs[0]["manifest_verified"]:
        status = "FILE_LEVEL_ONLY"
    else:
        status = "UNVERIFIED_SOURCE"
    return {"status": status, "references": refs}


def reconstruct_observed_draft(
    con: sqlite3.Connection, capture_id: int, *, max_rows_per_table: int = 200
) -> dict:
    """Read only synthetic or previously indexed normalized rows.

    Ordering is *within* an indexed table/zone sequence only. Native timestamps
    are displayed but not aligned with one another. A return value never
    contains a normative expected result, PASS, or executable instruction.
    """
    if type(capture_id) is not int or capture_id < 1:
        raise ValueError("capture_id must be a positive indexed capture identifier")
    if type(max_rows_per_table) is not int or not 1 <= max_rows_per_table <= 1000:
        raise ValueError("max_rows_per_table must be 1..1000")
    if not _exists(con, "captures") or not con.execute(
        "SELECT 1 FROM captures WHERE capture_id=?", (capture_id,)
    ).fetchone():
        raise ValueError("capture does not exist in the supplied index")

    streams: dict[tuple[str, object], dict] = {}
    gaps: set[str] = {"NO_NORMATIVE_EXPECTED_ORACLE", "DSP_SOURCE_CORRELATION_NOT_EVALUATED",
                      "CROSS_STREAM_CLOCK_ALIGNMENT_UNPROVEN"}
    truncated_tables: list[str] = []
    missing_tables: list[str] = []
    event_rows: list[dict] = []

    for table, fields, ordering, basis in _SOURCES:
        if not _exists(con, table):
            missing_tables.append(table)
            continue
        cursor = con.execute(
            f"SELECT {fields} FROM {table} WHERE capture_id=? ORDER BY {ordering} LIMIT ?",
            (capture_id, max_rows_per_table + 1),
        )
        columns = [d[0] for d in cursor.description]
        fetched = cursor.fetchall()
        if len(fetched) > max_rows_per_table:
            truncated_tables.append(table)
            gaps.add("TRUNCATED_CAPTURE_INDEX")
        for values in fetched[:max_rows_per_table]:
            row = dict(zip(columns, values))
            if table in {"capture_events", "capture_eventview"}:
                key = {"zone_db": row["zone_db"], "seq": row["seq"]}
                partition = row["zone_db"]
            else:
                key = {"seq": row["seq"]}
                partition = None
            loc = _source_locator(con, capture_id, table, key)
            if loc["status"] not in {"LOCATED_SOURCE_SPAN", "FILE_LEVEL_ONLY"}:
                gaps.add("SOURCE_PROVENANCE_INCOMPLETE")
            stream_key = (table, partition)
            if stream_key not in streams:
                streams[stream_key] = {
                    "table": table,
                    "zone_db": partition,
                    "order_basis": basis,
                    "clock_status": "NOT_ALIGNED_WITH_OTHER_STREAMS",
                    "events": [],
                }
            event = {
                "row_key": key,
                "observation_kind": table,
                "observed_fields": row,
                "native_timestamp": row.get("ts"),
                "time_basis": "SOURCE_NATIVE_UNVERIFIED" if row.get("ts") is not None else "NO_TIMESTAMP",
                "source": loc,
                "confidence": "INDEXED_OBSERVATION_ONLY",
                "identity_status": "UNRESOLVED",
            }
            streams[stream_key]["events"].append(event)
            if table == "capture_events":
                event_rows.append(row)
            if table == "capture_raw_packets" and (row["is_injected"] or row["is_blocked"]):
                gaps.add("PACKET_INJECTED_OR_BLOCKED_NOT_SERVER_CONFIRMATION")

    # Existing Capture Timeline helper only groups adjacent, compatible records;
    # its "complete_signal" is a pattern heuristic, NOT a transaction assertion.
    interactions = []
    for group in reconstruct_interaction_candidates(event_rows):
        interactions.append({
            "zone_db": group["zone_db"],
            "start_seq": group["start_seq"],
            "end_seq": group["end_seq"],
            "entity_id": group["entity_id"],
            "csid_as_recorded": group["csid"],
            "row_keys": [{"zone_db": r["zone_db"], "seq": r["seq"]} for r in group["rows"]],
            "pattern_signal_only": group["complete_signal"],
            "interpretation": "POSSIBLE_INTERACTION_NOT_PROVEN_TRANSACTION",
        })
    if missing_tables:
        gaps.add("PARTIAL_CAPTURE_TABLE_COVERAGE")
    return {
        "contract": "reverse_capture_preview_v0_NONCANONICAL",
        "capture_id": capture_id,
        "classification": "OBSERVED_ONLY",
        "scenario_status": "DRAFT_REVIEW_REQUIRED",
        "normative_expected": None,
        "verdict": "UNKNOWN",
        "execution_enabled": False,
        "approved_for_execution": False,
        "source_correlation": {"status": "NOT_EVALUATED", "dsp_commit": None, "citations": []},
        "streams": list(streams.values()),
        "interaction_candidates": interactions,
        "missing_tables": missing_tables,
        "truncated_tables": truncated_tables,
        "review_gaps": sorted(gaps),
        "limitations": [
            "Observed records are not gameplay truth or expected behavior",
            "Sequence is valid only within its capture table/zone; timestamps are not aligned",
            "Source locators identify original bytes/rows; raw artifacts are never copied here",
            "IDs are raw observed values, not validated DSP or client identity bindings",
            "Packet rows are metadata only; no opcode interpretation or decode was attempted",
        ],
    }
