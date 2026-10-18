#!/usr/bin/env python3
"""Offline packet-layout fixture tests. No client binaries or network required."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from workbench.client.protocol_compatibility import compare_builds, load_record, validate_record


def main():
    path = Path(__file__).resolve().parent.parent / "client_protocol_records" / "wardrobe_item_max_2021_2026.json"
    record = load_record(path)
    changes = compare_builds(record)
    assert len(changes) == 2, changes
    assert {c["field"] for c in changes} == {"u8_copy", "u16_capacity"}
    assert next(c for c in changes if c["field"] == "u16_capacity")["new"]["offset"] == "0x24"
    assert all(b["status"] == "INFERRED" for b in record["builds"])
    bad = json.loads(json.dumps(record))
    bad["builds"][0]["fields"][0]["offset"] = "-1"
    try:
        validate_record(bad)
    except ValueError:
        pass
    else:
        raise AssertionError("invalid offset accepted")
    bad = json.loads(json.dumps(record))
    bad["builds"][0]["fields"][0]["status"] = "VERIFIED_WITHOUT_PROOF"
    try:
        validate_record(bad)
    except ValueError:
        pass
    else:
        raise AssertionError("invalid evidence status accepted")
    print("client protocol compatibility fixture: PASS")


if __name__ == "__main__":
    main()
