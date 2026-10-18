"""Filter readiness without equating test readiness to completed validation."""
FILTERS=("all","blocked","needs_evidence","validated","ready_for_live_test","port_pending")

def filter_missions(missions, *, zone="", status="all"):
    if status not in FILTERS: raise ValueError("Unsupported readiness filter")
    result=[]
    for mission in missions:
        if zone and mission["zone"]!=zone: continue
        readiness=mission["readiness"]["status"]
        reviews=mission.get("reviews",{})
        def stage(name):return (reviews.get(name) or {}).get("state","unreviewed")
        # Ready to live test is deliberately narrower than needs-evidence:
        # implementation and port must have explicit validated reviews;
        # validation not complete and no confirmed blocker anywhere.
        ready=(readiness!="blocked" and stage("implementation")=="validated"
               and stage("port")=="validated" and stage("validation") in
               ("unreviewed","pending","in_progress","ready_for_test"))
        # A mission-level port approval does not override unresolved or unreviewed
        # issue/dependency DSP port states. Require explicit port evidence for
        # every linked item before offering the live-test queue.
        issue_ports = [
            ((issue.get("reviews") or {}).get("dsp_port") or {}).get("state", "unreviewed")
            for issue in mission.get("issue_crossrefs", [])
        ]
        dependency_ports = [
            dep.get("port", "unreviewed")
            for dep in mission.get("shared_dependencies", [])
        ]
        ready = ready and all(x in ("fixed", "not_applicable") for x in issue_ports + dependency_ports)
        pending=stage("port") not in ("validated","not_applicable")
        if status=="all" or status==readiness or (status=="ready_for_live_test" and ready) or (status=="port_pending" and pending):
            result.append(mission)
    return result
