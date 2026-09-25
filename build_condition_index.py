#!/usr/bin/env python3
"""Conservative build-condition and generated-source evidence indexer."""
from __future__ import annotations
import argparse,json,re
from dataclasses import asdict
from pathlib import Path
from workbench_schema import AnalysisResult, Finding

CPP_EXTENSIONS={".cpp",".cc",".cxx",".c",".h",".hpp",".hh",".hxx"}
BUILD_NAMES={"CMakeLists.txt","Makefile","makefile","GNUmakefile"}
GEN_WORDS=re.compile(r"\b(?:generate|generated|codegen|autogen|configure_file)\b",re.I)

def candidate_files(root):
    for p in root.rglob("*"):
        if p.is_file() and (p.name in BUILD_NAMES or p.name.endswith(".cmake") or p.suffix in {".mk",".make"} or p.suffix.lower() in CPP_EXTENSIONS):
            yield p

def index(root):
    findings=[]
    for p in candidate_files(root):
        rel=p.relative_to(root).as_posix()
        lines=p.read_text(encoding="utf-8",errors="replace").splitlines()
        for n,line in enumerate(lines,1):
            m=re.match(r"^\s*#\s*(if|ifdef|ifndef|elif|else|endif)\b(.*)$",line)
            if m:
                findings.append(Finding(
                    finding_id=f"compile-condition:{rel}:{n}",analysis_id="build-condition-index",
                    subject_id=rel,field="compile_condition",
                    value={"directive":m.group(1),"expression":m.group(2).strip()},
                    status="DISCOVERED",confidence="VERIFIED",
                    notes=["Preprocessor condition recorded syntactically; environment evaluation was not performed."]
                ))
            if (p.name in BUILD_NAMES or p.name.endswith(".cmake") or p.suffix in {".mk",".make"}) and GEN_WORDS.search(line):
                findings.append(Finding(
                    finding_id=f"generation-marker:{rel}:{n}",analysis_id="build-condition-index",
                    subject_id=rel,field="generation_marker",value=line.strip(),
                    status="DISCOVERED",confidence="INFERRED",
                    notes=["Generation keyword detected; exact generated artifact mapping requires build-command evaluation."]
                ))
    return findings

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("root",type=Path); ap.add_argument("--json",type=Path); a=ap.parse_args()
    fs=index(a.root)
    r=AnalysisResult(analysis_id="build-condition-index",analysis_type="BUILD_CONDITIONS_AND_GENERATION",
                     source=str(a.root),status="ANALYZED",findings=[x.finding_id for x in fs],
                     notes=["Conservative syntax scan; compiler/build environment was not evaluated."])
    out={"schema":1,"analysis":asdict(r),"findings":[asdict(x) for x in fs]}
    if a.json: a.json.parent.mkdir(parents=True,exist_ok=True); a.json.write_text(json.dumps(out,indent=2)+"\n",encoding="utf-8")
    else: print(json.dumps(out,indent=2))
if __name__=="__main__": raise SystemExit(main())
