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
    funcs, enum_defs, _bindings = index_api(root)
    enum_symbols={e.symbol for e in enum_defs}
    functions_by_path={}
    for fn in funcs:
        if fn.definition:
            functions_by_path.setdefault(fn.path,[]).append(fn)
    for rows in functions_by_path.values():
        rows.sort(key=lambda fn: fn.line or 0)

    for p in source_files(root):
        text=p.read_text(encoding="utf-8",errors="replace")
        src=p.relative_to(root).as_posix()
        lines=text.splitlines()
        spans=[]
        defs=functions_by_path.get(src,[])
        for i,fn in enumerate(defs):
            start_line=fn.line or 1
            end_line=(defs[i+1].line-1) if i+1<len(defs) and defs[i+1].line else len(lines)
            spans.append((start_line,end_line,fn.function_id))
        def owner(line_no):
            hits=[fid for lo,hi,fid in spans if lo <= line_no <= hi]
            return hits[-1] if hits else src

        for m in INCLUDE_RE.finditer(text):
            inc=m.group(1); line=text.count("\n",0,m.start())+1
            edges.append(DependencyEdge(
                edge_id=f"include:{src}:{line}:{inc}",source_node=src,target_node=inc,relationship="IMPORTS",
                confidence="VERIFIED",status="DISCOVERED",discovered_by="cpp_dependency_index",
                source_location=f"{src}:{line}",notes=["Direct #include directive."]
            ))
        for m in ENUM_USE_RE.finditer(text):
            ns,sym=m.groups()
            if ns.lower() in {"std","boost","fmt","sol","lua"}: continue
            line=text.count("\n",0,m.start())+1
            target=f"{ns}::{sym}"
            confidence="INFERRED"
            notes=["Namespace-qualified symbol use; function ownership and semantic type are inferred from lexical position."]
            if target in enum_symbols:
                notes.append("Exact symbol identity exists in the extracted enum/constant index; this does not verify function ownership.")
            edges.append(DependencyEdge(
                edge_id=f"symbol-use:{src}:{line}:{target}",source_node=owner(line),target_node=target,
                relationship="USES_ENUM",confidence=confidence,status="DISCOVERED",
                discovered_by="cpp_dependency_index",source_location=f"{src}:{line}",notes=notes
            ))
        for n,line_text in enumerate(lines,1):
            if PACKET_RE.search(line_text):
                edges.append(DependencyEdge(
                    edge_id=f"packet-ref:{src}:{n}",source_node=owner(n),target_node="PACKET_REFERENCE",
                    relationship="USES_PACKET",confidence="INFERRED",status="DISCOVERED",
                    discovered_by="cpp_dependency_index",source_location=f"{src}:{n}",
                    notes=["Packet-related token detected; exact opcode/handler mapping requires packet index evidence."]
                ))
    return edges

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("root",type=Path); ap.add_argument("--json",type=Path); args=ap.parse_args()
    sid=snapshot_id(args.root)
    edges=index(args.root)
    for edge in edges:
        edge.source_snapshot_id=sid
    result=AnalysisResult(analysis_id="cpp-dependency-index",analysis_type="CPP_DEPENDENCY_GRAPH",source=str(args.root),status="ANALYZED",source_snapshot_id=sid,notes=["Conservative lexical dependency extraction; semantic graph resolution is not claimed."])
    payload={"schema":1,"analysis":asdict(result),"edges":[asdict(e) for e in edges]}
    if args.json: args.json.parent.mkdir(parents=True,exist_ok=True); args.json.write_text(json.dumps(payload,indent=2)+"\n",encoding="utf-8")
    else: print(json.dumps(payload,indent=2))
if __name__=="__main__": raise SystemExit(main())
