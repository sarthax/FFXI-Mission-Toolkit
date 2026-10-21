#!/usr/bin/env python3
"""Synthetic-only regression: reverse capture preview never manufactures an oracle."""
from __future__ import annotations

import hashlib
import json
import sqlite3

from workbench.captures.scenario_draft import reconstruct_observed_draft


def synthetic_index():
    con = sqlite3.connect(":memory:")
    con.executescript("""
        CREATE TABLE captures (capture_id INTEGER PRIMARY KEY);
        CREATE TABLE capture_events (
            capture_id INTEGER, zone_db TEXT, seq INTEGER, direction TEXT,
            opcode TEXT, opcode_name TEXT, entity_id INTEGER, entity_name TEXT,
            event_hex TEXT, option INTEGER, message_id INTEGER);
        CREATE TABLE capture_eventview (
            capture_id INTEGER, zone_db TEXT, seq INTEGER, ts TEXT, direction TEXT,
            opcode TEXT, packet_class TEXT, gp_command TEXT, entity_id INTEGER,
            mes_num INTEGER, message_number INTEGER);
        CREATE TABLE capture_raw_packets (
            capture_id INTEGER, seq INTEGER, ts TEXT, direction TEXT, opcode TEXT,
            zone_id INTEGER, is_injected INTEGER, is_blocked INTEGER,
            source_format TEXT, source_native_id TEXT);
        CREATE TABLE capture_source_manifest (
            capture_id INTEGER, filename TEXT, sha256 TEXT, parser_name TEXT,
            parser_version TEXT, ingest_status TEXT);
        CREATE TABLE capture_row_locators (
            capture_id INTEGER, filename TEXT, target_table TEXT, row_key TEXT,
            source_sha256 TEXT, locator_basis TEXT, start_line INTEGER,
            end_line INTEGER, start_offset INTEGER, end_offset INTEGER, details_json TEXT);
    """)
    con.execute("INSERT INTO captures VALUES (1)")
    con.executemany(
        "INSERT INTO capture_events VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        [
            (1, "SYNTHETIC_ZONE", 1, "Incoming", None, "synthetic dialog record",
             7000, "SYNTHETIC_ACTOR", None, None, 15),
            (1, "SYNTHETIC_ZONE", 2, "Incoming", None, "synthetic event record",
             7000, "SYNTHETIC_ACTOR", "SYNTHETIC_EVENT", None, None),
        ],
    )
    con.execute(
        "INSERT INTO capture_eventview VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (1, "OTHER_SYNTHETIC_ZONE", 1, "unverified clock A", "Incoming", None,
         "synthetic class", None, None, 15, None),
    )
    con.execute(
        "INSERT INTO capture_raw_packets VALUES (?,?,?,?,?,?,?,?,?,?)",
        (1, 1, "unverified clock B", "Outgoing", None, None, 1, 0,
         "synthetic-source", "synthetic-native-id"),
    )
    raw = b"synthetic source bytes only\n"
    sha = hashlib.sha256(raw).hexdigest()
    con.execute(
        "INSERT INTO capture_source_manifest VALUES (?,?,?,?,?,?)",
        (1, "SYNTHETIC_ONLY.log", sha, "synthetic fixture", "0", "RECOGNIZED"),
    )
    con.execute(
        "INSERT INTO capture_row_locators VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (1, "SYNTHETIC_ONLY.log", "capture_events",
         json.dumps({"zone_db": "SYNTHETIC_ZONE", "seq": 1}, sort_keys=True),
         sha, "line", 4, 4, None, None, "{}"),
    )
    con.commit()
    return con


