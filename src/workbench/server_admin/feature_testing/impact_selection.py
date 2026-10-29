"""R6 #1210 WP2: rank scenario cases that a DSP revision change MIGHT affect.

Design: docs/workbench/R6_REGRESSION_IMPACT_DESIGN_1199_1210.md. A pure, offline function: it reads a validated
change set (``impact_changeset``), scenario specifications and optional explicit Feature Trace links. It never runs
git, touches a database or the network, launches anything, or concludes that a case IS affected. A candidate is a
suggestion with the reasons it was suggested; ``unlinked_changes`` and ``cases_without_sources`` disclose what the
analysis cannot see.

Links are explicit only: a scenario's declared ``dsp_source`` citation, or a caller-supplied trace link that cites
the edge it came from. Nothing is inferred from names, proximity or display order.
"""
from __future__ import annotations

from .impact_changeset import validate_change_set
from .scenario_contract_v2 import validate_contract_v2

CONFIDENCE_ORDER = ("DIRECT_SPAN", "DIRECT_PATH", "INFERRED")  # strongest first; UNKNOWN is never a candidate
_RANK = {name: index for index, name in enumerate(CONFIDENCE_ORDER)}
_EDGE_KEYS = {"provider", "relationship", "ref"}


def _clean_trace_links(trace_links) -> list[dict]:
    out = []
    for index, link in enumerate(trace_links or ()):
        if not isinstance(link, dict) or set(link) != {"path", "feature_id", "edge"}:
            raise ValueError(f"trace_links[{index}] must have exactly path, feature_id and edge")
        edge = link["edge"]
        if not isinstance(edge, dict) or set(edge) != _EDGE_KEYS or not all(
                isinstance(edge[k], str) and edge[k].strip() for k in _EDGE_KEYS):
            raise ValueError(f"trace_links[{index}].edge must cite provider, relationship and ref; "
                             "an inferred link without its source edge is not accepted")
        if not all(isinstance(link[k], str) and link[k] for k in ("path", "feature_id")):
            raise ValueError(f"trace_links[{index}] path and feature_id must be non-empty strings")
        out.append({"path": link["path"], "feature_id": link["feature_id"], "edge": dict(edge)})
    return out


def _overlaps(start: int, end: int, hunks: list[list[int]]) -> bool:
    return any(h_start <= end and start <= h_end for h_start, h_end in hunks)


def _associations(spec: dict, ref: str) -> list[str]:
    """Explicit author associations for a source ref; absence stays UNKNOWN (never inferred)."""
    found = []
    for item in (spec.get("contract_v2") or {}).get("source_associations", []):
        if ref in item["source_refs"]:
            found.append("case" if item["scope"] == "case" else "step:" + item["target_id"])
    return sorted(found) or ["UNKNOWN"]


def _why_not_span(pinned: bool, on_base: bool, has_span: bool, has_hunks: bool) -> list[str]:
    """First failing precondition for a line-level (DIRECT_SPAN) match."""
    if not pinned:
        return ["SOURCE_REVISION_UNPINNED"]
    if not on_base:
        return ["SOURCE_REVISION_DIFFERS"]
    if not has_span:
        return ["SOURCE_NO_LINE_SPAN"]
    if not has_hunks:
        return ["NO_HUNKS"]
    return ["NO_LINE_OVERLAP"]


def _classify(source: dict, change: dict, base_sha: str) -> tuple[str, list[str]]:
    """Return (confidence, reason/flag codes) for one citation against one change."""
    status = change["status"]
    pinned = source["revision"] is not None
    on_base = pinned and source["revision"].lower() == base_sha
    has_span = source["line_start"] is not None
    if status == "A":
        return "DIRECT_PATH", ["PATH_ADDED_AFTER_BASE"]
    if status == "D":
        if on_base and has_span:  # every cited line disappears with the file
            return "DIRECT_SPAN", ["SPAN_REMOVED", "SOURCE_REMOVED"]
        return "DIRECT_PATH", _why_not_span(pinned, on_base, has_span, True) + ["SOURCE_REMOVED"]
    flags = ["SOURCE_RENAMED"] if status == "R" else []
    hunks = change["hunks"]
    if on_base and has_span and hunks is not None and _overlaps(source["line_start"], source["line_end"], hunks):
        return "DIRECT_SPAN", ["SPAN_OVERLAP"] + flags
    return "DIRECT_PATH", _why_not_span(pinned, on_base, has_span, hunks is not None) + flags


