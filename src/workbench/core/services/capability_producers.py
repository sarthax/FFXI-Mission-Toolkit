"""Snapshot capability producers from deterministic Workbench analyzers.

Capability records describe reusable concepts. Snapshot-specific state belongs in
CapabilityObservation. These helpers intentionally do not create feature requirements;
a feature/domain analyzer must explicitly declare which capabilities it requires.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

from workbench.core import graph
from workbench.core.schema import Capability, CapabilityObservation


def _slug(value: Any) -> str:
    raw=json.dumps(value,sort_keys=True,default=str,separators=(",",":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _persist(
    con,
    *,
    capability_id: str,
    name: str,
    capability_type: str,
    subject_id: str | None,
    snapshot_id: str,
    status: str,
    value: Any,
    evidence_id: str | None = None,
    notes: list[str] | None = None,
) -> tuple[str,str]:
    graph.insert_record(con,Capability(
        capability_id=capability_id,
        name=name,
        capability_type=capability_type,
        subject_id=subject_id,
        source_snapshot_id=None,
        status="UNKNOWN",
        value={"snapshot_scoped":True},
        evidence_id=None,
        notes=["Logical capability concept; snapshot state is stored in capability_observations."],
    ))
    observation_id=f"capability-observation:{snapshot_id}:{_slug(capability_id)}"
    graph.insert_record(con,CapabilityObservation(
        observation_id=observation_id,
        capability_id=capability_id,
        source_snapshot_id=snapshot_id,
        status=status,
        value=value,
        evidence_id=evidence_id,
        notes=list(notes or ()),
    ))
    return capability_id,observation_id


_SCHEMA_STATUS={
    "FULL_PARSE_MAPPING":"VERIFIED",
    "PARTIAL_FIELD_MAPPING":"INFERRED",
    "NO_LOGICAL_MAPPING":"UNKNOWN",
    "IDENTITY_MAPPING_GAP":"CONTRADICTED",
}


def persist_schema_coverage_capabilities(
    con,
    payload: dict[str,Any],
    *,
    snapshot_id: str,
) -> dict[str,int]:
    """Persist one capability observation per logical server table mapping."""
    count=0
    for row in payload.get("tables",[]):
        logical_type=str(row["logical_type"])
        _persist(
            con,
            capability_id=f"capability:server-schema:{logical_type}",
            name=f"server_schema:{logical_type}",
            capability_type="SERVER_SCHEMA",
            subject_id=f"server-schema:{logical_type}",
            snapshot_id=snapshot_id,
            status=_SCHEMA_STATUS.get(str(row.get("status")),"UNKNOWN"),
            value={
                "profile_id":payload.get("profile_id"),
                "family":payload.get("family"),
                "physical_table":row.get("physical_table"),
                "coverage_status":row.get("status"),
                "identity_fields":row.get("identity_fields",[]),
                "mapped_logical_fields":row.get("mapped_logical_fields",[]),
                "unmapped_parsed_fields":row.get("unmapped_parsed_fields",[]),
                "missing_identity_mappings":row.get("missing_identity_mappings",[]),
            },
            notes=["Produced from deterministic server schema mapping coverage."],
        )
        count+=1
    con.commit()
    return {"capabilities":count,"observations":count}


_BINDING_STATUS={
    "EXACT_MATCH":"INFERRED",
    "REPRESENTATION_DRIFT":"INFERRED",
    "RENAMED_CLASS_DRIFT_CANDIDATE":"INFERRED",
    "IMPLEMENTATION_DRIFT":"INFERRED",
    "MISSING_BINDING":"UNKNOWN",
    "UNRESOLVED":"UNKNOWN",
    "AMBIGUOUS":"UNKNOWN",
}


def persist_binding_compatibility_capabilities(
    con,
    payload: dict[str,Any],
) -> dict[str,int]:
    """Persist target-snapshot binding availability/compatibility observations.

    Structural compatibility remains INFERRED even for exact indexed matches.
    MISSING_BINDING remains UNKNOWN because the analyzer scopes absence to
    INDEXED_SURFACE_ONLY.
    """
    target_snapshot_id=payload.get("target_snapshot_id")
    if not target_snapshot_id:
        raise ValueError("binding compatibility payload requires target_snapshot_id")
    count=0
    for row in payload.get("results",[]):
        source=row.get("source") or {}
        lua_name=str(source.get("lua_name") or "")
        class_name=str(source.get("class_name") or "")
        if not lua_name:
            continue
        identity={"class_name":class_name,"lua_name":lua_name}
        cap_id=f"capability:lua-binding:{_slug(identity)}"
        evidence=(row.get("evidence") or {}).get("source",{}).get("evidence_id")
        _persist(
            con,
            capability_id=cap_id,
            name=f"lua_binding:{class_name or '*'}:{lua_name}",
            capability_type="LUA_BINDING",
            subject_id=source.get("binding_id"),
            snapshot_id=str(target_snapshot_id),
            status=_BINDING_STATUS.get(str(row.get("category")),"UNKNOWN"),
            value={
                "category":row.get("category"),
                "confidence":row.get("confidence"),
                "match_basis":row.get("match_basis",[]),
                "changed_fields":row.get("changed_fields",[]),
                "absence_scope":row.get("absence_scope"),
                "source_snapshot_id":payload.get("source_snapshot_id"),
                "target_candidates":[candidate.get("binding_id") for candidate in row.get("target_candidates",[])],
            },
            evidence_id=evidence,
            notes=["Indexed structural binding comparison only; runtime behavior is not verified."],
        )
        count+=1
    con.commit()
    return {"capabilities":count,"observations":count}


_LIVE_STATUS={
    "VERIFIED":"VERIFIED",
    "CONTRADICTED":"CONTRADICTED",
    "MISSING":"MISSING",
    "FAILED":"FAILED",
    "AMBIGUOUS":"UNKNOWN",
    "UNKNOWN":"UNKNOWN",
}


def persist_live_target_capability(
    con,
    payload: dict[str,Any],
) -> dict[str,int]:
    """Persist aggregate live-target DB representation status for one logical table."""
    snapshot_id=payload.get("target_snapshot_id")
    logical_type=payload.get("logical_type")
    if not snapshot_id or not logical_type:
        raise ValueError("live target payload requires target_snapshot_id and logical_type")
    status=_LIVE_STATUS.get(str(payload.get("status")),"UNKNOWN")
    _persist(
        con,
        capability_id=f"capability:live-target:{logical_type}",
        name=f"live_target:{logical_type}",
        capability_type="LIVE_TARGET_DB",
        subject_id=f"server-schema:{logical_type}",
        snapshot_id=str(snapshot_id),
        status=status,
        value={
            "logical_type":logical_type,
            "target_table":payload.get("target_table"),
            "live_status":payload.get("status"),
            "result_count":len(payload.get("results",[])),
        },
        notes=[
            "Produced from read-only live target database validation.",
            "Database representation only; runtime behavior remains a separate validation dimension.",
        ],
    )
    con.commit()
    return {"capabilities":1,"observations":1}
