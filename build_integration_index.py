#!/usr/bin/env python3
"""Index C++ build integration evidence from an external server source tree.

The analyzer does not attempt to execute a build. It records source inclusion evidence from common
CMake/Make/source-manifest conventions and marks files with no discovered build reference UNKNOWN.
"""
from __future__ import annotations
import argparse, json, re
from dataclasses import asdict
from pathlib import Path
from source_snapshot import snapshot_id
from workbench_schema import AnalysisResult, Finding, BuildTarget, DependencyEdge
from cpp_api_index import index as index_api

CPP_EXTENSIONS={".cpp",".cc",".cxx",".c",".h",".hpp",".hh",".hxx"}
BUILD_FILES={"CMakeLists.txt","Makefile","makefile","GNUmakefile"}
CMAKE_ADD_RE=re.compile(r'\b(?:add_library|add_executable)\s*\(([^)]*)\)',re.S)
CMAKE_SOURCE_RE=re.compile(r'\btarget_sources\s*\(([^)]*)\)',re.S)
MAKE_VAR_RE=re.compile(r'^\s*([A-Za-z_][A-Za-z0-9_]*)\s*\+?=\s*(.*)$',re.M)

def source_files(root):
    return [p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in CPP_EXTENSIONS]

def build_files(root):
    return [p for p in root.rglob("*") if p.is_file() and (p.name in BUILD_FILES or p.name.endswith(".cmake") or p.suffix in {".mk",".make"})]

def tokens(text):
    return [x for x in re.split(r'\s+', re.sub(r'[\\"(),]', ' ', text)) if x]

def extract_targets(root, build_text):
    targets=[]
    edges=[]
    target_sources={}

    for p,text in build_text:
        for block in CMAKE_ADD_RE.findall(text):
            toks=tokens(block)
            if toks:
                name=toks[0]
                target_id=f"build-target:{p.relative_to(root).as_posix()}:{name}"
                targets.append(BuildTarget(
                    target_id=target_id, name=name, build_system="CMAKE", path=p.relative_to(root).as_posix(),
                    notes=["Target discovered from add_library/add_executable; configuration/generator evaluation not performed."]
                ))
                target_sources[target_id]=set(toks[1:])
    return targets, target_sources

def index(root):
    builders=build_files(root)
    build_text=[(p,p.read_text(encoding="utf-8",errors="replace")) for p in builders]
    included={}
    for p,text in build_text:
        for block_re in (CMAKE_ADD_RE,CMAKE_SOURCE_RE):
            for block in block_re.findall(text):
                for token in tokens(block):
                    if Path(token).suffix.lower() in CPP_EXTENSIONS:
                        included.setdefault(Path(token).as_posix(),[]).append(p.relative_to(root).as_posix())
        for m in MAKE_VAR_RE.finditer(text):
            for token in tokens(m.group(2)):
                if Path(token).suffix.lower() in CPP_EXTENSIONS:
                    included.setdefault(Path(token).as_posix(),[]).append(p.relative_to(root).as_posix())
    findings=[]
    targets,target_sources=extract_targets(root, build_text)
    all_paths={p.relative_to(root).as_posix():p for p in source_files(root)}
    for rel in sorted(all_paths):
        refs=included.get(rel,[])
        if refs:
            status="VERIFIED"
            conf="INFERRED"
            notes=["Referenced by a recognized build-file source list; execution/conditional evaluation not performed."]
        else:
            # Also allow basename matching because build systems frequently use relative paths from a
            # subdirectory rather than the repository root.
            base_refs=[b for k,v in included.items() if Path(k).name==Path(rel).name for b in v]
            if base_refs:
                status="DERIVED"; conf="INFERRED"
                notes=["Matched build source by basename; path-specific inclusion remains unverified."]
                refs=sorted(set(base_refs))
            else:
                status="UNKNOWN"; conf="UNKNOWN"
                notes=["No recognized source-list reference found; may be generated, globbed, conditional, or uncompiled."]
        findings.append(Finding(
            finding_id=f"build-source:{rel}",
            analysis_id="build-integration-index",
            subject_id=rel,
            field="build_inclusion",
            value={"references":sorted(set(refs))},
            status=status,
            confidence=conf,
            notes=notes,
        ))
    edges=[]
    try:
        api_funcs, _api_enums, _api_bindings = index_api(root)
    except Exception:
        api_funcs=[]
    for target_id, paths in target_sources.items():
        for rel in paths:
            edges.append(DependencyEdge(
                edge_id=f"builds-into:{rel}:{target_id}", source_node=rel, target_node=target_id,
                relationship="BUILDS_INTO", confidence="VERIFIED", status="DISCOVERED",
                discovered_by="build_integration_index", source_location=target_id,
                notes=["Source token occurs in an explicit CMake target source list; target configuration/generator evaluation was not performed."]
            ))
            # Function-level build edges let packet/Lua traces continue from a resolved C++ symbol
            # to its build target. The target association is verified lexically; build conditions
            # are still not evaluated.
            candidates=[rel]
            candidates.extend(path for path in all_paths if Path(path).name==Path(rel).name)
            for path in sorted(set(candidates)):
                if path not in all_paths: continue
                for fn in api_funcs:
                    if fn.path==path and fn.definition:
                        edges.append(DependencyEdge(
                            edge_id=f"function-builds-into:{fn.function_id}:{target_id}",
                            source_node=fn.function_id,target_node=target_id,relationship="BUILDS_INTO",
                            confidence="VERIFIED",status="DISCOVERED",discovered_by="build_integration_index",
                            source_location=target_id,
                            notes=["Function definition is in a source file explicitly associated with this CMake target; conditional build evaluation not performed."]
                        ))
    return builders,findings,targets,edges

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("root",type=Path)
    ap.add_argument("--json",type=Path)
    args=ap.parse_args()
    sid=snapshot_id(args.root)
    builders,findings,targets,edges=index(args.root)
    for target in targets:
        target.source_snapshot_id=sid
    for finding in findings:
        finding.source_snapshot_id=sid
    for edge in edges:
        edge.evidence_id=f"snapshot:{sid}"
        edge.source_snapshot_id=sid
    result=AnalysisResult(
        analysis_id="build-integration-index",
        analysis_type="BUILD_INTEGRATION",
        source=str(args.root),
        status="ANALYZED",
        notes=[f"Source snapshot: {sid}.", f"Scanned {len(builders)} recognized build files.", "No build was executed."],
        findings=[f.finding_id for f in findings],
        
    )
    payload={"schema":2,"analysis":asdict(result),"build_files":[p.relative_to(args.root).as_posix() for p in builders],"build_targets":[asdict(t) for t in targets],"edges":[asdict(e) for e in edges],"findings":[asdict(f) for f in findings]}
    if args.json:
        args.json.parent.mkdir(parents=True,exist_ok=True); args.json.write_text(json.dumps(payload,indent=2)+"\n",encoding="utf-8")
    else: print(json.dumps(payload,indent=2))
if __name__=="__main__": raise SystemExit(main())
