"""Offline, provisional Results DTO. Never authenticates or executes MOG-09."""
from __future__ import annotations
import json
from pathlib import Path

SOURCE_HEADS={"1422":"31bc9a8490199cf257943d4e40fe636325485558",
              "1417":"c64131e49c8835c7281824050b1759332f1e38f1",
              "1418":"d69cfc1c2145fdd32009d3b1c2fc99fdae4d99d7"}
NAMES=("Verify test session identity","Confirm furnishings stored in Mog Safe",
       "Inspect active Moghancement key item","Inspect eight-element aura",
       "Compare persisted bag with client bag","Compare persisted Mog Safe with client Mog Safe")

def unknown(reason):
    return {"contract":"mog09-results-offline-presentation/1",
            "status":"UNTRUSTED_PROTOTYPE","overall_outcome":"UNKNOWN",
            "runner_reported_verdict":None,"task_lifecycle":None,
            "independent_oracle":"NOT_ESTABLISHED","comparison":"NOT_COMPARABLE",
            "steps":[],"reason":reason,"source_contract_heads":SOURCE_HEADS,
            "execution_enabled":False,"publish_enabled":False}

def project(source):
    if not isinstance(source,dict):
        return unknown("MISSING_OR_INVALID_SOURCE")
    if source.get("source_head")!=SOURCE_HEADS["1422"] and source.get("source_head")!="a2a21a706d09e2eea0bb660f991db9d43d4266a1":
        return unknown("UNREVIEWED_OR_CONFLICTING_SOURCE")
    if source.get("source_pr")!=1420 or source.get("case_id")!="MOG-09":
        return unknown("CONFLICTING_CASE_IDENTITY")
    assertions=source.get("assertions")
    if not isinstance(assertions,list) or len(assertions)!=6 or any(not isinstance(x,dict) for x in assertions):
        return unknown("SIX_VALID_ASSERTIONS_REQUIRED")
    path=source.get("source_path")
    if not isinstance(path,str) or not path.startswith("docs/workbench/results_evidence_handoff/samples/") or not path.endswith("/report.json") or ".." in path or "\\" in path:
        return unknown("INVALID_SOURCE_POINTER")
    lifecycle=source.get("task_lifecycle")
    if lifecycle not in (None,"COMPLETED","CANCEL_REQUEST_ACCEPTED"):
        return unknown("INVALID_TASK_STATE")
    if lifecycle=="CANCEL_REQUEST_ACCEPTED":
        return unknown("CANCEL_NOT_TERMINAL")
    raw=source.get("runner_verdict")
    if raw not in ("PASS","FAIL"):
        return unknown("UNKNOWN_RUNNER_VERDICT")
    steps=[]
    for n,a in enumerate(assertions):
        if type(a.get("runner_ok")) is not bool or not isinstance(a.get("name"),str) or not a["name"].strip() or "expected" not in a or "observed" not in a:
            return unknown("INVALID_ASSERTION")
        expected=a["expected"];observed=a["observed"]
        if n in (4,5):
            if not isinstance(expected,dict) or not isinstance(observed,dict) or expected.get("side")!="persisted char_inventory" or observed.get("side")!="client inventory observation":
                return unknown("INVENTORY_POLARITY_CONFLICT")
            for obj in (expected,observed):
                if type(obj.get("row_count")) is not int or obj["row_count"]<0:
                    return unknown("INVALID_INVENTORY_ROWS")
        steps.append({"number":n+1,"title":NAMES[n],"description":a["name"],
            "expected":expected,"observed":observed,
            "runner_reported_check":"PASS" if a["runner_ok"] else "FAIL",
            "independent_step_verdict":"UNKNOWN","evidence_expanded_by_default":False,
            "technical_evidence":{"collector":"runner-supplied sanitized report, not independent",
                "pointer":path+"#/results/0/evidence/assertions/"+str(n),
                "source_integrity":"NOT_ESTABLISHED"}})
    if raw=="PASS" and any(not x["runner_ok"] for x in assertions):
        return unknown("CONTRADICTORY_RUNNER_SUMMARY")
    if raw=="FAIL" and all(x["runner_ok"] for x in assertions):
        return unknown("CONTRADICTORY_RUNNER_SUMMARY")
    return {"contract":"mog09-results-offline-presentation/1",
      "status":"UNTRUSTED_PROTOTYPE","overall_outcome":"UNKNOWN",
      "runner_reported_verdict":raw,"runner_reported_steps_ok":sum(x["runner_ok"] for x in assertions),
      "task_lifecycle":lifecycle,"independent_oracle":"NOT_ESTABLISHED",
      "comparison":"NOT_COMPARABLE","reason":"REPORT_AUTHENTICITY_AND_ORACLE_UNVERIFIED",
      "steps":steps,"source_contract_heads":SOURCE_HEADS,
      "source_reference":path,"scenario_revision":None,
      "execution_enabled":False,"publish_enabled":False}

def project_path(path):
    try:
        raw=json.loads(Path(path).read_text(encoding="utf-8"))
    except (ValueError,OSError,TypeError):
        return unknown("SOURCE_NOT_FOUND")
    return project(raw)

if __name__=="__main__":
    print(json.dumps(unknown("NO_SOURCE_GIVEN"),indent=2))