def select_candidates(change_set: dict, scenarios: list[dict], trace_links=()) -> dict:
    """Rank scenario cases for a change set. See the module docstring for guarantees."""
    changes = validate_change_set(change_set)
    base_sha, repository = changes["base_sha"], changes["repository"]
    links = _clean_trace_links(trace_links)
    if not isinstance(scenarios, list):
        raise ValueError("scenarios must be a list of scenario specifications")

    cases: dict[tuple[str, str], dict] = {}
    invalid = []
    for spec in scenarios:
        key = (spec.get("feature_id"), spec.get("case_id")) if isinstance(spec, dict) else (None, None)
        if not all(isinstance(part, str) and part for part in key):
            invalid.append({"feature_id": key[0], "case_id": key[1], "error": "missing feature_id or case_id"})
            continue
        if key in cases or any(i["feature_id"] == key[0] and i["case_id"] == key[1] for i in invalid):
            raise ValueError(f"duplicate scenario {key[0]}/{key[1]}")
        sources = []
        if spec.get("contract_v2") is not None:
            try:
                validate_contract_v2(spec)
            except (ValueError, KeyError, TypeError) as exc:
                invalid.append({"feature_id": key[0], "case_id": key[1], "error": str(exc)})
                continue
            sources = [s for s in spec["contract_v2"]["sources"]
                       if s["classification"] == "dsp_source" and s["repository"] == repository]
        cases[key] = {"spec": spec, "sources": sources}

    candidates: dict[tuple[str, str], dict] = {}
    linked_paths: set[str] = set()

    def add(key, confidence, reasons, flags, change_path):
        entry = candidates.setdefault(key, {"confidence": confidence, "flags": set(), "reasons": [],
                                            "paths": set()})
        if _RANK[confidence] < _RANK[entry["confidence"]]:
            entry["confidence"] = confidence
        entry["flags"].update(flags)
        entry["reasons"].extend(reasons)
        entry["paths"].add(change_path)

    for change in changes["changes"]:
        base_path = change["old_path"] or change["path"]  # the path as it existed at base_sha
        for key, case in cases.items():
            for source in case["sources"]:
                if source["path"] != base_path and not (change["status"] == "A" and source["path"] == change["path"]):
                    continue
                confidence, codes = _classify(source, change, base_sha)
                flags = [c for c in codes if c in ("SOURCE_REMOVED", "SOURCE_RENAMED")]
                reasons = [{"code": c, "change_path": change["path"], "change_status": change["status"],
                            "source_ref": source["ref"], "source_path": source["path"],
                            "lines": [source["line_start"], source["line_end"]]
                            if source["line_start"] is not None else None,
                            "associated_to": _associations(case["spec"], source["ref"])}
                           for c in codes if c not in flags]
                reasons += [{"code": f, "change_path": change["path"], "change_status": change["status"],
                             "source_ref": source["ref"], "source_path": source["path"], "lines": None,
                             "associated_to": _associations(case["spec"], source["ref"])} for f in flags]
                add(key, confidence, reasons, flags, change["path"])
                linked_paths.add(change["path"])
        for link in links:
            if link["path"] not in (change["path"], change["old_path"]):
                continue
            linked_paths.add(change["path"])
            for key in cases:
                if key[0] == link["feature_id"]:
                    add(key, "INFERRED", [{"code": "TRACE_EDGE", "change_path": change["path"],
                                           "change_status": change["status"], "source_ref": None,
                                           "source_path": link["path"], "lines": None,
                                           "trace_edge": dict(link["edge"])}], [], change["path"])

    ordered = []
    for (feature_id, case_id), entry in candidates.items():
        reasons = sorted(entry["reasons"], key=lambda r: (r["code"], r["change_path"], r["source_ref"] or ""))
        ordered.append({"feature_id": feature_id, "case_id": case_id, "confidence": entry["confidence"],
                        "flags": sorted(entry["flags"]), "changed_path_count": len(entry["paths"]),
                        "reasons": reasons})
    ordered.sort(key=lambda c: (_RANK[c["confidence"]], 0 if "SOURCE_REMOVED" in c["flags"] else 1,
                                -c["changed_path_count"], c["feature_id"], c["case_id"]))

    features_with_cases = {key[0] for key in cases}
    return {
        "schema_version": 1, "repository": repository, "base_sha": base_sha, "head_sha": changes["head_sha"],
        "candidates": ordered,
        "unlinked_changes": [{"path": c["path"], "status": c["status"]} for c in changes["changes"]
                             if c["path"] not in linked_paths],
        "trace_links_without_cases": sorted({link["feature_id"] for link in links
                                             if link["feature_id"] not in features_with_cases}),
        "cases_without_sources": sorted(f"{k[0]}/{k[1]}" for k, v in cases.items() if not v["sources"]),
        "invalid_scenarios": sorted(invalid, key=lambda i: (str(i["feature_id"]), str(i["case_id"]))),
        "launch": "NOT_PERFORMED",
        "note": "Candidates are suggestions from explicit citations and cited trace edges only; "
                "selection is not an impact finding and nothing was launched.",
    }
