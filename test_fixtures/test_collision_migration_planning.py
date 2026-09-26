#!/usr/bin/env python3
"""Regression coverage for collision-aware migration planning."""
from __future__ import annotations

from workbench.migrations.logical_planner import plan_collision_findings
from workbench.migrations.package_plan import build_package_plan


def main():
    result={
        "source_snapshot_id":"src-snap",
        "target_snapshot_id":"dst-snap",
        "findings":[
            {
                "classification":"EXACT_IDENTITY_EQUIVALENT",
                "logical_type":"npcs",
                "source_identity":[["npc_id",100]],
                "target_identity":[["npc_id",100]],
                "identifier_namespaces":["npcs:npc_id"],
                "confidence":"VERIFIED",
                "status":"COMPATIBLE",
            },
            {
                "classification":"ID_CONTENT_COLLISION",
                "logical_type":"npcs",
                "source_identity":[["npc_id",101]],
                "target_identity":[["npc_id",101]],
                "identifier_namespaces":["npcs:npc_id"],
                "confidence":"VERIFIED",
                "status":"CONTRADICTED",
            },
            {
                "classification":"CONTENT_RENUMBER_CANDIDATE",
                "logical_type":"npcs",
                "source_identity":[["npc_id",102]],
                "target_identity":[["npc_id",202]],
                "identifier_namespaces":["npcs:npc_id"],
                "confidence":"INFERRED",
                "status":"DISCOVERED",
            },
        ],
    }

    actions=plan_collision_findings(result,"migration:test")
    by_class={a.metadata["classification"]:a for a in actions}

    assert by_class["EXACT_IDENTITY_EQUIVALENT"].action=="NOT_REQUIRED",actions
    assert by_class["EXACT_IDENTITY_EQUIVALENT"].status=="COMPATIBLE",actions

    collision=by_class["ID_CONTENT_COLLISION"]
    assert collision.action=="MANUAL_REVIEW",collision
    assert collision.status=="BLOCKED",collision

    remap=by_class["CONTENT_RENUMBER_CANDIDATE"]
    assert remap.action=="RENUMBER",remap
    assert remap.status=="MANUAL_REQUIRED",remap
    assert remap.metadata["source_snapshot_id"]=="src-snap",remap
    assert remap.metadata["target_snapshot_id"]=="dst-snap",remap

    plan=build_package_plan(actions)
    assert plan.status=="BLOCKED",plan

    # Without a hard collision, a renumber candidate must still prevent automatic readiness.
    review_plan=build_package_plan([by_class["EXACT_IDENTITY_EQUIVALENT"],remap])
    assert review_plan.status=="MANUAL_REQUIRED",review_plan

    print("collision-aware migration planning self-test: PASS")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
