"""Standalone regression for evidence-conscious per-mission Assault next steps."""
from workbench.domains.assault_readiness import assess

def mission(implementation="unreviewed", port="unreviewed", validation="unreviewed", issue_port=None, dep_port=None):
    value={"reviews":{"implementation":{"state":implementation},
                      "port":{"state":port},"validation":{"state":validation}},
           "issue_crossrefs":[],"shared_dependencies":[]}
    if issue_port is not None:
        value["issue_crossrefs"].append({"id":1,"reviews":{"dsp_port":{"state":issue_port},
                                      "topaz":{"state":"fixed"},"dsp_validation":{"state":"unreviewed"}}})
    if dep_port is not None:
        value["shared_dependencies"].append({"title":"Appraisals","topaz":"fixed",
                                            "port":dep_port,"validation":"unreviewed"})
    return value

def run():
    assert assess(mission())["next_action"]["key"]=="implementation_review"
    assert assess(mission(implementation="validated"))["next_action"]["key"]=="port_review"
    assert assess(mission("validated","validated",issue_port="unreviewed"))["next_action"]["key"]=="dependency_review"
    assert assess(mission("validated","validated",dep_port="unreviewed"))["next_action"]["key"]=="dependency_review"
    assert assess(mission("validated","validated",issue_port="fixed",dep_port="fixed"))["next_action"]["key"]=="live_test"
    blocked=mission("validated","validated",issue_port="blocked")
    assert assess(blocked)["next_action"]["key"]=="resolve_blocker"
    # A historic Topaz fix never itself establishes DSP implementation.
    assert assess(mission(issue_port="unreviewed"))["next_action"]["key"]=="implementation_review"
    from pathlib import Path
    page=(Path(__file__).resolve().parents[1]/"gui/templates/domain_assault.html").read_text(encoding="utf-8")
    assert "mission.readiness.next_action.label" in page
    print("Assault next-action triage: PASS")

if __name__=="__main__":
    run()
