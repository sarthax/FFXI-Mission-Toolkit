#!/usr/bin/env python3
"""Extract conservative C++ dependency edges from includes, bindings, enums, and packet references."""
from __future__ import annotations
import argparse,json,re
from dataclasses import asdict
from pathlib import Path
from source_snapshot import snapshot_id
from workbench_schema import AnalysisResult, DependencyEdge
from cpp_api_index import index as index_api

INCLUDE_RE=re.compile(r'^\s*#\s*include\s*[<"]([^>"]+)[>"]',re.M)
ENUM_USE_RE=re.compile(r'\b([A-Za-z_]\w*)::([A-Za-z_]\w*)\b')
PACKET_RE=re.compile(r'\b(?:Packet|CBasePacket|GP_SERV_COMMAND|GP_SERV|GP_CLI)\b[^\n;]*',re.I)

def source_files(root):
    return [p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in {".cpp",".cc",".cxx",".h",".hpp",".hh",".hxx"}]

def index(root):
    edges=[]
    for p in source_files(root):
        text=p.read_text(encoding="utf-8",errors="replace")
        src=p.relative_to(root).as_posix()
        for inc in INCLUDE_RE.findall(text):
            edges.append(DependencyEdge(
                edge_id=f"include:{src}:{inc}",source_node=src,target_node=inc,relationship="IMPORTS",
                confidence="VERIFIED",status="DISCOVERED",discovered_by="cpp_dependency_index",
                source_location=src,notes=["Direct #include directive."]
            ))
        for ns,sym in ENUM_USE_RE.findall(text):
            if ns.lower() in {"std","boost","fmt","sol","lua"}: continue
            edges.append(DependencyEdge(
                edge_id=f"symbol-use:{src}:{ns}::{sym}",source_node=src,target_node=f"{ns}::{sym}",
                relationship="USES_ENUM",confidence="INFERRED",status="DISCOVERED",
                discovered_by="cpp_dependency_index",source_location=src,
                notes=["Namespace-qualified symbol use; semantic type is not proven by regex."]
            ))
        if PACKET_RE.search(text):
            edges.append(DependencyEdge(
                edge_id=f"packet-ref:{src}",source_node=src,target_node="PACKET_REFERENCE",
                relationship="USES_PACKET",confidence="INFERRED",status="DISCOVERED",
                discovered_by="cpp_dependency_index",source_location=src,
                notes=["Packet-related token detected; exact opcode/handler mapping requires semantic or packet index evidence."]
            ))
    return edges

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("root",type=Path); ap.add_argument("--json",type=Path); args=ap.parse_args()
    sid=snapshot_id(args.root)
    edges=index(args.root)
    sid=snapshot_id(args.root)
    for edge in edges:
        edge.source_snapshot_id=sid
    # Resolve exact symbols through the API index. This upgrades identity only; it does not
    # claim that every namespace-qualified token is semantically an enum.
    try:
        _funcs, enum_defs, _bindings = index_api(args.root)
        enum_symbols={e.symbol for e in enum_defs}
        for edge in edges:
            if edge.relationship == "USES_ENUM" and edge.target_node in enum_symbols:
                edge.confidence="VERIFIED"
                edge.notes.append("Exact symbol exists in extracted enum/constant index; semantic enum classification remains unproven.")
    except Exception as exc:
        edges.append(DependencyEdge(
            edge_id="api-resolution-error", source_node=str(args.root), target_node="cpp-api-index",
            relationship="REFERENCES", confidence="UNKNOWN", status="UNKNOWN",
            discovered_by="cpp_dependency_index", source_location=str(args.root), source_snapshot_id=sid,
            notes=[f"API index resolution failed: {exc}"]
        ))
    result=AnalysisResult(analysis_id="cpp-dependency-index",analysis_type="CPP_DEPENDENCY_GRAPH",source=str(args.root),status="ANALYZED",source_snapshot_id=sid,notes=["Conservative lexical dependency extraction; semantic graph resolution is not claimed."])
    payload={"schema":1,"analysis":asdict(result),"edges":[asdict(e) for e in edges]}
    if args.json: args.json.parent.mkdir(parents=True,exist_ok=True); args.json.write_text(json.dumps(payload,indent=2)+"\n",encoding="utf-8")
    else: print(json.dumps(payload,indent=2))
if __name__=="__main__": raise SystemExit(main())
