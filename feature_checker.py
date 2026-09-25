#!/usr/bin/env python3
"""Check declared feature requirements against canonical capability and implementation evidence.

Feature Checker is deliberately evidence-driven. It does not infer that a feature is implemented
from graph connectivity, a wiki page, or the presence of one source artifact. Required capabilities
are evaluated independently, and implementation/validation records are reported as supporting
evidence rather than collapsed into an opaque score.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


SCHEMA = 1

CAPABILITY_STATUSES = {
    "VERIFIED": "VERIFIED",
    "CONTRADICTED": "CONTRADICTED",
    "FAILED": "CONTRADICTED",
    "MISSING": "MISSING",
    "UNKNOWN": "UNKNOWN",
    "DISCOVERED": "PRESENT_UNVERIFIED",
    "INFERRED": "PRESENT_UNVERIFIED",
    "IMPLEMENTED": "PRESENT_UNVERIFIED",
}


def _json_value(raw):
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return raw


def resolve_feature(con: sqlite3.Connection, value: str) -> dict | None:
    row = con.execute(
        "SELECT feature_id, name, feature_type, domain_id, source_snapshot_id, target_snapshot_id, status, metadata_json "
        "FROM features WHERE feature_id=?",
        (value,),
    ).fetchone()
    if row:
        return {
            "feature_id": row[0], "name": row[1], "feature_type": row[2], "domain_id": row[3],
            "source_snapshot_id": row[4], "target_snapshot_id": row[5], "status": row[6],
            "metadata": _json_value(row[7]) or {},
        }

    rows = con.execute(
        "SELECT feature_id, name, feature_type, domain_id, source_snapshot_id, target_snapshot_id, status, metadata_json "
        "FROM features WHERE feature_id LIKE ? OR name LIKE ? ORDER BY feature_id",
        (f"%{value}%", f"%{value}%"),
    ).fetchall()
    if len(rows) != 1:
        return None
    row = rows[0]
    return {
        "feature_id": row[0], "name": row[1], "feature_type": row[2], "domain_id": row[3],
        "source_snapshot_id": row[4], "target_snapshot_id": row[5], "status": row[6],
        "metadata": _json_value(row[7]) or {},
    }


def check_feature(con: sqlite3.Connection, feature: dict) -> dict:
    fid = feature["feature_id"]
    requirements = con.execute(
        "SELECT requirement_id, capability_id, required, status, evidence_id, notes_json "
        "FROM capability_requirements WHERE feature_id=? ORDER BY requirement_id",
        (fid,),
    ).fetchall()

    checks = []
    for req_id, cap_id, required, req_status, req_evidence, req_notes in requirements:
        cap = con.execute(
            "SELECT capability_id, name, capability_type, subject_id, source_snapshot_id, status, value_json, evidence_id, notes_json "
            "FROM capabilities WHERE capability_id=?",
            (cap_id,),
        ).fetchone()

        if cap is None:
            observed = "MISSING"
            cap_record = None
        else:
            observed = CAPABILITY_STATUSES.get(cap[5], "UNKNOWN")
            cap_record = {
                "capability_id": cap[0], "name": cap[1], "capability_type": cap[2],
                "subject_id": cap[3], "source_snapshot_id": cap[4], "status": cap[5],
                "value": _json_value(cap[6]), "evidence_id": cap[7],
                "notes": _json_value(cap[8]) or [],
            }

        checks.append({
            "requirement_id": req_id,
            "capability_id": cap_id,
            "required": bool(required),
            "requirement_status": req_status,
            "requirement_evidence_id": req_evidence,
            "requirement_notes": _json_value(req_notes) or [],
            "observed_status": observed,
            "capability": cap_record,
        })

    # Report only explicit semantic edges here; generic reachability remains navigation evidence.
    semantic_relationships = []
    semantic_types = ("REQUIRES","IMPLEMENTS","IMPLEMENTED_BY","USES_CLIENT_CAPABILITY","VALIDATED_BY")
    for row in con.execute(
        "SELECT relationship_id,source_node,target_node,relationship,evidence_id,confidence,status,metadata_json FROM entity_relationships WHERE source_node=? ORDER BY relationship_id",
        (fid,),
    ):
        if row[3] not in semantic_types:
            continue
        semantic_relationships.append({
            "relationship_id":row[0],"source_node":row[1],"target_node":row[2],
            "relationship":row[3],"evidence_id":row[4],"confidence":row[5],
            "status":row[6],"metadata":_json_value(row[7]) or {},
        })

    implementations = []
    for row in con.execute(
        "SELECT implementation_id, artifact_id, artifact_type, status, language, path, symbol, change_type, "
        "scope, requires_build, build_target, evidence_id, notes_json "
        "FROM implementations WHERE feature_id=? ORDER BY implementation_id",
        (fid,),
    ):
        implementations.append({
            "implementation_id": row[0], "artifact_id": row[1], "artifact_type": row[2],
            "status": row[3], "language": row[4], "path": row[5], "symbol": row[6],
            "change_type": row[7], "scope": row[8], "requires_build": bool(row[9]),
            "build_target": row[10], "evidence_id": row[11], "notes": _json_value(row[12]) or [],
        })

    validations = []
    for row in con.execute(
        "SELECT validation_id, run_id, validation_type, subject_id, status, evidence_id, source, target, notes_json "
        "FROM validation_results WHERE subject_id=? ORDER BY validation_id",
        (fid,),
    ):
        validations.append({
            "validation_id": row[0], "run_id": row[1], "validation_type": row[2],
            "subject_id": row[3], "status": row[4], "evidence_id": row[5],
            "source": row[6], "target": row[7], "notes": _json_value(row[8]) or [],
        })

    implementation_statuses = [r["status"] for r in implementations]
    if not implementations:
        implementation_status = "NO_IMPLEMENTATION_RECORDS"
    elif any(s in ("CONTRADICTED","FAILED") for s in implementation_statuses):
        implementation_status = "CONTRADICTED"
    elif all(s == "VERIFIED" for s in implementation_statuses):
        implementation_status = "IMPLEMENTATIONS_VERIFIED"
    elif any(s in ("VERIFIED","IMPLEMENTED") for s in implementation_statuses):
        implementation_status = "IMPLEMENTATIONS_PRESENT_UNVERIFIED"
    else:
        implementation_status = "IMPLEMENTATION_STATUS_UNKNOWN"

    validation_statuses = [r["status"] for r in validations]
    if not validations:
        validation_status = "NO_VALIDATION_RECORDS"
    elif any(s in ("CONTRADICTED","FAILED") for s in validation_statuses):
        validation_status = "VALIDATION_FAILED"
    elif all(s == "VERIFIED" for s in validation_statuses):
        validation_status = "VALIDATIONS_VERIFIED"
    elif any(s == "VERIFIED" for s in validation_statuses):
        validation_status = "PARTIALLY_VALIDATED"
    else:
        validation_status = "VALIDATION_STATUS_UNKNOWN"

    required = [c for c in checks if c["required"]]
    if not required:
        aggregate = "NO_REQUIREMENTS_DECLARED"
    elif any(c["observed_status"] == "CONTRADICTED" for c in required):
        aggregate = "CONTRADICTED"
    elif any(c["observed_status"] == "MISSING" for c in required):
        aggregate = "MISSING_REQUIRED_CAPABILITY"
    elif any(c["observed_status"] == "UNKNOWN" for c in required):
        aggregate = "UNKNOWN_REQUIRED_CAPABILITY"
    elif any(c["observed_status"] == "PRESENT_UNVERIFIED" for c in required):
        aggregate = "REQUIRES_VERIFICATION"
    else:
        aggregate = "REQUIRED_CAPABILITIES_VERIFIED"

    return {
        "schema": SCHEMA,
        "check_id": f"feature-check:{fid}",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "feature": feature,
        "status": aggregate,\n        "dimensions": {\n            "requirements": aggregate,\n            "implementation": implementation_status,\n            "validation": validation_status,\n        },
        "requirements": checks,
        "semantic_relationships": semantic_relationships,
        "implementation_records": implementations,
        "validation_results": validations,
        "notes": [
            "Capability checks are evaluated independently.",
            "Implementation records and validation results are supporting evidence, not substitutes for missing capability evidence.",
            "No single numeric score is produced.",\n            "Requirements, implementation, and validation remain separate status dimensions.",
        ],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", type=Path, default=Path("workbench.db"))
    group = ap.add_mutually_exclusive_group(required=True)
    group.add_argument("--feature")
    group.add_argument("--name")
    ap.add_argument("--json", type=Path)
    args = ap.parse_args()

    con = sqlite3.connect(args.db)
    feature = resolve_feature(con, args.feature or args.name)
    if feature is None:
        result = {
            "schema": SCHEMA,
            "status": "NOT_FOUND_OR_AMBIGUOUS",
            "query": args.feature or args.name,
        }
        if args.json:
            args.json.parent.mkdir(parents=True, exist_ok=True)
            args.json.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        else:
            print(json.dumps(result, indent=2))
        con.close()
        return 2

    result = check_feature(con, feature)
    con.close()
    output = json.dumps(result, indent=2, sort_keys=True)
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(output + "\n", encoding="utf-8")
    else:
        print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
