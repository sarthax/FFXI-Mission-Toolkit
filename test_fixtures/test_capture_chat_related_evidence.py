#!/usr/bin/env python3
from __future__ import annotations

import sqlite3

from workbench.core.services import capture_integrity
from workbench.core.services.capture_related_evidence import chat_native_source_matches


def key(**values):
    return capture_integrity.canonical_row_key(values)


def main():
    con = sqlite3.connect(":memory:")
    con.row_factory = sqlite3.Row
    con.execute("""CREATE TABLE capture_chat_observations (
        capture_id INTEGER, seq INTEGER, ts TEXT, direction TEXT,
        zone_id INTEGER, zone_db TEXT, text TEXT,
        source_format TEXT, source_native_id TEXT,
        PRIMARY KEY (capture_id, seq)
    )""")
    con.execute("""CREATE TABLE capture_caplog_chat (
        capture_id INTEGER, seq INTEGER, ts TEXT, zone_db TEXT, text TEXT,
        PRIMARY KEY (capture_id, seq)
    )""")

    # Proven pair: both rows are emitted by the CapLog parser from one source observation.
    con.execute(
        "INSERT INTO capture_caplog_chat VALUES (?,?,?,?,?)",
        (1, 7, "12:34:56", "Bastok_Mines", "same parser observation"),
    )
    con.execute(
        "INSERT INTO capture_chat_observations VALUES (?,?,?,?,?,?,?,?,?)",
        (1, 7, "12:34:56", None, None, "Bastok_Mines", "same parser observation",
         "caplog", "CapLog/Bastok.log:line:42"),
    )

    canonical = chat_native_source_matches(
        con, 1, "capture_chat_observations", key(seq=7)
    )
    assert len(canonical) == 1, canonical
    assert canonical[0]["target_table"] == "capture_caplog_chat", canonical
    assert canonical[0]["relation"] == "same CapLog source observation", canonical
    assert canonical[0]["source_native_id"] == "CapLog/Bastok.log:line:42", canonical

    reverse = chat_native_source_matches(con, 1, "capture_caplog_chat", key(seq=7))
    assert len(reverse) == 1, reverse
    assert reverse[0]["target_table"] == "capture_chat_observations", reverse

    # A row with the same sequence but a different adapter/native-id namespace is not related.
    con.execute(
        "INSERT INTO capture_caplog_chat VALUES (?,?,?,?,?)",
        (1, 8, "12:34:57", "Bastok_Mines", "number collision only"),
    )
    con.execute(
        "INSERT INTO capture_chat_observations VALUES (?,?,?,?,?,?,?,?,?)",
        (1, 8, "12:34:57", None, 234, "Bastok_Mines", "number collision only",
         "packetdb_chatlog", "8"),
    )
    assert chat_native_source_matches(
        con, 1, "capture_chat_observations", key(seq=8)
    ) == []
    assert chat_native_source_matches(con, 1, "capture_caplog_chat", key(seq=8)) == []

    # CapLog identity requires the typed native line locator; matching text/time never substitutes.
    con.execute(
        "INSERT INTO capture_caplog_chat VALUES (?,?,?,?,?)",
        (1, 9, "12:34:58", "Bastok_Mines", "same text"),
    )
    con.execute(
        "INSERT INTO capture_chat_observations VALUES (?,?,?,?,?,?,?,?,?)",
        (1, 9, "12:34:58", None, None, "Bastok_Mines", "same text",
         "caplog", "legacy-unknown-9"),
    )
    assert chat_native_source_matches(
        con, 1, "capture_chat_observations", key(seq=9)
    ) == []

    con.close()
    print("Capture chat native-source Related Evidence runtime regression: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
