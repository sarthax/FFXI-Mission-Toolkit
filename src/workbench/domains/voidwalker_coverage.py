"""Read-only, fail-closed Voidwalker validation coverage and next-test queue.

Source presence and historical backlog 'done' do not establish in-game success.
"""
from __future__ import annotations
from collections import Counter

AREA_NAMES = ("pop", "hint", "fight", "model", "drops", "upgrade")
ACCEPTED = frozenset(("ok", "issue", "n/a", "untested"))


def summarize(nms: list[dict], *, limit: int = 30) -> dict:
    counts = {name: Counter() for name in AREA_NAMES}
    by_zone: dict[str, dict] = {}
    next_tests = []
    recorded_keys = set()
    orphan_records = []
    for nm in nms:
        key = str(nm["key"])
        recorded_keys.add(key)
        zone_key = f'{nm["zone_id"]}:{nm["zone"]}'
        zone = by_zone.setdefault(zone_key, {"zone_id": nm["zone_id"], "zone": nm["zone"], "spawns": 0, "untested_checks": 0, "issue_checks": 0})
        zone["spawns"] += 1
        rec = nm.get("validation_rec") or {}
        areas = rec.get("areas") or {}
        pending = []
        issues = []
        for name in AREA_NAMES:
            state = areas.get(name, "untested")
            if state not in ACCEPTED:
                state = "untested"
            counts[name][state] += 1
            if state == "untested":
                pending.append(name)
                zone["untested_checks"] += 1
            elif state == "issue":
                issues.append(name)
                zone["issue_checks"] += 1
        if pending or issues:
            next_tests.append({
                "key": key, "name": nm["name"], "zone_id": nm["zone_id"],
                "zone": nm["zone"], "pending": pending, "issues": issues,
                "recorded": bool(rec), "source_gaps": list(nm.get("gaps") or []),
            })
    next_tests.sort(key=lambda x: (-len(x["issues"]), -len(x["pending"]), x["zone_id"], x["name"], x["key"]))
    total = len(nms)
    return {
        "spawns": total,
        "checks": total * len(AREA_NAMES),
        "area_counts": {name: {state: counts[name][state] for state in ("ok", "issue", "n/a", "untested")} for name in AREA_NAMES},
        "untested_checks": sum(counts[name]["untested"] for name in AREA_NAMES),
        "issue_checks": sum(counts[name]["issue"] for name in AREA_NAMES),
        "zones": sorted(by_zone.values(), key=lambda z: (z["zone_id"], z["zone"])),
        "next_tests": next_tests[:limit],
        "next_tests_total": len(next_tests),
        "truncated": len(next_tests) > limit,
        "note": "Only recorded per-NM area results count as observed. Untested means no recorded result, not a failed feature; n/a is an operator designation, not automatic proof. Missing source data cannot be counted as validated.",
    }
