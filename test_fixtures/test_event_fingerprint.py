#!/usr/bin/env python3
"""Regression for composite FFXI event-resource fingerprints."""
from __future__ import annotations

import tempfile
from pathlib import Path

from workbench.client.event_fingerprint import (
    EventResource,
    compare_event_fingerprints,
    fingerprint_event,
    parse_event_export,
)


def main() -> None:
    # Same opcode/instruction shape, different immediate WAIT argument.
    a = fingerprint_event(EventResource(
        entity_id=1001, event_id=10,
        byte_code=bytes([0x1C, 0x01, 0x00, 0x21]),
        data_count=2, block_event_count=3,
    ))
    b = fingerprint_event(EventResource(
        entity_id=2002, event_id=77,
        byte_code=bytes([0x1C, 0x02, 0x00, 0x21]),
        data_count=9, block_event_count=12,
    ))
    assert a.exact_sha256 != b.exact_sha256, (a, b)
    assert a.structural_sha256 == b.structural_sha256, (a, b)
    structural = compare_event_fingerprints(a, b)
    expected_status = "STRUCTURE_MATCH" if a.parser != "RAW_ONLY" and b.parser != "RAW_ONLY" else "COARSE_SHAPE_MATCH"
    expected_confidence = "HIGH" if expected_status == "STRUCTURE_MATCH" else "LOW"
    assert structural["status"] == expected_status, structural
    assert structural["confidence"] == expected_confidence, structural

    # Same text alone must not override structural disagreement.
    c = fingerprint_event(EventResource(
        entity_id=1001, event_id=10,
        byte_code=bytes([0x04, 0x21]),
        data_count=2, block_event_count=3,
    ))
    text_only = compare_event_fingerprints(
        a, c,
        source_text_fingerprint="same-text",
        target_text_fingerprint="same-text",
    )
    assert text_only["status"] == "TEXT_ONLY_MATCH", text_only
    assert text_only["confidence"] == "LOW", text_only

    exact = compare_event_fingerprints(a, a)
    assert exact["status"] == "EXACT_BYTECODE", exact
    assert exact["confidence"] == "VERIFIED", exact

    # Message ids may drift while the referenced Retail text remains semantically identical.
    # Source uses an immediate-data reference (0x8000 -> 500); target uses direct id 503.
    msg_source = fingerprint_event(
        EventResource(
            entity_id=1001,
            event_id=20,
            byte_code=bytes([0x48, 0x00, 0x80, 0x21]),
            data_count=1,
            data_values=(500,),
            block_event_count=1,
        ),
        dialog_entries={500: "The same Retail line."},
    )
    msg_target = fingerprint_event(
        EventResource(
            entity_id=2002,
            event_id=90,
            byte_code=bytes([0x48, 0xF7, 0x01, 0x21]),
            data_count=1,
            data_values=(999,),
            block_event_count=1,
        ),
        dialog_entries={503: "The same Retail line."},
    )
    assert msg_source.message_ids == (500,), msg_source
    assert msg_target.message_ids == (503,), msg_target
    assert msg_source.structural_sha256 == msg_target.structural_sha256, (msg_source, msg_target)
    assert msg_source.composite_sha256 == msg_target.composite_sha256, (msg_source, msg_target)
    composite = compare_event_fingerprints(msg_source, msg_target)
    assert composite["status"] == "COMPOSITE_STRUCTURE_TEXT_MATCH", composite
    assert composite["confidence"] == "HIGH", composite

    # Ordinary raw entity ids are contextual only and must not change semantic identity.
    npc_a = fingerprint_event(EventResource(
        entity_id=1001,
        event_id=30,
        byte_code=bytes([0x49, 0x01, 0x00, 0x00, 0x01, 0xF4, 0x01, 0x21]),
        block_event_count=1,
    ))
    npc_b = fingerprint_event(EventResource(
        entity_id=2002,
        event_id=31,
        byte_code=bytes([0x49, 0x02, 0x00, 0x00, 0x01, 0xF4, 0x01, 0x21]),
        block_event_count=1,
    ))
    assert npc_a.entity_roles == (), npc_a
    assert npc_b.entity_roles == (), npc_b
    assert npc_a.structural_sha256 == npc_b.structural_sha256, (npc_a, npc_b)

    # Portable special entity semantics are fingerprint evidence.
    event_entity = fingerprint_event(EventResource(
        entity_id=1001,
        event_id=32,
        byte_code=bytes([0x49, 0xF8, 0xFF, 0xFF, 0x7F, 0xF4, 0x01, 0x21]),
        block_event_count=1,
    ))
    local_player = fingerprint_event(EventResource(
        entity_id=1001,
        event_id=33,
        byte_code=bytes([0x49, 0xF0, 0xFF, 0xFF, 0x7F, 0xF4, 0x01, 0x21]),
        block_event_count=1,
    ))
    assert event_entity.entity_roles == ("EVENT_ENTITY",), event_entity
    assert local_player.entity_roles == ("LOCAL_PLAYER",), local_player
    assert event_entity.structural_sha256 != local_player.structural_sha256

    msg_other_text = fingerprint_event(
        EventResource(
            entity_id=2002,
            event_id=91,
            byte_code=bytes([0x48, 0xF7, 0x01, 0x21]),
            data_count=1,
            data_values=(999,),
            block_event_count=1,
        ),
        dialog_entries={503: "A different Retail line."},
    )
    assert msg_source.structural_sha256 == msg_other_text.structural_sha256
    assert msg_source.composite_sha256 != msg_other_text.composite_sha256

    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "events.yml"
        path.write_text(
            "blocks:\n"
            "- entity_id: 12345\n"
            "  events:\n"
            "  - id: 10\n"
            "    byte_code: '0x1C010021'\n"
            "  - id: 11\n"
            "    byte_code: '0x0421'\n"
            "  data:\n"
            "  - 123\n"
            "  - 456\n",
            encoding="utf-8",
        )
        rows = parse_event_export(path)
        assert len(rows) == 2, rows
        assert [x.event_id for x in rows] == [10, 11], rows
        assert all(x.entity_id == 12345 for x in rows), rows
        assert all(x.data_count == 2 for x in rows), rows
        assert all(x.data_values == (123, 456) for x in rows), rows
        assert all(x.block_event_count == 2 for x in rows), rows

    print("event structural fingerprint self-test: PASS")


if __name__ == "__main__":
    main()
