#!/usr/bin/env python3
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from tempfile import TemporaryDirectory

from workbench.captures.ingestion import build_index as build_capture_index
from workbench.core.services import capture_integrity


def add_event(con, cid, seq, event_hex, message_id):
    con.execute(
        """INSERT INTO capture_events
           (capture_id,zone_db,seq,direction,opcode,opcode_name,entity_id,entity_name,
            event_hex,option,message_id,params_raw)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
        (cid, "Test Zone", seq, "Incoming", "0x034", "CS Event", 17000001, "Test NPC",
         event_hex, 0, message_id, "{1,2}"),
    )


def add_action(con, cid, key, name, message):
    con.execute(
        """INSERT INTO capture_actions
           (capture_id,action_key,actor,actor_name,action_type,animation,category,message,name,ts)
           VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (cid, key, 17000002, "Test Mob", None, 44, 7, message, name, None),
    )


def main():
    with TemporaryDirectory() as tmp:
        con = sqlite3.connect(Path(tmp) / "capture.db")
        build_capture_index.init_db(con)

        a = build_capture_index.create_manual_capture(con, "session A", "Research", None)
        b = build_capture_index.create_manual_capture(con, "session B partial copy", "Research", None)
        c = build_capture_index.create_manual_capture(con, "unrelated", "Research", None)

        # A and B share two evidence families with four exact normalized observations.
        add_event(con, a, 0, "0x0199", 123)
        add_event(con, a, 1, "0x019A", 124)
        add_action(con, a, "a1", "Head Butt", 185)
        add_action(con, a, "a2", "Doton: Ni", 31)

        add_event(con, b, 0, "0x0199", 123)
        add_event(con, b, 1, "0x019A", 124)
        add_action(con, b, "b1", "Head Butt", 185)
        add_action(con, b, "b2", "Doton: Ni", 31)
        # One unique observation keeps this from being an exact normalized clone.
        add_action(con, b, "b3", "Unique Move", 999)

        # C shares only one common event: not enough for a partial-session candidate.
        add_event(con, c, 0, "0x0199", 123)
        add_action(con, c, "c1", "Completely Different", 777)
        con.commit()

        overlaps = capture_integrity.find_partial_capture_overlaps(con, a)
        assert len(overlaps) == 1, overlaps
        assert overlaps[0]["capture_id"] == b, overlaps
        assert overlaps[0]["shared_by_family"] == {"actions": 2, "events": 2}, overlaps[0]
        assert overlaps[0]["shared_total"] == 4
        assert overlaps[0]["basis"] == "normalized_runtime_evidence"

        # Timestamp locators preserve original physical source order. Midnight is normal; a later
        # 30-second backward move is a discontinuity that must be surfaced, not corrected.
        for idx, ts in enumerate(("23:59:59", "00:00:30", "00:00:00"), start=1):
            capture_integrity.record_row_locator(
                con, a, "caplog/session.txt", "capture_caplog_chat",
                json.dumps({"seq": idx - 1}), "line",
                start_line=idx, end_line=idx,
                details={"source": "caplog", "timestamp": ts},
            )

        # A separate full-datetime source also goes backwards.
        for idx, ts in enumerate(("2026-09-28 10:00:05", "2026-09-28 10:00:02"), start=1):
            capture_integrity.record_row_locator(
                con, a, "EventView/Test Zone.log", "capture_eventview",
                json.dumps({"zone_db": "Test Zone", "seq": idx - 1}), "block",
                start_line=idx * 2, end_line=idx * 2 + 1,
                details={"source": "eventview", "timestamp": ts},
            )
        con.commit()

        clocks = capture_integrity.clock_discontinuities(con, a)
        assert clocks["status"] == "ISSUES", clocks
        assert clocks["streams"] == 2, clocks
        assert clocks["timestamped_rows"] == 5, clocks
        backward = [d for d in clocks["discontinuities"] if d["type"] == "backward_clock_jump"]
        assert len(backward) == 2, clocks
        assert any(d["filename"] == "caplog/session.txt" and d["delta_seconds"] == -30 for d in backward)
        assert any(d["filename"] == "EventView/Test Zone.log" and d["delta_seconds"] == -3 for d in backward)

        # Midnight rollover itself must not be reported as a discontinuity.
        assert not any(
            d["filename"] == "caplog/session.txt" and d.get("line") == 2
            for d in clocks["discontinuities"]
        ), clocks

        health = capture_integrity.capture_health(con, a)
        assert health["dimensions"]["session_overlap"]["status"] == "PARTIAL", health
        assert health["dimensions"]["session_overlap"]["candidates"][0]["capture_id"] == b
        assert health["dimensions"]["clock_continuity"]["status"] == "ISSUES", health

        con.close()

    print("Capture overlap and clock diagnostics regression: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
