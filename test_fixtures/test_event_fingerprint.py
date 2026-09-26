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
        data_count=2, block_event_count=3,
    ))
    assert a.exact_sha256 != b.exact_sha256, (a, b)
    assert a.structural_sha256 == b.structural_sha256, (a, b)
    structural = compare_event_fingerprints(a, b)
    assert structural["status"] == "STRUCTURE_MATCH", structural
    assert structural["confidence"] == "HIGH", structural

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
        assert all(x.block_event_count == 2 for x in rows), rows

    print("event structural fingerprint self-test: PASS")


if __name__ == "__main__":
    main()
