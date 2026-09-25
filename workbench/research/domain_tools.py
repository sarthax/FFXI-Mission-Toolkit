"""Typed read-only domain tools over the canonical Workbench graph."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

import feature_checker


def _json(raw):
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except (TypeError,json.JSONDecodeError):
        return raw


class WorkbenchDomainReader:
    def __init__(self, db_path: Path):
        self.db_path=Path(db_path)

    def _connect(self) -> sqlite3.Connection:
        con=sqlite3.connect(f"file:{self.db_path}?mode=ro",uri=True)
        con.row_factory=sqlite3.Row
        return con

    def feature_inspect(self, feature: str) -> dict[str,Any]:
        con=self._connect()
        try:
            resolved=feature_checker.resolve_feature(con,feature)
            if resolved is None:
                return {"status":"NOT_FOUND_OR_AMBIGUOUS","query":feature}
            result=feature_checker.check_feature(con,resolved)
            evidence_ids=set()
            for requirement in result.get("requirements",[]):
                for key in ("requirement_evidence_id",):
                    value=requirement.get(key)
                    if value:
                        evidence_ids.add(value)
                cap=requirement.get("capability") or {}
                if cap.get("evidence_id"):
                    evidence_ids.add(cap["evidence_id"])
                for obs in requirement.get("observations",[]):
                    if obs.get("evidence_id"):
                        evidence_ids.add(obs["evidence_id"])
            for row in result.get("semantic_relationships",[]):
                if row.get("evidence_id"):
                    evidence_ids.add(row["evidence_id"])
            for row in result.get("implementation_records",[]):
                if row.get("evidence_id"):
                    evidence_ids.add(row["evidence_id"])
            for row in result.get("validation_results",[]):
                if row.get("evidence_id"):
                    evidence_ids.add(row["evidence_id"])
            result["evidence_ids"]=sorted(evidence_ids)
            return result
        finally:
            con.close()

    def entity_lookup(
        self,
        value: str,
        *,
        identifier_type: str | None = None,
        limit: int = 20,
    ) -> dict[str,Any]:
        con=self._connect()
        try:
            params=[]
            where=[]
            if identifier_type:
                where.append("ei.identifier_type=?")
                params.append(identifier_type)
            where.append("(ei.identifier_value=? OR e.entity_id=? OR COALESCE(e.display_name,'') LIKE ?)")
            params.extend([value,value,f"%{value}%"])
            rows=con.execute(
                "SELECT DISTINCT e.entity_id,e.entity_type,e.display_name,e.metadata_json "
                "FROM entities e LEFT JOIN entity_identifiers ei ON ei.entity_id=e.entity_id "
                f"WHERE {' AND '.join(where)} ORDER BY e.entity_id LIMIT ?",
                (*params,limit),
            ).fetchall()
            matches=[]
            evidence_ids=set()
            for row in rows:
                entity_id=row["entity_id"]
                identifiers=[
                    dict(item)
                    for item in con.execute(
                        "SELECT identifier_type,identifier_value,source_snapshot_id "
                        "FROM entity_identifiers WHERE entity_id=? ORDER BY identifier_type,identifier_value",
                        (entity_id,),
                    ).fetchall()
                ]
                findings=[]
                for item in con.execute(
                    "SELECT finding_id,analysis_id,field,value_json,status,confidence,evidence_id,"
                    "source_snapshot_id,notes_json FROM findings WHERE subject_id=? ORDER BY finding_id",
                    (entity_id,),
                ).fetchall():
                    record=dict(item)
                    record["value"]=_json(record.pop("value_json"))
                    record["notes"]=_json(record.pop("notes_json")) or []
                    if record.get("evidence_id"):
                        evidence_ids.add(record["evidence_id"])
                    findings.append(record)
                matches.append({
                    "entity_id":entity_id,
                    "entity_type":row["entity_type"],
                    "display_name":row["display_name"],
                    "metadata":_json(row["metadata_json"]) or {},
                    "identifiers":identifiers,
                    "findings":findings,
                })
            return {
                "status":"OK",
                "query":value,
                "identifier_type":identifier_type,
                "matches":matches,
                "evidence_ids":sorted(evidence_ids),
                "truncated":len(matches)>=limit,
            }
        finally:
            con.close()

    def binding_lookup(
        self,
        lua_name: str,
        *,
        class_name: str | None = None,
        limit: int = 30,
    ) -> dict[str,Any]:
        con=self._connect()
        try:
            where=["lower(b.lua_name)=lower(?)"]
            params=[lua_name]
            if class_name:
                where.append("lower(COALESCE(b.class_name,''))=lower(?)")
                params.append(class_name)
            rows=con.execute(
                "SELECT b.binding_id,b.lua_name,b.binding_system,b.cpp_symbol,b.class_name,b.function_id,"
                "b.source_snapshot_id,b.path,b.line,b.evidence_id,b.status,b.notes_json,"
                "f.qualified_name,f.name AS function_name,f.namespace,f.class_name AS function_class,"
                "f.path AS function_path,f.line AS function_line,f.signature_json,f.evidence_id AS function_evidence_id "
                "FROM bindings b LEFT JOIN functions f ON f.function_id=b.function_id "
                f"WHERE {' AND '.join(where)} ORDER BY b.binding_id LIMIT ?",
                (*params,limit),
            ).fetchall()
            matches=[]
            evidence_ids=set()
            for row in rows:
                item=dict(row)
                item["notes"]=_json(item.pop("notes_json")) or []
                item["signature"]=_json(item.pop("signature_json")) or {}
                for key in ("evidence_id","function_evidence_id"):
                    if item.get(key):
                        evidence_ids.add(item[key])
                matches.append(item)
            return {
                "status":"OK",
                "lua_name":lua_name,
                "class_name":class_name,
                "matches":matches,
                "evidence_ids":sorted(evidence_ids),
                "truncated":len(matches)>=limit,
            }
        finally:
            con.close()

    def packet_lookup(self, opcode: str, *, limit: int = 50) -> dict[str,Any]:
        token=opcode.strip()
        if not token:
            return {"status":"ERROR","error":"opcode is required"}
        candidates={token}
        try:
            value=int(token,0)
            candidates.update({
                str(value),
                f"0x{value:03X}",
                f"0x{value:03x}",
                f"packet:{value}",
                f"packet:0x{value:03X}",
                f"packet:0x{value:03x}",
            })
        except ValueError:
            pass
        con=self._connect()
        try:
            clauses=[]
            params=[]
            for candidate in sorted(candidates):
                clauses.extend(["source_node=?","target_node=?"])
                params.extend([candidate,candidate])
            rows=con.execute(
                "SELECT relationship_id,source_node,target_node,relationship,evidence_id,confidence,status,"
                "metadata_json,source_snapshot_id FROM entity_relationships "
                f"WHERE {' OR '.join(clauses)} ORDER BY relationship_id LIMIT ?",
                (*params,limit),
            ).fetchall()
            relationships=[]
            evidence_ids=set()
            function_ids=set()
            for row in rows:
                item=dict(row)
                item["metadata"]=_json(item.pop("metadata_json")) or {}
                if item.get("evidence_id"):
                    evidence_ids.add(item["evidence_id"])
                for node in (item["source_node"],item["target_node"]):
                    if node.startswith("function:") or node.startswith("fn:"):
                        function_ids.add(node)
                relationships.append(item)
            handlers=[]
            if function_ids:
                placeholders=",".join("?" for _ in function_ids)
                for row in con.execute(
                    "SELECT function_id,qualified_name,name,class_name,path,line,source_snapshot_id,evidence_id "
                    f"FROM functions WHERE function_id IN ({placeholders}) ORDER BY function_id",
                    tuple(sorted(function_ids)),
                ).fetchall():
                    item=dict(row)
                    if item.get("evidence_id"):
                        evidence_ids.add(item["evidence_id"])
                    handlers.append(item)
            return {
                "status":"OK",
                "opcode":opcode,
                "relationships":relationships,
                "handlers":handlers,
                "evidence_ids":sorted(evidence_ids),
                "truncated":len(relationships)>=limit,
            }
        finally:
            con.close()

    def server_symbol_lookup(
        self,
        symbol: str,
        *,
        limit: int = 30,
    ) -> dict[str,Any]:
        con=self._connect()
        try:
            rows=con.execute(
                "SELECT function_id,qualified_name,name,namespace,class_name,source_snapshot_id,"
                "path,line,kind,declaration,definition,signature_json,evidence_id,notes_json "
                "FROM functions WHERE qualified_name LIKE ? OR name LIKE ? "
                "ORDER BY definition DESC,qualified_name,function_id LIMIT ?",
                (f"%{symbol}%",f"%{symbol}%",limit),
            ).fetchall()
            matches=[]
            evidence_ids=set()
            for row in rows:
                item=dict(row)
                item["signature"]=_json(item.pop("signature_json")) or {}
                item["notes"]=_json(item.pop("notes_json")) or []
                item["declaration"]=bool(item["declaration"])
                item["definition"]=bool(item["definition"])
                if item.get("evidence_id"):
                    evidence_ids.add(item["evidence_id"])
                bindings=[
                    dict(b)
                    for b in con.execute(
                        "SELECT binding_id,lua_name,binding_system,class_name,status,evidence_id,path,line "
                        "FROM bindings WHERE function_id=? ORDER BY binding_id",
                        (item["function_id"],),
                    ).fetchall()
                ]
                for binding in bindings:
                    if binding.get("evidence_id"):
                        evidence_ids.add(binding["evidence_id"])
                relationships=[]
                for edge in con.execute(
                    "SELECT relationship_id,source_node,target_node,relationship,evidence_id,confidence,status,"
                    "metadata_json,source_snapshot_id FROM entity_relationships "
                    "WHERE source_node=? OR target_node=? ORDER BY relationship_id",
                    (item["function_id"],item["function_id"]),
                ).fetchall():
                    record=dict(edge)
                    record["metadata"]=_json(record.pop("metadata_json")) or {}
                    if record.get("evidence_id"):
                        evidence_ids.add(record["evidence_id"])
                    relationships.append(record)
                item["bindings"]=bindings
                item["relationships"]=relationships
                matches.append(item)
            return {
                "status":"OK",
                "query":symbol,
                "matches":matches,
                "evidence_ids":sorted(evidence_ids),
                "truncated":len(matches)>=limit,
            }
        finally:
            con.close()

    def server_enum_lookup(
        self,
        symbol: str,
        *,
        enum_name: str | None = None,
        limit: int = 50,
    ) -> dict[str,Any]:
        con=self._connect()
        try:
            where=["(symbol LIKE ? OR enum_name LIKE ?)"]
            params=[f"%{symbol}%",f"%{symbol}%"]
            if enum_name:
                where.append("enum_name=?")
                params.append(enum_name)
            rows=con.execute(
                "SELECT enum_id,enum_name,source_snapshot_id,path,line,format,value,symbol,evidence_id,notes_json "
                f"FROM enum_definitions WHERE {' AND '.join(where)} ORDER BY enum_name,symbol,enum_id LIMIT ?",
                (*params,limit),
            ).fetchall()
            matches=[]
            evidence_ids=set()
            for row in rows:
                item=dict(row)
                item["notes"]=_json(item.pop("notes_json")) or []
                if item.get("evidence_id"):
                    evidence_ids.add(item["evidence_id"])
                usage=[]
                for edge in con.execute(
                    "SELECT relationship_id,source_node,target_node,relationship,evidence_id,confidence,status,"
                    "metadata_json,source_snapshot_id FROM entity_relationships "
                    "WHERE target_node=? ORDER BY relationship_id",
                    (item["enum_id"],),
                ).fetchall():
                    record=dict(edge)
                    record["metadata"]=_json(record.pop("metadata_json")) or {}
                    if record.get("evidence_id"):
                        evidence_ids.add(record["evidence_id"])
                    usage.append(record)
                item["usage"]=usage
                matches.append(item)
            return {
                "status":"OK",
                "query":symbol,
                "enum_name":enum_name,
                "matches":matches,
                "evidence_ids":sorted(evidence_ids),
                "truncated":len(matches)>=limit,
            }
        finally:
            con.close()

    def server_build_target_lookup(
        self,
        target: str,
        *,
        limit: int = 30,
    ) -> dict[str,Any]:
        con=self._connect()
        try:
            rows=con.execute(
                "SELECT target_id,name,build_system,path,source_snapshot_id,artifact_id,status,notes_json "
                "FROM build_targets WHERE target_id LIKE ? OR name LIKE ? "
                "ORDER BY name,target_id LIMIT ?",
                (f"%{target}%",f"%{target}%",limit),
            ).fetchall()
            matches=[]
            evidence_ids=set()
            for row in rows:
                item=dict(row)
                item["notes"]=_json(item.pop("notes_json")) or []
                relationships=[]
                for edge in con.execute(
                    "SELECT relationship_id,source_node,target_node,relationship,evidence_id,confidence,status,"
                    "metadata_json,source_snapshot_id FROM entity_relationships "
                    "WHERE target_node=? OR source_node=? ORDER BY relationship_id",
                    (item["target_id"],item["target_id"]),
                ).fetchall():
                    record=dict(edge)
                    record["metadata"]=_json(record.pop("metadata_json")) or {}
                    if record.get("evidence_id"):
                        evidence_ids.add(record["evidence_id"])
                    relationships.append(record)
                item["relationships"]=relationships
                matches.append(item)
            return {
                "status":"OK",
                "query":target,
                "matches":matches,
                "evidence_ids":sorted(evidence_ids),
                "truncated":len(matches)>=limit,
            }
        finally:
            con.close()

    def capability_inspect(
        self,
        capability: str,
        *,
        feature_id: str | None = None,
        limit: int = 50,
    ) -> dict[str,Any]:
        con=self._connect()
        try:
            rows=con.execute(
                "SELECT capability_id,name,capability_type,subject_id,source_snapshot_id,status,"
                "value_json,evidence_id,notes_json FROM capabilities "
                "WHERE capability_id=? OR name LIKE ? ORDER BY capability_id LIMIT ?",
                (capability,f"%{capability}%",limit),
            ).fetchall()
            matches=[]
            evidence_ids=set()
            for row in rows:
                item=dict(row)
                item["value"]=_json(item.pop("value_json"))
                item["notes"]=_json(item.pop("notes_json")) or []
                if item.get("evidence_id"):
                    evidence_ids.add(item["evidence_id"])
                observations=[]
                for obs in con.execute(
                    "SELECT observation_id,source_snapshot_id,status,value_json,evidence_id,notes_json "
                    "FROM capability_observations WHERE capability_id=? "
                    "ORDER BY source_snapshot_id,observation_id",
                    (item["capability_id"],),
                ).fetchall():
                    record=dict(obs)
                    record["value"]=_json(record.pop("value_json"))
                    record["notes"]=_json(record.pop("notes_json")) or []
                    if record.get("evidence_id"):
                        evidence_ids.add(record["evidence_id"])
                    observations.append(record)
                requirements=[]
                req_sql=(
                    "SELECT requirement_id,feature_id,required,status,evidence_id,notes_json "
                    "FROM capability_requirements WHERE capability_id=?"
                )
                req_params=[item["capability_id"]]
                if feature_id:
                    req_sql+=" AND feature_id=?"
                    req_params.append(feature_id)
                req_sql+=" ORDER BY feature_id,requirement_id"
                for req in con.execute(req_sql,tuple(req_params)).fetchall():
                    record=dict(req)
                    record["required"]=bool(record["required"])
                    record["notes"]=_json(record.pop("notes_json")) or []
                    if record.get("evidence_id"):
                        evidence_ids.add(record["evidence_id"])
                    requirements.append(record)
                item["observations"]=observations
                item["requirements"]=requirements
                matches.append(item)
            return {
                "status":"OK",
                "query":capability,
                "feature_id":feature_id,
                "matches":matches,
                "evidence_ids":sorted(evidence_ids),
                "truncated":len(matches)>=limit,
            }
        finally:
            con.close()

    def migration_inspect(
        self,
        migration: str,
        *,
        feature_id: str | None = None,
        limit: int = 100,
    ) -> dict[str,Any]:
        con=self._connect()
        try:
            if feature_id:
                rows=con.execute(
                    "SELECT migration_id,feature_id,source_snapshot_id,target_snapshot_id,status,metadata_json "
                    "FROM migrations WHERE feature_id=? ORDER BY migration_id LIMIT ?",
                    (feature_id,limit),
                ).fetchall()
            else:
                rows=con.execute(
                    "SELECT migration_id,feature_id,source_snapshot_id,target_snapshot_id,status,metadata_json "
                    "FROM migrations WHERE migration_id=? OR migration_id LIKE ? OR COALESCE(feature_id,'') LIKE ? "
                    "ORDER BY migration_id LIMIT ?",
                    (migration,f"%{migration}%",f"%{migration}%",limit),
                ).fetchall()
            matches=[]
            evidence_ids=set()
            for row in rows:
                item=dict(row)
                item["metadata"]=_json(item.pop("metadata_json")) or {}
                actions=[]
                for action in con.execute(
                    "SELECT action_id,action,artifact_id,status,reason,metadata_json "
                    "FROM migration_actions WHERE migration_id=? ORDER BY action_id",
                    (item["migration_id"],),
                ).fetchall():
                    record=dict(action)
                    record["metadata"]=_json(record.pop("metadata_json")) or {}
                    actions.append(record)
                relationships=[]
                if item.get("feature_id"):
                    for edge in con.execute(
                        "SELECT relationship_id,source_node,target_node,relationship,evidence_id,confidence,status,"
                        "metadata_json,source_snapshot_id FROM entity_relationships "
                        "WHERE source_node=? OR target_node=? ORDER BY relationship_id",
                        (item["feature_id"],item["feature_id"]),
                    ).fetchall():
                        record=dict(edge)
                        record["metadata"]=_json(record.pop("metadata_json")) or {}
                        if record.get("evidence_id"):
                            evidence_ids.add(record["evidence_id"])
                        relationships.append(record)
                item["actions"]=actions
                item["feature_relationships"]=relationships
                matches.append(item)
            return {
                "status":"OK",
                "query":migration,
                "feature_id":feature_id,
                "matches":matches,
                "evidence_ids":sorted(evidence_ids),
                "truncated":len(matches)>=limit,
            }
        finally:
            con.close()

    def validation_inspect(
        self,
        *,
        subject_id: str | None = None,
        run_id: str | None = None,
        feature_id: str | None = None,
        limit: int = 100,
    ) -> dict[str,Any]:
        if not any((subject_id,run_id,feature_id)):
            return {"status":"ERROR","error":"subject_id, run_id, or feature_id is required"}
        con=self._connect()
        try:
            runs=[]
            results=[]
            evidence_ids=set()

            if run_id:
                run_rows=con.execute(
                    "SELECT run_id,name,source_snapshot_id,target_snapshot_id,feature_id,status,"
                    "started_at,finished_at,metadata_json FROM validation_runs WHERE run_id=?",
                    (run_id,),
                ).fetchall()
            elif feature_id:
                run_rows=con.execute(
                    "SELECT run_id,name,source_snapshot_id,target_snapshot_id,feature_id,status,"
                    "started_at,finished_at,metadata_json FROM validation_runs "
                    "WHERE feature_id=? ORDER BY started_at DESC LIMIT ?",
                    (feature_id,limit),
                ).fetchall()
            else:
                run_rows=[]

            for row in run_rows:
                item=dict(row)
                item["metadata"]=_json(item.pop("metadata_json")) or {}
                runs.append(item)

            result_where=[]
            params=[]
            if subject_id:
                result_where.append("subject_id=?")
                params.append(subject_id)
            if run_id:
                result_where.append("run_id=?")
                params.append(run_id)
            if feature_id and runs:
                result_where.append("run_id IN ("+",".join("?" for _ in runs)+")")
                params.extend([row["run_id"] for row in runs])

            if result_where:
                for row in con.execute(
                    "SELECT validation_id,run_id,validation_type,subject_id,status,evidence_id,source,target,notes_json "
                    f"FROM validation_results WHERE {' AND '.join(result_where)} ORDER BY validation_id LIMIT ?",
                    (*params,limit),
                ).fetchall():
                    item=dict(row)
                    item["notes"]=_json(item.pop("notes_json")) or []
                    if item.get("evidence_id"):
                        evidence_ids.add(item["evidence_id"])
                    results.append(item)

            return {
                "status":"OK",
                "query":{"subject_id":subject_id,"run_id":run_id,"feature_id":feature_id},
                "runs":runs,
                "results":results,
                "evidence_ids":sorted(evidence_ids),
                "truncated":len(results)>=limit,
            }
        finally:
            con.close()
