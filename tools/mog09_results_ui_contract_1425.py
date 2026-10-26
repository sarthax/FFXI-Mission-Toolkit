"""Offline, provisional Results DTO. Never authenticates or executes MOG-09."""
from __future__ import annotations
import json
import re
from pathlib import Path

SOURCE_HEADS={"1422":"31bc9a8490199cf257943d4e40fe636325485558",
              "1417":"c64131e49c8835c7281824050b1759332f1e38f1",
              "1418":"d69cfc1c2145fdd32009d3b1c2fc99fdae4d99d7"}
NAMES=("Verify test session identity","Confirm furnishings stored in Mog Safe",
       "Inspect active Moghancement key item","Inspect eight-element aura",
       "Compare persisted bag with client bag","Compare persisted Mog Safe with client Mog Safe")

SAFE_NAME = re.compile(r"synthetic assertion [0-5]\\Z")
SAFE_POINTER = "fixture://mog09/synthetic"

def unknown(reason):
    return {"contract":"mog09-results-offline-presentation/1",
            "status":"BLOCKED_UNTRUSTED_SOURCE","overall_outcome":"UNKNOWN",
            "source_kind":"UNKNOWN","source_integrity":"NOT_ESTABLISHED",
            "redaction_status":"UNVERIFIED","run_id":None,"scenario_revision":None,
            "runner_reported_verdict":None,"task_lifecycle":None,
            "independent_oracle":"NOT_ESTABLISHED","comparison":"NOT_COMPARABLE",
            "steps":[],"reason":reason,"source_contract_heads":SOURCE_HEADS,
            "execution_enabled":False,"publish_enabled":False}

def project(source):
    if not isinstance(source,dict):
        return unknown("MISSING_OR_INVALID_SOURCE")
    # This offline prototype admits only an explicitly declared synthetic fixture.
    # No source/head string can promote runner-origin evidence to trusted UI data.
    if source.get("source_kind") != "SYNTHETIC_FIXTURE":
        return unknown("RUNNER_ORIGIN_REQUIRES_OWNER_ATTESTATION")
    if source.get("redaction_status") != "SYNTHETIC_REDACTED":
        return unknown("REDACTION_NOT_ESTABLISHED")
    if source.get("source_integrity") != "SYNTHETIC_ONLY":
        return unknown("UNVERIFIED_SOURCE_INTEGRITY")
    if source.get("source_head") != SOURCE_HEADS["1422"] or source.get("source_pr") != 1422 or source.get("case_id") != "MOG-09":
        return unknown("CONFLICTING_SOURCE_IDENTITY")
    if source.get("run_id") is not None or source.get("scenario_revision") is not None:
        return unknown("FORGED_AUTHENTIC_RUN_IDENTITY")
    assertions=source.get("assertions")
    if not isinstance(assertions,list) or len(assertions)!=6 or any(not isinstance(x,dict) for x in assertions):
        return unknown("SIX_VALID_ASSERTIONS_REQUIRED")
    path=source.get("source_path")
    if path != SAFE_POINTER:
        return unknown("INVALID_OR_PRIVATE_SOURCE_POINTER")
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
        if type(a.get("runner_ok")) is not bool or not isinstance(a.get("name"),str) or not SAFE_NAME.fullmatch(a["name"]) or a["name"] != "synthetic assertion "+str(n) or "expected" not in a or "observed" not in a:
            return unknown("INVALID_ASSERTION")
        expected=a["expected"];observed=a["observed"]
        # No arbitrary JSON/text/markup reaches a browser DTO, even in collapsed evidence.
        if n < 4 and (expected != "<redacted>" or observed != "<redacted>"):
            return unknown("UNSAFE_NONINVENTORY_DISPLAY_VALUE")
        if n in (4,5):
            if not isinstance(expected,dict) or not isinstance(observed,dict) or expected.get("side")!="persisted char_inventory" or observed.get("side")!="client inventory observation":
                return unknown("INVENTORY_POLARITY_CONFLICT")
            for obj in (expected,observed):
                if set(obj) != {"side", "row_count"} or type(obj.get("row_count")) is not int or not 0 <= obj["row_count"] <= 10000:
                    return unknown("INVALID_INVENTORY_ROWS")
        steps.append({"number":n+1,"title":NAMES[n],"description":a["name"],
            "expected":expected,"observed":observed,
            "runner_reported_check":"PASS" if a["runner_ok"] else "FAIL",
            "independent_step_verdict":"UNKNOWN","evidence_expanded_by_default":False,
            "technical_evidence":{"collector":"runner-supplied sanitized report, not independent",
                "pointer":"fixture://mog09/synthetic/assertions/"+str(n),
                "source_integrity":"NOT_ESTABLISHED"}})
    if raw=="PASS" and any(not x["runner_ok"] for x in assertions):
        return unknown("CONTRADICTORY_RUNNER_SUMMARY")
    if raw=="FAIL" and all(x["runner_ok"] for x in assertions):
        return unknown("CONTRADICTORY_RUNNER_SUMMARY")
    return {"contract":"mog09-results-offline-presentation/1",
      "status":"UNTRUSTED_SYNTHETIC_PREVIEW","overall_outcome":"UNKNOWN",
      "source_kind":"SYNTHETIC_FIXTURE","source_integrity":"SYNTHETIC_ONLY",
      "redaction_status":"SYNTHETIC_REDACTED","run_id":None,
      "runner_reported_verdict":raw,"runner_reported_steps_ok":sum(x["runner_ok"] for x in assertions),
      "task_lifecycle":lifecycle,"independent_oracle":"NOT_ESTABLISHED",
      "comparison":"NOT_COMPARABLE","reason":"REPORT_AUTHENTICITY_AND_ORACLE_UNVERIFIED",
      "steps":steps,"source_contract_heads":SOURCE_HEADS,
      "source_reference":SAFE_POINTER,"scenario_revision":None,
      "execution_enabled":False,"publish_enabled":False}

def project_path(path):
    try:
        raw=json.loads(Path(path).read_text(encoding="utf-8"))
    except (ValueError,OSError,TypeError):
        return unknown("SOURCE_NOT_FOUND")
    return project(raw)

if __name__=="__main__":
    print(json.dumps(unknown("NO_SOURCE_GIVEN"),indent=2))
