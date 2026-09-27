"""Read-only contradiction discovery and canonical evidence drill-down for ResearchSession UI."""
from __future__ import annotations

import json
from pathlib import Path
import sqlite3
from typing import Any


def _connect(db_path: Path) -> sqlite3.Connection:
    con=sqlite3.connect(Path(db_path))
    con.row_factory=sqlite3.Row
    return con


def _tables(con: sqlite3.Connection) -> set[str]:
    return {row[0] for row in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}


def _json(raw: str | None, default):
    try:
        return json.loads(raw) if raw else default
    except (TypeError, ValueError, json.JSONDecodeError):
        return default


def evidence_record(db_path: Path, evidence_id: str) -> dict[str, Any] | None:
    """Return one canonical Evidence row plus every known table/session reference."""
    con=_connect(db_path)
    try:
        tables=_tables(con)
        if "evidence" not in tables:
            return None
        row=con.execute("SELECT * FROM evidence WHERE evidence_id=?",(evidence_id,)).fetchone()
        if row is None:
            return None
        evidence=dict(row)
        refs: list[dict[str,Any]]=[]

        specs=(
            ("findings","finding_id","subject_id","status"),
            ("entity_relationships","relationship_id","source_node","status"),
            ("validation_results","validation_id","subject_id","status"),
            ("capabilities","capability_id","subject_id","status"),
            ("capability_observations","observation_id","capability_id","status"),
            ("capability_requirements","requirement_id","feature_id","status"),
            ("functions","function_id","qualified_name",None),
            ("bindings","binding_id","lua_name","status"),
            ("enum_definitions","enum_id","symbol",None),
            ("implementations","implementation_id","feature_id","status"),
        )
        for table,id_col,subject_col,status_col in specs:
            if table not in tables:
                continue
            cols=[id_col,subject_col]
            if status_col:
                cols.append(status_col)
            sql=f"SELECT {','.join(cols)} FROM {table} WHERE evidence_id=?"
            for item in con.execute(sql,(evidence_id,)).fetchall():
                refs.append({
                    "kind":table,
                    "record_id":item[id_col],
                    "subject_id":item[subject_col],
                    "status":item[status_col] if status_col else None,
                })

        if "research_tool_calls" in tables:
            for call in con.execute(
                "SELECT research_session_id,sequence_no,tool_name,status,evidence_ids_json "
                "FROM research_tool_calls ORDER BY research_session_id,sequence_no"
            ).fetchall():
                ids=_json(call["evidence_ids_json"],[])
                if evidence_id in ids:
                    refs.append({
                        "kind":"research_tool_call",
                        "record_id":f"{call['research_session_id']}:{call['sequence_no']}",
                        "subject_id":call["research_session_id"],
                        "status":call["status"],
                        "tool_name":call["tool_name"],
                    })

        if "research_proposals" in tables:
            for proposal in con.execute(
                "SELECT proposal_id,research_session_id,proposal_type,subject_id,status,"
                "supporting_evidence_ids_json,contradicting_evidence_ids_json "
                "FROM research_proposals ORDER BY created_at,proposal_id"
            ).fetchall():
                support=_json(proposal["supporting_evidence_ids_json"],[])
                contradict=_json(proposal["contradicting_evidence_ids_json"],[])
                roles=[]
                if evidence_id in support:
                    roles.append("SUPPORTING")
                if evidence_id in contradict:
                    roles.append("CONTRADICTING")
                if roles:
                    refs.append({
                        "kind":"research_proposal",
                        "record_id":proposal["proposal_id"],
                        "subject_id":proposal["subject_id"] or proposal["research_session_id"],
                        "status":proposal["status"],
                        "proposal_type":proposal["proposal_type"],
                        "evidence_roles":roles,
                        "research_session_id":proposal["research_session_id"],
                    })

        evidence["references"]=refs
        evidence["reference_count"]=len(refs)
        return evidence
    finally:
        con.close()


def _evidence_lookup(con: sqlite3.Connection, ids: set[str]) -> dict[str,dict[str,Any]]:
    if not ids or "evidence" not in _tables(con):
        return {}
    placeholders=",".join("?" for _ in ids)
    return {
        row["evidence_id"]:dict(row)
        for row in con.execute(
            f"SELECT * FROM evidence WHERE evidence_id IN ({placeholders})",
            tuple(sorted(ids)),
        ).fetchall()
    }


