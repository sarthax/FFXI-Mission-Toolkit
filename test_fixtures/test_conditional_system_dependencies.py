#!/usr/bin/env python3
"""Foundation regression: conditional cross-zone/system dependencies enter package scope."""
from __future__ import annotations

import json
import sqlite3
import tempfile
from pathlib import Path

from workbench.core import graph
from workbench.core.schema import Artifact, Entity, Evidence, MigrationAction
from workbench.core.services.conditional_dependencies import (
    ConditionalDependency,
    persist_conditional_dependency,
    project_conditional_dependency,
)
from workbench.migrations.package_scope import build_dependency_scope


ROOT=Path(__file__).resolve().parents[1]
TRUTH=ROOT/"test_fixtures"/"fixtures"/"dependency_truth_cross_zone_entity.json"


def main():
    payload=json.loads(TRUTH.read_text(encoding="utf-8"))
    facts=payload["verified_facts"]
    variants=facts["alternate_variants"]

    with tempfile.TemporaryDirectory() as td:
        db=Path(td)/"workbench.db"
        con=graph.init_db(db)
        con.row_factory=sqlite3.Row
        con.execute(
            "INSERT INTO migrations VALUES (?,?,?,?,?,?)",
            ("migration:medusa","feature:medusa-arrapago","lsb:test","dsp:test","DISCOVERED","{}"),
        )
        root=Artifact(
            "artifact:medusa-arrapago","LUA",
            "scripts/zones/Arrapago_Reef/mobs/Medusa.lua",
            "lsb:test","dsp:test","feature:medusa-arrapago",
        )
        graph.insert_record(con,root)
        graph.insert_record(con,MigrationAction(
            "action:medusa-root","migration:medusa","CONVERT",root.artifact_id,
            "AUTO_MIGRATABLE","Root Arrapago Medusa implementation.",
        ))

        besieged=Artifact(
            "artifact:system:besieged","LUA",facts["besieged_system"]["global_script"],
            "lsb:test","dsp:test","feature:system:besieged",
        )
        graph.insert_record(con,besieged)
        graph.insert_record(con,Entity(
            "system-state:besieged","SYSTEM_STATE","Besieged lifecycle",{
                "source_status":facts["besieged_system"]["current_lsb_status"],
                "semantic_requirement":facts["besieged_system"]["semantic_requirement"],
            },
        ))
        graph.insert_record(con,Evidence(
            "evidence:medusa-system-coupling","REFERENCE_PROOF",
            "dependency_truth_cross_zone_entity",
            str(TRUTH.relative_to(ROOT)),None,
            "Machine-readable proof that alternate Medusa variants share conditional Besieged lifecycle/state.",
        ))

        system_projection=project_conditional_dependency(ConditionalDependency(
            root.artifact_id,
            besieged.artifact_id,
            "Besieged lifecycle coupling",
            conditions=(
                {"subject":"system-state:besieged","operator":"CONTROLS_LIFECYCLE","value":True},
            ),
            rationale=facts["besieged_system"]["semantic_requirement"],
            evidence_id="evidence:medusa-system-coupling",
            confidence="EXPECTED",
            source_snapshot_id="lsb:test",
            source_location=str(TRUTH.relative_to(ROOT)),
            metadata={"proof_case":"cross-zone-system-coupling"},
        ))
        persist_conditional_dependency(con,system_projection,commit=False)

        for row in variants:
            zone_slug=row["zone"].replace(" ","_")
            variant=Artifact(
                f"artifact:medusa-variant:{zone_slug}","LUA",row["script"],
                "lsb:test","dsp:test","feature:system:besieged",
            )
            graph.insert_record(con,variant)
            projection=project_conditional_dependency(ConditionalDependency(
                system_projection.gate.entity_id,
                variant.artifact_id,
                f"{row['zone']} Medusa lifecycle variant",
                conditions=(
                    {"subject":"system:besieged","operator":"COUPLES_VARIANT","value":row["zone"]},
                ),
                rationale=row["reason"],
                evidence_id="evidence:medusa-system-coupling",
                confidence="EXPECTED",
                source_snapshot_id="lsb:test",
                source_location=str(TRUTH.relative_to(ROOT)),
                metadata={"relation":row["relation"],"zone":row["zone"]},
            ))
            persist_conditional_dependency(con,projection,commit=False)
        con.commit()

        scope=build_dependency_scope(con,"migration:medusa",max_depth=6)
        by_id={item["node_id"]:item for item in scope["items"]}

        assert "artifact:system:besieged" in by_id,scope
        assert by_id["artifact:system:besieged"]["effective_decision"]=="QUESTIONABLE",scope
        assert system_projection.gate.entity_id in by_id,scope
        gate=by_id[system_projection.gate.entity_id]
        assert gate["node_kind"]=="CONDITIONAL_DEPENDENCY",gate
        assert "system-state:besieged" in (gate["condition_summary"] or ""),gate
        assert gate["relationship"]=="HAS_CONDITIONAL_DEPENDENCY",gate

        variant_ids={
            f"artifact:medusa-variant:{row['zone'].replace(' ','_')}"
            for row in variants
        }
        assert variant_ids <= set(by_id),scope
        assert all(by_id[node]["effective_decision"]=="QUESTIONABLE" for node in variant_ids),scope
        assert any(item["relationship"]=="CONDITIONALLY_REQUIRES" for item in scope["items"]),scope
        assert scope["closure_status"]=="MANUAL_REQUIRED",scope
        assert scope["package_gate"]=="REVIEW_REQUIRED",scope
        con.close()

    print("conditional cross-zone/system dependency foundation: PASS")


if __name__=="__main__":
    main()
