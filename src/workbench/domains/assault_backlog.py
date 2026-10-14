"""Read-only actionable filters over recorded Assault issue reviews.

No status is inferred from historical Topaz prose or candidate fix-log matches.
"""
FILTERS = ("all", "topaz_fixed_unported", "ported_awaiting_test", "blocked", "unreviewed", "open")


def backlog(missions, *, zone="", status="all", search=""):
    if status not in FILTERS:
        raise ValueError("Unknown backlog filter")
    results = []
    search = search.casefold().strip()
    for mission in missions:
        if zone and mission["zone"] != zone:
            continue
        for issue in mission.get("issue_crossrefs", []):
            reviews = issue.get("reviews") or {}
            def state(stage):
                return (reviews.get(stage) or {}).get("state", "unreviewed")
            topaz, port, test = (state(stage) for stage in ("topaz", "dsp_port", "dsp_validation"))
            match = {
                "all": True,
                "topaz_fixed_unported": topaz == "fixed" and port not in ("fixed", "not_applicable"),
                "ported_awaiting_test": port == "fixed" and test not in ("fixed", "not_applicable"),
                "blocked": "blocked" in (topaz, port, test),
                "unreviewed": "unreviewed" in (topaz, port, test),
                "open": "open" in (topaz, port, test),
            }[status]
            if not match:
                continue
            if search and search not in (mission["name"] + " " + issue["text"]).casefold():
                continue
            results.append({"mission": mission["number"], "name": mission["name"],
                            "zone": mission["zone"], "issue": issue["id"],
                            "text": issue["text"], "topaz": topaz, "port": port,
                            "validation": test, "fix_candidates": len(issue.get("candidates", []))})
    return results
