#!/usr/bin/env python3
"""End-to-end structural/composite event identity resolution regression."""
from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path

from workbench.client.event_fingerprint import EventResource
from workbench.core.services.identity_resolver import (
    IdentitySnapshot,
    assess_identity_closure,
    ingest_event_structure_records,
    register_snapshot,
    resolve_identity,
)


def main() -> None:
    with tempfile.TemporaryDirectory() as td:
        con = sqlite3.connect(Path(td) / "workbench.db")
        register_snapshot(con, IdentitySnapshot("client:new", "CLIENT", "RETAIL", "new"))
        register_snapshot(con, IdentitySnapshot("client:old", "CLIENT", "RETAIL", "old"))

        # Same semantic event:
        # new client: event 77, message 503
        # old client: event 10, message 500
        # Opcode shape and Retail text agree while literal ids differ.
        ingest_event_structure_records(
            con,
            snapshot_id="client:new",
            zone_key="NORTH_GUSTABERG_S",
            resources=[
                EventResource(
                    entity_id=2002,
                    event_id=77,
                    byte_code=bytes([0x48, 0xF7, 0x01, 0x21]),
                    data_count=1,
                    data_values=(999,),
                    block_event_count=4,
                    block_index=0,
                )
            ],
            dialog_entries={503: "The same Retail line."},
        )
        ingest_event_structure_records(
            con,
            snapshot_id="client:old",
            zone_key="NORTH_GUSTABERG_S",
            resources=[
                EventResource(
                    entity_id=1001,
                    event_id=10,
                    byte_code=bytes([0x48, 0x00, 0x80, 0x21]),
                    data_count=1,
                    data_values=(500,),
                    block_event_count=2,
                    block_index=0,
                )
            ],
            dialog_entries={500: "The same Retail line."},
        )
        con.commit()

        resolved = resolve_identity(
            con,
            source_snapshot_id="client:new",
            target_snapshot_id="client:old",
            namespace="EVENT",
            source_numeric_id=77,
            zone_key="NORTH_GUSTABERG_S",
        )
        assert resolved.status == "TARGET_EQUIVALENT", resolved
        assert resolved.target_numeric_id == "10", resolved
        assert resolved.confidence == "HIGH", resolved

        closure = assess_identity_closure([resolved], minimum_confidence="HIGH")
        assert closure.status == "READY", closure

        # Add a second target event with identical composite semantics.
        # Resolver must refuse to guess which numeric event is correct.
        ingest_event_structure_records(
            con,
            snapshot_id="client:old",
            zone_key="NORTH_GUSTABERG_S",
            resources=[
                EventResource(
                    entity_id=1002,
                    event_id=11,
                    byte_code=bytes([0x48, 0xF4, 0x01, 0x21]),
                    data_count=0,
                    data_values=(),
                    block_event_count=1,
                    block_index=1,
                )
            ],
            dialog_entries={500: "The same Retail line."},
        )
        con.commit()

        ambiguous = resolve_identity(
            con,
            source_snapshot_id="client:new",
            target_snapshot_id="client:old",
            namespace="EVENT",
            source_numeric_id=77,
            zone_key="NORTH_GUSTABERG_S",
        )
        assert ambiguous.status == "TARGET_ID_AMBIGUOUS", ambiguous

        con.close()

    print("event identity resolution self-test: PASS")


if __name__ == "__main__":
    main()
