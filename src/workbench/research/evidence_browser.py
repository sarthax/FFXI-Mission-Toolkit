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


def _uniq(values) -> list[Any]:
    return sorted({value for value in values if value not in (None, "")}, key=lambda value: str(value))


def _display_value(raw: str | None):
    if raw is None:
        return None
    return _json(raw, raw)


def _side(
    *,
    label: str,
    records: list[dict[str,Any]],
    evidence_ids: list[str] | None = None,
    value: Any = None,
    statuses: list[str] | None = None,
) -> dict[str,Any]:
    ids=_uniq(evidence_ids if evidence_ids is not None else [row.get("evidence_id") for row in records])
    snapshots=_uniq(row.get("source_snapshot_id") for row in records)
    status_values=_uniq(statuses if statuses is not None else [row.get("status") for row in records])
    confidence=_uniq(row.get("confidence") for row in records)
    return {
        "label":label,
        "value":value,
        "statuses":status_values,
        "confidence":confidence,
        "source_snapshots":snapshots,
        "evidence_ids":ids,
        "records":records,
        "evidence":[],
    }


def _comparison_state(sides: list[dict[str,Any]], *, flagged_only: bool = False) -> str:
    if flagged_only:
        return "FLAGGED_ONLY"
    if len(sides) < 2:
        return "INCOMPLETE"
    if all(side.get("evidence_ids") for side in sides):
        return "EVIDENCE_BACKED_SIDES"
    return "INCOMPLETE_EVIDENCE"


