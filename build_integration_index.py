#!/usr/bin/env python3
"""Index C++ build integration evidence from an external server source tree.

The analyzer does not attempt to execute a build. It records source inclusion evidence from common
CMake/Make/source-manifest conventions and marks files with no discovered build reference UNKNOWN.
"""
from __future__ import annotations
import argparse, json, re
from dataclasses import asdict
from pathlib import Path
from workbench_schema import AnalysisResult, Finding

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
    return builders,findings

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("root",type=Path)
    ap.add_argument("--json",type=Path)
    args=ap.parse_args()
    builders,findings=index(args.root)
    result=AnalysisResult(
        analysis_id="build-integration-index",
        analysis_type="BUILD_INTEGRATION",
        source=str(args.root),
        status="ANALYZED",
        findings=[f.finding_id for f in findings],
        notes=[f"Scanned {len(builders)} recognized build files.","No build was executed."],
    )
    payload={"schema":1,"analysis":asdict(result),"build_files":[p.relative_to(args.root).as_posix() for p in builders],"findings":[asdict(f) for f in findings]}
    if args.json:
        args.json.parent.mkdir(parents=True,exist_ok=True); args.json.write_text(json.dumps(payload,indent=2)+"\n",encoding="utf-8")
    else: print(json.dumps(payload,indent=2))
if __name__=="__main__": raise SystemExit(main())
