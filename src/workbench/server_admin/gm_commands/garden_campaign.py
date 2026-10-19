"""Offline, deterministic gardening campaign case generator. No GM/client execution."""
from __future__ import annotations

import itertools
import json
from pathlib import Path

_FIELD = ("pot_type", "plant_type", "crystal1", "crystal2")
_TREE = frozenset({6, 7})


def _pair_keys(case: dict) -> set[tuple]:
    return {(a, case[a], b, case[b]) for a, b in itertools.combinations(_FIELD, 2)}


def generate_campaign(plan: dict) -> dict:
    if plan.get("mode") != "batch_moghouse" or plan.get("execution_enabled") is not False:
        raise ValueError("only non-executing batch_moghouse plans are accepted")
    sample = plan["sampling"]
    count = sample["max_runs"]
    repeat = sample.get("repeat_per_case", 1)
    if type(count) is not int or not 1 <= count <= 1000:
        raise ValueError("max_runs must be 1..1000")
    if type(repeat) is not int or not 1 <= repeat <= 20:
        raise ValueError("repeat_per_case must be 1..20")
    options = plan["inputs"]
    filters = sample.get("filter", {})
    sets = []
    ranges = {"pot_type": plan["setup"]["pot_types"], "plant_type": options["plant_types"],
              "crystal1": options["crystal1"], "crystal2": options["crystal2"]}
    for field in _FIELD:
        values = ranges[field]
        if not isinstance(values, list) or not values or any(type(x) is not int for x in values):
            raise ValueError(f"invalid values for {field}")
        forced = filters.get(field)
        if forced is not None:
            if type(forced) is not int or forced not in values:
                raise ValueError(f"invalid filter for {field}")
            values = [forced]
        sets.append(sorted(set(values)))
    candidates = []
    for pot, plant, first, second in itertools.product(*sets):
        # Second feeding belongs to tree cuttings / saplings only.
        if plant not in _TREE and second != 0:
            continue
        candidates.append(dict(zip(_FIELD, (pot, plant, first, second))))
    if not candidates:
        raise ValueError("no valid cases for selected filters")
    desired = set().union(*(_pair_keys(c) for c in candidates))
    uncovered = desired.copy()
    selected = []
    # Greedy coverage; stable tie order from sorted iteration.
    if sample["strategy"] not in {"pairwise_then_targeted", "full_cartesian"}:
        raise ValueError("unsupported sampling strategy")
    if sample["strategy"] == "full_cartesian":
        if not sample.get("allow_full_cartesian"):
            raise ValueError("full cartesian requires explicit opt-in")
        selected = candidates[:count // repeat]
    else:
        while uncovered and len(selected) * repeat < count:
            best = max(candidates, key=lambda c: len(_pair_keys(c) & uncovered))
            if not (_pair_keys(best) & uncovered):
                break
            selected.append(best)
            uncovered.difference_update(_pair_keys(best))
            candidates.remove(best)
    runs = []
    for i, case in enumerate(selected):
        for r in range(repeat):
            runs.append({"case_id": f"GARD-BATCH-{i+1:04d}-R{r+1:02d}",
                         "inputs": case.copy(), "execution_status": "NOT_RUN",
                         "evidence": [], "mode": "fixture_mechanics"})
    return {"schema_version": 1, "execution_enabled": False, "cases": runs,
            "pairwise_covered": len(desired - uncovered) if sample["strategy"] != "full_cartesian" else len(set().union(*(_pair_keys(c["inputs"]) for c in runs))),
            "pairwise_possible": len(desired),
            "truncated": len(runs) >= count and (bool(uncovered) if sample["strategy"] != "full_cartesian" else len(candidates) > len(selected)),
            "blockers": list(plan.get("blockers", []))}


def generate_from_file(path: str | Path) -> dict:
    return generate_campaign(json.loads(Path(path).read_text(encoding="utf-8")))
