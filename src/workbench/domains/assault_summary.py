"""Evidence-conscious summary of Assault reviews, by zone and global totals."""
from collections import Counter

def summarize(missions):
    totals = Counter()
    zones = {}
    for mission in missions:
        zone = mission["zone"]
        c = zones.setdefault(zone, Counter())
        action = (mission.get("readiness") or {}).get("next_action") or {}
        key = action.get("key", "implementation_review")
        for bucket in (totals, c):
            bucket["next_" + key] += 1
        for bucket in (totals, c):
            bucket["missions"] += 1
            for stage in ("implementation", "port", "validation"):
                row = mission.get("reviews", {}).get(stage)
                state = row["state"] if row else "unreviewed"
                bucket[f"mission_{stage}_{state}"] += 1
        for issue in mission.get("issue_crossrefs", []):
            for bucket in (totals, c):
                bucket["issues"] += 1
                for stage in ("topaz", "dsp_port", "dsp_validation"):
                    review = issue.get("reviews", {}).get(stage)
                    state = review["state"] if review else "unreviewed"
                    bucket[f"issue_{stage}_{state}"] += 1
                if any(r and r["state"] == "blocked" for r in issue.get("reviews", {}).values()):
                    bucket["blocked_issues"] += 1
                if all(issue.get("reviews", {}).get(stage) and
                       issue["reviews"][stage]["state"] in ("fixed", "not_applicable")
                       for stage in ("topaz", "dsp_port", "dsp_validation")):
                    bucket["fully_reviewed_issues"] += 1
                else:
                    bucket["remaining_issue_reviews"] += 1
    return {"total": dict(totals), "zones": {zone: dict(values) for zone, values in zones.items()},
            "note": "Unreviewed is unknown, not proof of an unresolved bug. Shared issues are displayed separately."}
