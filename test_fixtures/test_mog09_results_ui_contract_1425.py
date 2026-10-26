import importlib.util
from pathlib import Path
M=Path(__file__).resolve().parents[1]/"tools/mog09_results_ui_contract_1425.py"
s=importlib.util.spec_from_file_location("dto",M);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
def sample(raw="FAIL"):
    a=[]
    for i in range(6):
        expected={"side":"persisted char_inventory","row_count":0} if i>=4 else "<redacted>"
        observed={"side":"client inventory observation","row_count":8 if i==4 else 1} if i>=4 else "<redacted>"
        a.append({"name":"synthetic assertion "+str(i),"runner_ok":i<4 if raw=="FAIL" else True,
                  "expected":expected,"observed":observed})
    return {"source_head":"a2a21a706d09e2eea0bb660f991db9d43d4266a1",
            "source_pr":1420,"case_id":"MOG-09","runner_verdict":raw,
            "task_lifecycle":"COMPLETED" if raw=="FAIL" else None,
            "source_path":"docs/workbench/results_evidence_handoff/samples/redacted/report.json","assertions":a}
def main():
    for label,count in (("FAIL",4),("PASS",6)):
        d=m.project(sample(label))
        assert d["overall_outcome"]=="UNKNOWN" and d["independent_oracle"]=="NOT_ESTABLISHED"
        assert d["runner_reported_verdict"]==label and d["runner_reported_steps_ok"]==count
        assert len(d["steps"])==6 and [x["number"] for x in d["steps"]]==list(range(1,7))
        assert d["comparison"]=="NOT_COMPARABLE"
        assert not d["execution_enabled"] and not d["publish_enabled"]
        assert all(x["independent_step_verdict"]=="UNKNOWN" for x in d["steps"])
        assert all(not x["evidence_expanded_by_default"] for x in d["steps"])
    d=m.project(sample("FAIL"))
    assert [(x["expected"]["row_count"],x["observed"]["row_count"]) for x in d["steps"][4:]]==[(0,8),(0,1)]
    bad=sample();bad["assertions"][4]["expected"]["side"]="client inventory observation"
    assert m.project(bad)["overall_outcome"]=="UNKNOWN" and not m.project(bad)["steps"]
    for edit in ({"assertions":[None]*6},{"source_path":None},
                 {"task_lifecycle":"CANCEL_REQUEST_ACCEPTED"},{"runner_verdict":"PASS"},
                 {"source_head":"forged"},{"case_id":"OTHER"}):
        q=sample();q.update(edit)
        assert m.project(q)["overall_outcome"]=="UNKNOWN" and not m.project(q)["steps"]
    for x in (None,[],{},{"assertions":[1]*6}):
        assert m.project(x)["overall_outcome"]=="UNKNOWN"
    assert m.project_path("/nonexistent/1425.json")["overall_outcome"]=="UNKNOWN"
    print("1425 offline Results DTO: six steps, privacy-neutral, negative cases PASS")
if __name__=="__main__":main()
