#!/usr/bin/env python3
"""Regression coverage for generic normalized ID/content collision analysis."""
from __future__ import annotations

from workbench.adapters.servers.base import LogicalRecord
from workbench.migrations.id_collision import analyze_collisions


def rec(logical_type, identity, **fields):
    return LogicalRecord(
        logical_type=logical_type,
        identity=tuple(identity),
        fields=dict(fields),
        source_family="synthetic",
        source_table=logical_type,
    )


def main():
    source = [
        rec("npcs", (("npc_id", 100),), npc_id=100, name="Alpha", zone_id=1, script="Alpha"),
        rec("npcs", (("npc_id", 101),), npc_id=101, name="Beta", zone_id=1, script="Beta"),
        rec("npcs", (("npc_id", 102),), npc_id=102, name="Gamma", zone_id=1, script="Gamma"),
        rec("npcs", (("npc_id", None),), npc_id=None, name="Unknown", zone_id=1, script="Unknown"),
        rec("spawns", (("spawn_id", 1), ("zone_id", 10)), spawn_id=1, zone_id=10, pool_id=55, x=1.0),
    ]
    target = [
        rec("npcs", (("npc_id", 100),), npc_id=100, name="Alpha", zone_id=1, script="Alpha"),
        rec("npcs", (("npc_id", 101),), npc_id=101, name="Other", zone_id=1, script="Other"),
        rec("npcs", (("npc_id", 202),), npc_id=202, name="Gamma", zone_id=1, script="Gamma"),
        rec("npcs", (("npc_id", 300),), npc_id=300, name="TargetOnly", zone_id=1, script="TargetOnly"),
        rec("spawns", (("spawn_id", 1), ("zone_id", 11)), spawn_id=1, zone_id=11, pool_id=55, x=1.0),
    ]

    result = analyze_collisions(
        source,
        target,
        source_snapshot_id="src-snap",
        target_snapshot_id="dst-snap",
    )
    findings = result["findings"]
    by_class = {}
    for row in findings:
        by_class.setdefault(row["classification"], []).append(row)

    assert len(by_class["EXACT_IDENTITY_EQUIVALENT"]) == 1, by_class
    assert len(by_class["ID_CONTENT_COLLISION"]) == 1, by_class
    assert len(by_class["CONTENT_RENUMBER_CANDIDATE"]) == 1, by_class
    assert len(by_class["SOURCE_IDENTITY_UNRESOLVED"]) == 1, by_class
    assert len(by_class["TARGET_ONLY"]) == 1, by_class

    remap = by_class["CONTENT_RENUMBER_CANDIDATE"][0]
    assert remap["source_identity"] == (("npc_id", 102),), remap
    assert remap["target_identity"] == (("npc_id", 202),), remap
    assert remap["confidence"] == "INFERRED", remap

    collision = by_class["ID_CONTENT_COLLISION"][0]
    assert collision["status"] == "CONTRADICTED", collision
    assert collision["identifier_namespaces"] == ("npcs:npc_id",), collision

    # Same numeric spawn_id in different zone_id is not a collision because the adapter-defined
    # identity tuple is composite and therefore namespace-local.
    assert not any(
        row["classification"] == "ID_CONTENT_COLLISION"
        and row["logical_type"] == "spawns"
        for row in findings
    ), findings

    print("ID/content collision analyzer self-test: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
