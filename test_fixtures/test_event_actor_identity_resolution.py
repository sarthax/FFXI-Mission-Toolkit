#!/usr/bin/env python3
"""Regression for snapshot-aware target actor constraints in EVENT resolution."""
from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path

from workbench.client.event_fingerprint import EventResource
from workbench.core.services.identity_resolver import (
    IdentityRecord,
    IdentitySnapshot,
    ingest_entity_identity_records,
    ingest_event_structure_records,
    register_snapshot,
    resolve_event_identity,
    semantic_entity_key,
    upsert_record,
)


ZONE = "NORTH_GUSTABERG_S"
SOURCE_BYTES = bytes([0x48, 0xF7, 0x01, 0x21])
TARGET_BYTES = bytes([0x48, 0xF4, 0x01, 0x21])


def _event(actor: int, event_id: int, byte_code: bytes) -> EventResource:
    return EventResource(
        entity_id=actor,
        event_id=event_id,
        byte_code=byte_code,
        block_event_count=1,
        block_index=actor,
    )


def main() -> None:
    with tempfile.TemporaryDirectory() as td:
        con = sqlite3.connect(Path(td) / "workbench.db")
        register_snapshot(con, IdentitySnapshot("client:new", "CLIENT", "RETAIL", "new"))
        register_snapshot(con, IdentitySnapshot("client:old", "CLIENT", "RETAIL", "old"))

        # One source event has three structurally equivalent target events. The source actor
        # has drifted from 2002 to 1001, so only a semantic entity mapping may select event 10.
        ingest_event_structure_records(
            con,
            snapshot_id="client:new",
            zone_key=ZONE,
            resources=[
                _event(2002, 77, SOURCE_BYTES),
                _event(2003, 78, SOURCE_BYTES),
                _event(2004, 79, SOURCE_BYTES),
                _event(3000, 80, SOURCE_BYTES),
            ],
        )
        ingest_event_structure_records(
            con,
            snapshot_id="client:old",
            zone_key=ZONE,
            resources=[
                _event(1001, 10, TARGET_BYTES),
                _event(1002, 11, TARGET_BYTES),
                # Matching the unresolved source actor numerically is not evidence of identity.
                _event(2004, 12, TARGET_BYTES),
                _event(3000, 21, TARGET_BYTES),
            ],
        )
        ingest_entity_identity_records(
            con,
            snapshot_id="client:new",
            zone_key=ZONE,
            entities={2002: "NPC:SUPPLY_OFFICER", 3000: "NPC:STABLE"},
            evidence_id_prefix="entity-profile:new",
        )
        ingest_entity_identity_records(
            con,
            snapshot_id="client:old",
            zone_key=ZONE,
            entities={1001: "NPC:SUPPLY_OFFICER", 3000: "NPC:STABLE"},
            evidence_id_prefix="entity-profile:old",
        )

        # Two independently claimed source semantic identities for one actor remain ambiguous.
        for suffix in ("A", "B"):
            upsert_record(
                con,
                IdentityRecord(
                    record_id=f"identity:client:new:ENTITY:{ZONE}:2003:{suffix}",
                    snapshot_id="client:new",
                    namespace="ENTITY",
                    semantic_key=semantic_entity_key(
                        zone_key=ZONE,
                        semantic_identity=f"NPC:AMBIGUOUS_{suffix}",
                    ),
                    numeric_id=2003,
                    zone_key=ZONE,
                    confidence="HIGH",
                ),
            )
        con.commit()

        drifted = resolve_event_identity(
            con,
            source_snapshot_id="client:new",
            target_snapshot_id="client:old",
            source_numeric_id=77,
            zone_key=ZONE,
            source_actor_key=2002,
        )
        assert drifted.status == "TARGET_EQUIVALENT", drifted
        assert drifted.target_numeric_id == "10", drifted
        assert drifted.metadata["actor_resolution"] == {
            "source_actor_id": "2002",
            "constraint_applied": True,
            "status": "TARGET_EQUIVALENT",
            "confidence": "HIGH",
            "source_record_id": f"identity:client:new:ENTITY:{ZONE}:2002",
            "target_record_id": f"identity:client:old:ENTITY:{ZONE}:1001",
            "reason": "Semantic identity matches but target snapshot uses a different numeric representation.",
            "target_actor_id": "1001",
        }, drifted

        ambiguous_actor = resolve_event_identity(
            con,
            source_snapshot_id="client:new",
            target_snapshot_id="client:old",
            source_numeric_id=78,
            zone_key=ZONE,
            source_actor_key=2003,
        )
        assert ambiguous_actor.status == "TARGET_ID_AMBIGUOUS", ambiguous_actor
        assert ambiguous_actor.metadata["actor_resolution"]["status"] == "SOURCE_ID_AMBIGUOUS", ambiguous_actor
        assert not ambiguous_actor.metadata["actor_resolution"]["constraint_applied"], ambiguous_actor

        unresolved_actor = resolve_event_identity(
            con,
            source_snapshot_id="client:new",
            target_snapshot_id="client:old",
            source_numeric_id=79,
            zone_key=ZONE,
            source_actor_key=2004,
        )
        assert unresolved_actor.status == "TARGET_ID_AMBIGUOUS", unresolved_actor
        assert unresolved_actor.metadata["actor_resolution"]["status"] == "SOURCE_ID_UNRESOLVED", unresolved_actor
        assert not unresolved_actor.metadata["actor_resolution"]["constraint_applied"], unresolved_actor

        same_actor = resolve_event_identity(
            con,
            source_snapshot_id="client:new",
            target_snapshot_id="client:old",
            source_numeric_id=80,
            zone_key=ZONE,
            source_actor_key=3000,
        )
        assert same_actor.status == "TARGET_EQUIVALENT", same_actor
        assert same_actor.target_numeric_id == "21", same_actor
        assert same_actor.metadata["actor_resolution"]["status"] == "EXACT", same_actor
        assert same_actor.metadata["actor_resolution"]["target_actor_id"] == "3000", same_actor
        assert same_actor.metadata["actor_resolution"]["constraint_applied"], same_actor

        con.close()

    print("event target actor identity resolution self-test: PASS")


if __name__ == "__main__":
    main()
