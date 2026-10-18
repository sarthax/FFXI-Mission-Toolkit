"""Evidence-based Assault readiness, with unknown distinct from blocked."""
from collections import Counter

def next_action(mission, *, status):
    """Conservative triage step; never infer port or DSP success from Topaz history."""
    if status == "validated":
        return {"key": "validated", "label": "Validated (reviewed)", "detail": "Keep evidence current"}
    reviews = mission.get("reviews") or {}
    def state(stage):
        return (reviews.get(stage) or {}).get("state", "unreviewed")
    if status == "blocked":
        return {"key": "resolve_blocker", "label": "Resolve recorded blocker", "detail": "Inspect blocked mission, issue and shared-dependency reviews"}
    if state("implementation") != "validated":
        return {"key": "implementation_review", "label": "Review DSP implementation", "detail": "Verify source, handlers and prerequisites"}
    if state("port") != "validated":
        return {"key": "port_review", "label": "Verify DSP port", "detail": "Compare Topaz fixes with actual DSP implementation"}
    issue_ports = [
        ((i.get("reviews") or {}).get("dsp_port") or {}).get("state", "unreviewed")
        for i in mission.get("issue_crossrefs", [])
    ]
    dep_ports = [d.get("port", "unreviewed") for d in mission.get("shared_dependencies", [])]
    if any(x not in ("fixed", "not_applicable") for x in issue_ports + dep_ports):
        return {"key": "dependency_review", "label": "Review issue/dependency ports", "detail": "Complete linked DSP port evidence before live testing"}
    if state("validation") != "validated":
        return {"key": "live_test", "label": "Run DSP live validation", "detail": "Record zone, instance, party, steps and server/client evidence"}
    return {"key": "evidence_review", "label": "Review remaining evidence", "detail": "Resolve incomplete issue/dependency validation reviews"}


def assess(mission):
    reasons=[]
    issues=mission.get("issue_crossrefs",[])
    deps=mission.get("shared_dependencies",[])
    blockers=[]
    unknown=[]
    reviews=mission.get("reviews",{})
    for stage in ("implementation","port","validation"):
        state=(reviews.get(stage) or {}).get("state","unreviewed")
        if state=="blocked":
            blockers.append("Mission "+stage+" blocked")
        elif state not in ("validated","not_applicable"):
            unknown.append("Mission "+stage+": "+state)
    for issue in issues:
        states={stage:(issue.get("reviews",{}).get(stage) or {}).get("state","unreviewed")
                for stage in ("topaz","dsp_port","dsp_validation")}
        if "blocked" in states.values() or "open" in states.values():
            blockers.append("Issue "+str(issue["id"])+" has an open/blocked review")
        elif any(v not in ("fixed","not_applicable") for v in states.values()):
            unknown.append("Issue "+str(issue["id"])+" needs review")
    for dep in deps:
        states=(dep.get("topaz"),dep.get("port"),dep.get("validation"))
        if "blocked" in states or "open" in states:
            blockers.append("Shared dependency: "+dep["title"])
        elif any(v not in ("fixed","not_applicable") for v in states):
            unknown.append("Shared dependency not verified: "+dep["title"])
    status="blocked" if blockers else ("needs_evidence" if unknown else "validated")
    return {"status":status,"next_action":next_action(mission, status=status),"blockers":blockers,"unknown":unknown,
            "issue_count":len(issues),"dependency_count":len(deps)}


def assess_all(missions):
    counts=Counter()
    for mission in missions:
        mission["readiness"]=assess(mission)
        counts[mission["readiness"]["status"]]+=1
    return dict(counts)
