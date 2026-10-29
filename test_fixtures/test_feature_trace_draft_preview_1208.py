import importlib.util
import json
from pathlib import Path
S=importlib.util.spec_from_file_location("ft_preview",Path(__file__).resolve().parents[1]/"tools/feature_trace_draft_preview_1208.py")
m=importlib.util.module_from_spec(S);S.loader.exec_module(m)
C={"contract":"coverage_behavior_reference_v1","feature_id":"gardening","behavior_ref":"GARD-SYNTH-01",
   "label":"Inspect declared garden test intent","category":"positive","source":"data/testing/feature_test_readiness.json",
   "source_pointer":"features[id=gardening].cases[id=GARD-SYNTH-01]","source_revision":"UNPINNED",
   "reference_kind":"declared_test_case_intent_not_behavior_trace_identity","proposed_case_id":None,
   "expected_oracle":"UNKNOWN","assertions":[],"observations":[],"capability_bindings":[],
   "context_only":True,"design_only":True,"review_required":True,"auto_populate_allowed":False,
   "auto_save_allowed":False,"execution_enabled":False}
def bad(**changes):
    x=dict(C,**changes)
    try: m.preview(x)
    except ValueError: return
    raise AssertionError(f"unsafe context accepted: {changes}")
def main():
    p=m.preview(C)
    assert p["scenario_id"] is None and p["verdict"]=="NOT_RUN" and p["oracle"]=="UNKNOWN"
    assert p["state"]=="REVIEW_REQUIRED" and not any(p[k] for k in ("executable","save_allowed","publish_allowed","canonical"))
    assert p["source"]["revision"]=="UNPINNED" and p["source"]["pointer"]==C["source_pointer"]
    assert "UNKNOWN" in p["then"] and "BLOCKED" in p["action_capability"]
    assert m.preview(dict(C,source_revision="a"*40))["source"]["revision"]=="a"*40
    for k,v in [("execution_enabled",True),("review_required",False),("context_only",False),
                ("auto_populate_allowed",True),("auto_save_allowed",True),("expected_oracle","PASS"),
                ("proposed_case_id","FORGED"),("assertions",[{"ok":True}]),("observations",["zone"]),
                ("capability_bindings",["talk_npc"]),("source_revision","a"*39),
                ("source_revision",""),("source_revision","f"*40+"-conflict"),
                ("source_pointer","features[id=other].cases[id=GARD-SYNTH-01]"),
                ("source_pointer","https://host/evil"),("source","../../passwd"),
                ("behavior_ref","gardening"),("behavior_ref","GARD/01"),("category","unknown"),
                ("label",42)]:
        bad(**{k:v})
    for obj in [None,[],{"contract":"coverage_behavior_reference_v1"}]:
        try:m.preview(obj)
        except ValueError:pass
        else:raise AssertionError("malformed input accepted")
    print("offline feature trace preview #1208: positive + negative gates PASS")
if __name__=="__main__":main()
