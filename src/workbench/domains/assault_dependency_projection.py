"""Project confirmed shared dependencies into Assault mission detail panels.

Keep zone-scope and explicit mission links deduplicated, with no inferred closure.
"""
def project(missions, shared):
    for mission in missions:
        dependencies=[]
        for index, section in enumerate(shared, 1):
            direct=mission["number"] in section.get("missions", [])
            zone_matches=[z for z in section.get("zones", []) if z["zone"] == mission["zone"]]
            if not direct and not zone_matches:
                continue
            reviews=section.get("reviews", {})
            dependencies.append({
                "section_id": index, "title": section["title"],
                "scope": "direct + zone" if direct and zone_matches else ("direct" if direct else "zone"),
                "evidence": [r["evidence"] for r in zone_matches],
                "topaz": (reviews.get("topaz") or {}).get("state", "unreviewed"),
                "port": (reviews.get("dsp_port") or {}).get("state", "unreviewed"),
                "validation": (reviews.get("dsp_validation") or {}).get("state", "unreviewed"),
            })
        mission["shared_dependencies"] = dependencies
    return missions
