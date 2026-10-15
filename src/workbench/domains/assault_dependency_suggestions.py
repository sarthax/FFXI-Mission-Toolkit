"""Conservative suggested mission links for shared Assault issues.

Candidate-only: never writes a reviewed dependency or asserts a DSP fix.
"""
import re

def suggest(shared, missions):
    by_name = {m["number"]: m for m in missions}
    for section in shared:
        prose = section.get("comments", "")
        candidates = {}
        # Exact mission name mention, with word boundaries to prevent accidental substrings.
        for mission in missions:
            name = mission["name"]
            pattern = r"(?<![A-Za-z0-9])" + re.escape(name) + r"(?![A-Za-z0-9])"
            matches = list(re.finditer(pattern, prose, re.I))
            if matches:
                candidates[mission["number"]] = {
                    "mission": mission["number"], "name": name,
                    "reason": "Exact mission name in shared issue text",
                    "mentions": len(matches),
                    "evidence": prose[max(0, matches[0].start()-70):min(len(prose),matches[0].end()+110)].replace("\n", " ")
                }
        section["suggested_missions"] = sorted(
            (v for n,v in candidates.items() if n not in section.get("missions", [])),
            key=lambda v: (-v["mentions"], v["mission"]))
    return shared