def _session_evidence_ids(con: sqlite3.Connection, tables: set[str], research_session_id: str | None) -> set[str]:
    if not research_session_id:
        return set()
    ids: set[str]=set()
    if "research_tool_calls" in tables:
        for row in con.execute(
            "SELECT evidence_ids_json FROM research_tool_calls WHERE research_session_id=?",
            (research_session_id,),
        ).fetchall():
            ids.update(str(value) for value in _json(row["evidence_ids_json"],[]) if value)
    if "research_proposals" in tables:
        for row in con.execute(
            "SELECT supporting_evidence_ids_json,contradicting_evidence_ids_json "
            "FROM research_proposals WHERE research_session_id=?",
            (research_session_id,),
        ).fetchall():
            ids.update(str(value) for value in _json(row["supporting_evidence_ids_json"],[]) if value)
            ids.update(str(value) for value in _json(row["contradicting_evidence_ids_json"],[]) if value)
    return ids


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
                ref={
                    "kind":table,
                    "record_id":item[id_col],
                    "subject_id":item[subject_col],
                    "status":item[status_col] if status_col else None,
                }
                if table == "findings":
                    detail=con.execute(
                        "SELECT field,value_json,confidence,source_snapshot_id FROM findings WHERE finding_id=?",
                        (item[id_col],),
                    ).fetchone()
                    if detail:
                        ref.update({
                            "field":detail["field"],
                            "value":_display_value(detail["value_json"]),
                            "confidence":detail["confidence"],
                            "source_snapshot_id":detail["source_snapshot_id"],
                        })
                elif table == "capability_observations":
                    detail=con.execute(
                        "SELECT value_json,source_snapshot_id FROM capability_observations WHERE observation_id=?",
                        (item[id_col],),
                    ).fetchone()
                    if detail:
                        ref.update({
                            "field":"capability_observation",
                            "value":_display_value(detail["value_json"]),
                            "source_snapshot_id":detail["source_snapshot_id"],
                        })
                refs.append(ref)

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
        evidence["reference_kinds"]=_uniq(ref.get("kind") for ref in refs)
        evidence["referenced_subjects"]=_uniq(ref.get("subject_id") for ref in refs)
        evidence["referenced_snapshots"]=_uniq(ref.get("source_snapshot_id") for ref in refs)
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
        session_evidence_ids=_session_evidence_ids(con,tables,research_session_id)
        items: list[dict[str,Any]]=[]

        if "findings" in tables:
            findings=[dict(row) for row in con.execute(
                "SELECT * FROM findings ORDER BY subject_id,field,finding_id"
            ).fetchall()]
            for row in findings:
                if str(row.get("status") or "").upper()=="CONTRADICTED":
                    sides=[_side(
                        label="Explicit contradicted finding",
                        records=[row],
                        value=_display_value(row.get("value_json")),
                    )]
                    items.append({
                        "kind":"EXPLICIT_FINDING_CONTRADICTION",
                        "subject_id":row["subject_id"],
                        "field":row["field"],
                        "status":row["status"],
                        "evidence_ids":[row["evidence_id"]] if row.get("evidence_id") else [],
                        "records":[row],
                        "sides":sides,
                        "comparison_state":_comparison_state(sides, flagged_only=True),
                        "summary":"Finding is explicitly marked CONTRADICTED; no opposing canonical side is implied.",
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
                    side_groups: dict[str,list[dict[str,Any]]]={}
                    for row in rows:
                        side_groups.setdefault(str(row.get("value_json") or "null"),[]).append(row)
                    sides=[
                        _side(
                            label=f"Recorded value {index}",
                            records=group,
                            value=_display_value(group[0].get("value_json")),
                        )
                        for index,group in enumerate(side_groups.values(), start=1)
                    ]
                    items.append({
                        "kind":"FINDING_VALUE_CONFLICT",
                        "subject_id":subject,
                        "field":field,
                        "status":"CONTRADICTED",
                        "evidence_ids":_uniq(r.get("evidence_id") for r in rows),
                        "records":rows,
                        "sides":sides,
                        "comparison_state":_comparison_state(sides),
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
                    side_groups: dict[tuple[str,str],list[dict[str,Any]]]={}
                    for row in group:
                        side_groups.setdefault(
                            (str(row.get("status") or ""),str(row.get("value_json") or "null")),[]
                        ).append(row)
                    sides=[
                        _side(
                            label=f"Observation {index}",
                            records=side_rows,
                            value=_display_value(side_rows[0].get("value_json")),
                        )
                        for index,side_rows in enumerate(side_groups.values(), start=1)
                    ]
                    items.append({
                        "kind":"CAPABILITY_OBSERVATION_CONFLICT",
                        "subject_id":capability,
                        "field":"capability_observation",
                        "status":"CONTRADICTED",
                        "evidence_ids":_uniq(r.get("evidence_id") for r in group),
                        "records":group,
                        "sides":sides,
                        "comparison_state":_comparison_state(sides),
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
                support=_json(row["supporting_evidence_ids_json"],[])
                contradict=_json(row["contradicting_evidence_ids_json"],[])
                if not contradict and str(row["status"]).upper()!="CONTRADICTED":
                    continue
                proposal_record={
                    "proposal_id":row["proposal_id"],
                    "research_session_id":row["research_session_id"],
                    "proposal_type":row["proposal_type"],
                    "verification_requirement":row["verification_requirement"],
                }
                sides=[]
                if support:
                    sides.append(_side(
                        label="Supporting evidence",
                        records=[proposal_record],
                        evidence_ids=list(support),
                    ))
                if contradict:
                    sides.append(_side(
                        label="Contradicting evidence",
                        records=[proposal_record],
                        evidence_ids=list(contradict),
                    ))
                items.append({
                    "kind":"RESEARCH_PROPOSAL_CONTRADICTION",
                    "subject_id":row["subject_id"] or row["research_session_id"],
                    "field":row["proposal_type"],
                    "status":row["status"],
                    "evidence_ids":_uniq([*support,*contradict]),
                    "records":[proposal_record],
                    "sides":sides,
                    "comparison_state":_comparison_state(sides),
                    "summary":"Research proposal has evidence recorded on opposing roles.",
                    "research_session_id":row["research_session_id"],
                })

        if subject_id:
            items=[item for item in items if item.get("subject_id")==subject_id]
        if research_session_id:
            items=[
                item for item in items
                if item.get("research_session_id")==research_session_id
                or bool(session_evidence_ids.intersection(item.get("evidence_ids",[])))
            ]

        all_ids={eid for item in items for eid in item.get("evidence_ids",[]) if eid}
        evidence=_evidence_lookup(con,all_ids)
        for item in items:
            item["evidence"]=[evidence[eid] for eid in item.get("evidence_ids",[]) if eid in evidence]
            item["missing_evidence_ids"]=[eid for eid in item.get("evidence_ids",[]) if eid not in evidence]
            item["evidence_types"]=_uniq(e.get("evidence_type") for e in item["evidence"])
            item["sources"]=_uniq(e.get("source") for e in item["evidence"])
            item["snapshots"]=_uniq([
                *(e.get("snapshot") for e in item["evidence"]),
                *(snapshot for side in item.get("sides",[]) for snapshot in side.get("source_snapshots",[])),
            ])
            for side in item.get("sides",[]):
                side["evidence"]=[evidence[eid] for eid in side.get("evidence_ids",[]) if eid in evidence]
                side["missing_evidence_ids"]=[eid for eid in side.get("evidence_ids",[]) if eid not in evidence]
                side["evidence_types"]=_uniq(e.get("evidence_type") for e in side["evidence"])
                side["sources"]=_uniq(e.get("source") for e in side["evidence"])
            if item.get("missing_evidence_ids") and item.get("comparison_state")=="EVIDENCE_BACKED_SIDES":
                item["comparison_state"]="INCOMPLETE_EVIDENCE"

        if evidence_type:
            wanted=evidence_type.strip().upper()
            items=[item for item in items if wanted in {x.upper() for x in item.get("evidence_types",[])}]

        type_counts: dict[str,int]={}
        state_counts: dict[str,int]={}
        for item in items:
            type_counts[item["kind"]]=type_counts.get(item["kind"],0)+1
            state=item.get("comparison_state") or "UNKNOWN"
            state_counts[state]=state_counts.get(state,0)+1
        matched_total=len(items)
        bounded_limit=max(0,int(limit))
        items=items[:bounded_limit]
        available_evidence_types=sorted({
            str(row["evidence_type"])
            for row in con.execute("SELECT DISTINCT evidence_type FROM evidence ORDER BY evidence_type").fetchall()
        }) if "evidence" in tables else []
        return {
            "research_session_id":research_session_id,
            "subject_id":subject_id,
            "evidence_type":evidence_type,
            "total":len(items),
            "matched_total":matched_total,
            "limit":bounded_limit,
            "truncated":matched_total>len(items),
            "type_counts":type_counts,
            "state_counts":state_counts,
            "available_evidence_types":available_evidence_types,
            "items":items,
        }
    finally:
        con.close()
