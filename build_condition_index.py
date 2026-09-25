#!/usr/bin/env python3
"""Index conditional compilation and generated-source evidence without evaluating the build."""
from __future__ import annotations
import argparse, json, re
from dataclasses import asdict
from pathlib import Path
from workbench_schema import AnalysisResult, Artifact, DependencyEdge, Finding

CPP_EXTENSIONS={".c",".cc",".cpp",".cxx",".h",".hh",".hpp",".hxx"}
BUILD_NAMES={"CMakeLists.txt","Makefile","makefile","GNUmakefile"}
COND_RE=re.compile(r"^\s*#\s*(if|ifdef|ifndef|elif|else|endif)\b(.*)$",re.M)
GEN_RE=re.compile(r"\b(?:add_custom_command|add_custom_target)\s*\((.*?)\)",re.S|re.I)
OUT_RE=re.compile(r"\b(?:OUTPUT|BYPRODUCTS)\s+([^\s)]+)",re.I)
DEP_RE=re.compile(r"\b(?:DEPENDS)\s+([^\s)]+)",re.I)
CM_GEN_RE=re.compile(r"\b(?:configure_file|file)\s*\((.*?)\)",re.S|re.I)

def files(root):
    return [p for p in root.rglob("*") if p.is_file()]

def condition_index(root):
    findings=[]; edges=[]; artifacts=[]
    for p in files(root):
        if p.suffix.lower() not in CPP_EXTENSIONS: continue
        text=p.read_text(encoding="utf-8",errors="replace")
        for m in COND_RE.finditer(text):
            line=text.count("\n",0,m.start())+1
            directive=m.group(1); expr=m.group(2).strip()
            findings.append(asdict(Finding(
                finding_id=f"compile-condition:{p.relative_to(root).as_posix()}:{line}",
                analysis_id="build-condition-index", subject_id=p.relative_to(root).as_posix(),
                field="compile_condition", value={"directive":directive,"expression":expr},
                status="UNKNOWN", confidence="VERIFIED",
                notes=["Condition was parsed from source; the analyzer does not evaluate the build environment."]
            )))
    for p in files(root):
        if p.name not in BUILD_NAMES and p.suffix.lower() not in {".cmake",".mk",".make"}: continue
        text=p.read_text(encoding="utf-8",errors="replace")
        for m in GEN_RE.finditer(text):
            block=m.group(1)
            outputs=OUT_RE.findall(block); deps=DEP_RE.findall(block)
            for out in outputs:
                out_path=Path(out).as_posix()
                aid=f"generated:{out_path}"
                artifacts.append(asdict(Artifact(aid,"GENERATED",out_path,None,None,None,{"build_file":p.relative_to(root).as_posix()})))
                for dep in deps:
                    edges.append(asdict(DependencyEdge(
                        edge_id=f"{aid}:from:{dep}", source_node=aid,
                        target_node=f"artifact:{Path(dep).as_posix()}",
                        relationship="GENERATED_FROM", confidence="INFERRED",
                        status="DISCOVERED", discovered_by="build_condition_index",
                        source_location=f"{p}:{text.count(chr(10),0,m.start())+1}",
                        notes="Generated-source relationship parsed from build command; command execution was not performed."
                    )))
    result=AnalysisResult("build-condition-index","BUILD_CONDITIONS_AND_GENERATION",str(root),status="ANALYZED",
                          findings=[f["finding_id"] for f in findings],
                          notes=["Conditional directives are evidence only; unknown macros are not assumed true or false."])
    return result,findings,artifacts,edges

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("root",type=Path); ap.add_argument("--json",type=Path); a=ap.parse_args()
    result,findings,artifacts,edges=condition_index(a.root)
    payload={"schema":1,"analysis":asdict(result),"findings":findings,"artifacts":artifacts,"edges":edges}
    s=json.dumps(payload,indent=2)+"\n"
    if a.json: a.json.parent.mkdir(parents=True,exist_ok=True); a.json.write_text(s,encoding="utf-8")
    else: print(s)
if __name__=="__main__": raise SystemExit(main())
