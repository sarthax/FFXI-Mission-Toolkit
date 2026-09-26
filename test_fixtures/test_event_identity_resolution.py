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
    compare_event_snapshots,
    ingest_event_structure_records,
    register_snapshot,
    resolve_event_identity,
)


def main() -> None:
    with tempfile.TemporaryDirectory() as td:
        con = sqlite3.connect(Path(td) / "workbench.db")
        register_snapshot(con, IdentitySnapshot("client:new", "CLIENT", "RETAIL", "new"))
        register_snapshot(con, IdentitySnapshot("client:old", "CLIENT", "RETAIL", "old"))
        register_snapshot(con, IdentitySnapshot("client:structure-only", "CLIENT", "RETAIL", "structure-only"))
        register_snapshot(con, IdentitySnapshot("client:unknown-opcode", "CLIENT", "RETAIL", "unknown-opcode"))

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
        # Same numeric event id under another source actor: raw CSID alone is not enough.
        ingest_event_structure_records(
            con,
            snapshot_id="client:new",
            zone_key="NORTH_GUSTABERG_S",
            resources=[
                EventResource(
                    entity_id=2003,
                    event_id=77,
                    byte_code=bytes([0x04, 0x21]),
                    data_count=0,
                    data_values=(),
                    block_event_count=1,
                    block_index=1,
                )
            ],
            dialog_entries={},
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

        unscoped_source = resolve_event_identity(
            con,
            source_snapshot_id="client:new",
            target_snapshot_id="client:old",
            source_numeric_id=77,
            zone_key="NORTH_GUSTABERG_S",
        )
        assert unscoped_source.status == "SOURCE_ID_AMBIGUOUS", unscoped_source

        resolved = resolve_event_identity(
            con,
            source_snapshot_id="client:new",
            target_snapshot_id="client:old",
            source_numeric_id=77,
            zone_key="NORTH_GUSTABERG_S",
            source_actor_key=2002,
        )
        assert resolved.status == "TARGET_EQUIVALENT", resolved
        assert resolved.target_numeric_id == "10", resolved
        assert resolved.confidence == "HIGH", resolved

        closure = assess_identity_closure([resolved], minimum_confidence="HIGH")
        assert closure.status == "READY", closure

        bulk = compare_event_snapshots(
            con,
            source_snapshot_id="client:new",
            target_snapshot_id="client:old",
            zone_key="NORTH_GUSTABERG_S",
            minimum_confidence="HIGH",
        )
        assert bulk["total"] == 2, bulk
        assert bulk["counts"]["TARGET_EQUIVALENT"] == 1, bulk
        assert bulk["counts"]["TARGET_ID_UNRESOLVED"] == 1, bulk
        mapped = [r for r in bulk["rows"] if r["status"] == "TARGET_EQUIVALENT"]
        assert mapped[0]["source_actor_key"] == "2002", mapped
        assert mapped[0]["source_event_id"] == "77", mapped
        assert mapped[0]["target_event_id"] == "10", mapped
        assert mapped[0]["confidence"] == "HIGH", mapped

        # Target lacks matching dialog text evidence but has the same fully decoded structure.
        ingest_event_structure_records(
            con,
            snapshot_id="client:structure-only",
            zone_key="NORTH_GUSTABERG_S",
            resources=[
                EventResource(
                    entity_id=3001,
                    event_id=44,
                    byte_code=bytes([0x48, 0xE7, 0x03, 0x21]),
                    block_event_count=1,
                    block_index=0,
                )
            ],
            dialog_entries={},
        )
        con.commit()
        structure_only = resolve_event_identity(
            con,
            source_snapshot_id="client:new",
            target_snapshot_id="client:structure-only",
            source_numeric_id=77,
            zone_key="NORTH_GUSTABERG_S",
            source_actor_key=2002,
            minimum_confidence="HIGH",
        )
        assert structure_only.status == "TARGET_EQUIVALENT", structure_only
        assert structure_only.target_numeric_id == "44", structure_only
        assert structure_only.confidence == "HIGH", structure_only
        assert structure_only.metadata["match_basis"] == "DECODED_STRUCTURE", structure_only

        # Unknown opcodes may produce a coarse shape, but cannot satisfy HIGH-confidence closure.
        ingest_event_structure_records(
            con,
            snapshot_id="client:unknown-opcode",
            zone_key="UNKNOWN_ZONE",
            resources=[
                EventResource(
                    entity_id=4001,
                    event_id=55,
                    byte_code=bytes([0xFE, 0x48, 0xF5, 0x01, 0x21]),
                    block_event_count=1,
                    block_index=0,
                )
            ],
            dialog_entries={},
        )
        ingest_event_structure_records(
            con,
            snapshot_id="client:new",
            zone_key="UNKNOWN_ZONE",
            resources=[
                EventResource(
                    entity_id=4002,
                    event_id=56,
                    byte_code=bytes([0xFE, 0x48, 0xF4, 0x01, 0x21]),
                    block_event_count=1,
                    block_index=2,
                )
            ],
            dialog_entries={},
        )
        con.commit()
        low = resolve_event_identity(
            con,
            source_snapshot_id="client:new",
            target_snapshot_id="client:unknown-opcode",
            source_numeric_id=56,
            zone_key="UNKNOWN_ZONE",
            source_actor_key=4002,
            minimum_confidence="HIGH",
        )
        assert low.status == "TARGET_ID_LOW_CONFIDENCE", low
        assert low.confidence == "LOW", low
        assert low.metadata["match_basis"] == "COARSE_STRUCTURE", low

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

        ambiguous = resolve_event_identity(
            con,
            source_snapshot_id="client:new",
            target_snapshot_id="client:old",
            source_numeric_id=77,
            zone_key="NORTH_GUSTABERG_S",
            source_actor_key=2002,
        )
        assert ambiguous.status == "TARGET_ID_AMBIGUOUS", ambiguous

        con.close()

    print("event identity resolution self-test: PASS")


if __name__ == "__main__":
    main()