def list_contradictions(
    db_path: Path,
    *,
    research_session_id: str | None = None,
    subject_id: str | None = None,
    evidence_type: str | None = None,
    limit: int = 250,
) -> dict[str,Any]:
    """Find explicit and value-conflict contradictions without promoting them to truth."""
    con=_connect(db_path)
    try:
        tables=_tables(con)
        items: list[dict[str,Any]]=[]

        if "findings" in tables:
            findings=[dict(row) for row in con.execute(
                "SELECT * FROM findings ORDER BY subject_id,field,finding_id"
            ).fetchall()]
            for row in findings:
                if str(row.get("status") or "").upper()=="CONTRADICTED":
                    items.append({
                        "kind":"EXPLICIT_FINDING_CONTRADICTION",
                        "subject_id":row["subject_id"],
                        "field":row["field"],
                        "status":row["status"],
                        "evidence_ids":[row["evidence_id"]] if row.get("evidence_id") else [],
                        "records":[row],
                        "summary":"Finding is explicitly marked CONTRADICTED.",
                    })
            groups: dict[tuple[str,str],list[dict[str,Any]]]={}
            for row in findings:
                if not row.get("field"):
                    continue
                groups.setdefault((row["subject_id"],row["field"]),[]).append(row)
            for (subject,field),rows in groups.items():
                values={str(row.get("value_json") or "null") for row in rows}
                sources={str(row.get("source_snapshot_id") or "") for row in rows}
                if len(values)>1 and len(rows)>1 and (len(sources)>1 or len({r.get("evidence_id") for r in rows})>1):
                    items.append({
                        "kind":"FINDING_VALUE_CONFLICT",
                        "subject_id":subject,
                        "field":field,
                        "status":"CONTRADICTED",
                        "evidence_ids":[r["evidence_id"] for r in rows if r.get("evidence_id")],
                        "records":rows,
                        "summary":f"{len(values)} distinct values are recorded for the same subject/field.",
                    })

        if "capability_observations" in tables:
            rows=[dict(row) for row in con.execute(
                "SELECT * FROM capability_observations ORDER BY capability_id,source_snapshot_id,observation_id"
            ).fetchall()]
            groups: dict[str,list[dict[str,Any]]]={}
            for row in rows:
                groups.setdefault(row["capability_id"],[]).append(row)
            for capability,group in groups.items():
                signals={(str(r.get("status") or ""),str(r.get("value_json") or "null")) for r in group}
                if len(signals)>1 and len({r["source_snapshot_id"] for r in group})>1:
                    items.append({
                        "kind":"CAPABILITY_OBSERVATION_CONFLICT",
                        "subject_id":capability,
                        "field":"capability_observation",
                        "status":"CONTRADICTED",
                        "evidence_ids":[r["evidence_id"] for r in group if r.get("evidence_id")],
                        "records":group,
                        "summary":f"Capability observations disagree across {len({r['source_snapshot_id'] for r in group})} snapshots.",
                    })

        if "research_proposals" in tables:
            sql=(
                "SELECT proposal_id,research_session_id,proposal_type,subject_id,status,"
                "supporting_evidence_ids_json,contradicting_evidence_ids_json,verification_requirement "
                "FROM research_proposals"
            )
            params: list[Any]=[]
            if research_session_id:
                sql += " WHERE research_session_id=?"
                params.append(research_session_id)
            sql += " ORDER BY created_at,proposal_id"
            for row in con.execute(sql,params).fetchall():
                contradict=_json(row["contradicting_evidence_ids_json"],[])
                if not contradict and str(row["status"]).upper()!="CONTRADICTED":
                    continue
                items.append({
                    "kind":"RESEARCH_PROPOSAL_CONTRADICTION",
                    "subject_id":row["subject_id"] or row["research_session_id"],
                    "field":row["proposal_type"],
                    "status":row["status"],
                    "evidence_ids":list(contradict),
                    "records":[{
                        "proposal_id":row["proposal_id"],
                        "research_session_id":row["research_session_id"],
                        "proposal_type":row["proposal_type"],
                        "verification_requirement":row["verification_requirement"],
                    }],
                    "summary":"Research proposal has contradicting evidence.",
                    "research_session_id":row["research_session_id"],
                })

        if subject_id:
            items=[item for item in items if item.get("subject_id")==subject_id]

        all_ids={eid for item in items for eid in item.get("evidence_ids",[]) if eid}
        evidence=_evidence_lookup(con,all_ids)
        for item in items:
            item["evidence"]=[evidence[eid] for eid in item.get("evidence_ids",[]) if eid in evidence]
            item["evidence_types"]=sorted({str(e.get("evidence_type") or "") for e in item["evidence"] if e.get("evidence_type")})

        if evidence_type:
            wanted=evidence_type.strip().upper()
            items=[item for item in items if wanted in {x.upper() for x in item.get("evidence_types",[])}]

        items=items[:max(0,int(limit))]
        type_counts: dict[str,int]={}
        for item in items:
            type_counts[item["kind"]]=type_counts.get(item["kind"],0)+1
        available_evidence_types=sorted({
            str(row["evidence_type"])
            for row in con.execute("SELECT DISTINCT evidence_type FROM evidence ORDER BY evidence_type").fetchall()
        }) if "evidence" in tables else []
        return {
            "research_session_id":research_session_id,
            "subject_id":subject_id,
            "evidence_type":evidence_type,
            "total":len(items),
            "type_counts":type_counts,
            "available_evidence_types":available_evidence_types,
            "items":items,
        }
    finally:
        con.close()