def test_synthetic_observations_do_not_become_expected_or_pass():
    con = synthetic_index()
    # The entire adapter must be usable against a read-only SQLite connection.
    con.execute("PRAGMA query_only=ON")
    result = reconstruct_observed_draft(con, 1)
    assert result["contract"].endswith("NONCANONICAL")
    assert result["classification"] == "OBSERVED_ONLY"
    assert result["scenario_status"] == "DRAFT_REVIEW_REQUIRED"
    assert result["normative_expected"] is None
    assert result["verdict"] == "UNKNOWN"
    assert result["execution_enabled"] is False
    assert result["approved_for_execution"] is False
    assert result["source_correlation"]["citations"] == []
    assert result["source_correlation"]["dsp_commit"] is None

    events = next(s for s in result["streams"] if s["table"] == "capture_events")
    assert events["order_basis"] == "ZONE_SEQUENCE"
    assert [e["row_key"]["seq"] for e in events["events"]] == [1, 2]
    exact = events["events"][0]["source"]
    assert exact["status"] == "LOCATED_SOURCE_SPAN"
    assert exact["references"][0]["start_line"] == 4
    assert exact["references"][0]["source_manifest"]["parser_version"] == "0"
    assert events["events"][1]["source"]["status"] == "UNRESOLVED"
    assert len(result["interaction_candidates"]) == 1
    assert result["interaction_candidates"][0]["pattern_signal_only"] is True
    assert result["interaction_candidates"][0]["interpretation"] != "PROVEN_TRANSACTION"
    assert "SOURCE_PROVENANCE_INCOMPLETE" in result["review_gaps"]

    pkt = next(s for s in result["streams"] if s["table"] == "capture_raw_packets")
    ev = next(s for s in result["streams"] if s["table"] == "capture_eventview")
    assert pkt["events"][0]["time_basis"] == "SOURCE_NATIVE_UNVERIFIED"
    assert ev["events"][0]["time_basis"] == "SOURCE_NATIVE_UNVERIFIED"
    assert pkt["clock_status"] == ev["clock_status"] == "NOT_ALIGNED_WITH_OTHER_STREAMS"
    assert "PACKET_INJECTED_OR_BLOCKED_NOT_SERVER_CONFIRMATION" in result["review_gaps"]
    assert "raw_hex" not in str(result)
    assert "CROSS_STREAM_CLOCK_ALIGNMENT_UNPROVEN" in result["review_gaps"]
    con.close()


def test_locator_ambiguity_and_mismatched_hash_fail_closed():
    con = synthetic_index()
    key = json.dumps({"zone_db": "SYNTHETIC_ZONE", "seq": 1}, sort_keys=True)
    con.execute(
        "INSERT INTO capture_row_locators VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (1, "SECOND_SYNTHETIC.log", "capture_events", key,
         "b" * 64, "line", 9, 9, None, None, "{}"),
    )
    draft = reconstruct_observed_draft(con, 1)
    event = next(s for s in draft["streams"] if s["table"] == "capture_events")["events"][0]
    assert event["source"]["status"] == "AMBIGUOUS"
    assert len(event["source"]["references"]) == 2
    assert "SOURCE_PROVENANCE_INCOMPLETE" in draft["review_gaps"]
    con.close()


def test_missing_tables_and_bounded_output_are_explicit():
    con = synthetic_index()
    result = reconstruct_observed_draft(con, 1, max_rows_per_table=1)
    assert result["truncated_tables"] == ["capture_events"]
    assert "capture_ki_events" in result["missing_tables"]
    assert "TRUNCATED_CAPTURE_INDEX" in result["review_gaps"]
    assert len(next(s for s in result["streams"] if s["table"] == "capture_events")["events"]) == 1
    for invalid in (0, -1, 1001, True):
        try:
            reconstruct_observed_draft(con, 1, max_rows_per_table=invalid)
        except ValueError:
            pass
        else:
            raise AssertionError("unbounded/invalid request accepted")
    try:
        reconstruct_observed_draft(con, 99)
    except ValueError:
        pass
    else:
        raise AssertionError("unknown capture accepted")
    con.close()


def main():
    test_synthetic_observations_do_not_become_expected_or_pass()
    test_locator_ambiguity_and_mismatched_hash_fail_closed()
    test_missing_tables_and_bounded_output_are_explicit()
    print("synthetic reverse-capture draft regression: PASS")


if __name__ == "__main__":
    main()
