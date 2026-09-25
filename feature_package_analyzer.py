#!/usr/bin/env python3
"""Analyze an assembled migration package into generic Feature/Artifact/Dependency records.

This complements backport_package.py rather than replacing it. It consumes a package directory and
its existing BACKPORT_REPORT.md, while optionally reading a feature manifest. It does not invent
dependencies from require() chains; explicit manifest edges and deterministic artifact relationships
are preferred.
"""
from __future__ import annotations
import argparse, json, re, tempfile
from pathlib import Path
from workbench.core import graph as workbench_graph

STATES={"DISCOVERED","ANALYZED","COMPATIBLE","AUTO_MIGRATABLE","MANUAL_REQUIRED","MIGRATED","IMPLEMENTED","VALIDATING","VERIFIED","FAILED","UNKNOWN","CONTRADICTED","BLOCKED"}

def files(root):
    return [p for p in root.rglob("*") if p.is_file()]

def artifact_type(p):
    s=p.suffix.lower()
    return {".lua":"LUA",".sql":"SQL",".cpp":"CPP",".cc":"CPP",".cxx":"CPP",".h":"HEADER",".hpp":"HEADER",".json":"MANIFEST",".md":"REPORT"}.get(s,"FILE")

def parse_report(path):
    if not path.exists(): return {"status":"UNKNOWN","issues":[]}
    text=path.read_text(encoding="utf-8",errors="replace")
    issues=[]
    if "Needs review" in text: issues.append("BACKPORT_REPORT_NEEDS_REVIEW")
    if "Clean" in text and "Needs review" not in text: status="VERIFIED"
    else: status="MANUAL_REQUIRED" if issues else "UNKNOWN"
    for line in text.splitlines():
        if re.search(r"\bMISSING\b|\bcollision\b|\bduplication\b|syntax error|undeclared",line,re.I):
            issues.append(line.strip())
    return {"status":status,"issues":issues}

def load_manifest(path):
    if not path.exists(): return {}
    try:
        import yaml
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        # JSON is accepted as a safe manifest fallback when YAML support is unavailable.
        try: return json.loads(path.read_text(encoding="utf-8"))
        except Exception: return {}

def analyze(package: Path):
    manifest=load_manifest(package/"FEATURE_MANIFEST.yaml")
    feature=manifest.get("feature",{}) if isinstance(manifest,dict) else {}
    feature_id=feature.get("id") or f"package:{package.name}"
    name=feature.get("name") or package.name
    report=parse_report(package/"BACKPORT_REPORT.md")
    arts=[]
    for p in files(package):
        if p.name=="BACKPORT_REPORT.md": continue
        rel=p.relative_to(package).as_posix()
        arts.append({"artifact_id":f"artifact:{feature_id}:{rel}","artifact_type":artifact_type(p),"path":rel,"feature_id":feature_id})
    deps=[]
    for i,d in enumerate(manifest.get("dependencies",[]) if isinstance(manifest,dict) else []):
        if isinstance(d,str): target=d; relationship="REQUIRES"; evidence="MANIFEST"
        else:
            target=d.get("target"); relationship=d.get("relationship","REQUIRES"); evidence=d.get("evidence","MANIFEST")
        if target:
            deps.append({"edge_id":f"manifest:{feature_id}:{i}","source_node":feature_id,"target_node":target,"relationship":relationship,"confidence":"VERIFIED","status":"DISCOVERED","discovered_by":"feature_package_analyzer","source_location":"FEATURE_MANIFEST.yaml","notes":evidence})
    actions=[]
    mig_state=report["status"]
    if arts and mig_state=="VERIFIED":
        action_state="AUTO_MIGRATABLE"
    elif arts:
        action_state="MANUAL_REQUIRED"
    else:
        action_state="UNKNOWN"
    for i,a in enumerate(arts):
        actions.append({"action_id":f"action:{feature_id}:{i}","migration_id":f"migration:{feature_id}","action":"CONVERT" if a["artifact_type"] in {"LUA","SQL"} else "MANUAL_REVIEW","artifact_id":a["artifact_id"],"status":action_state,"reason":"TARGET_ALREADY_HAS" if mig_state=="VERIFIED" else "UNRESOLVED"})
    return {
        "schema":2,
        "feature":{"feature_id":feature_id,"name":name,"feature_type":feature.get("type"),"domain_id":feature.get("domain"),"status":mig_state},
        "artifacts":arts,
        "dependencies":deps,
        "edges":deps,
        "migration":{"migration_id":f"migration:{feature_id}","feature_id":feature_id,"status":mig_state},
        "actions":actions,
        "migration_actions":actions,
        "report":report,
    }

def import_to_graph(payload, db: Path):
    """Import analyzer output through the canonical graph importer."""
    with tempfile.NamedTemporaryFile("w",suffix=".json",encoding="utf-8",delete=False) as tmp:
        json.dump(payload,tmp)
        tmp_path=Path(tmp.name)
    try:
        workbench_graph.import_json(tmp_path,db)
    finally:
        tmp_path.unlink(missing_ok=True)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("package",type=Path)
    ap.add_argument("--json",type=Path)
    ap.add_argument("--graph-db",type=Path,help="Optionally import canonical feature/artifact/edge/migration/action records into the Workbench graph.")
    args=ap.parse_args()
    out=analyze(args.package)
    if args.graph_db:
        import_to_graph(out,args.graph_db)
    if args.json:
        args.json.parent.mkdir(parents=True,exist_ok=True); args.json.write_text(json.dumps(out,indent=2)+"\n",encoding="utf-8")
    else: print(json.dumps(out,indent=2))
if __name__=="__main__": raise SystemExit(main())
