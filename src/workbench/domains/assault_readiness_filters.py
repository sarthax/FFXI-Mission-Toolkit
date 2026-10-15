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
        pending=stage("port") not in ("validated","not_applicable")
        if status=="all" or status==readiness or (status=="ready_for_live_test" and ready) or (status=="port_pending" and pending):
            result.append(mission)
    return result
