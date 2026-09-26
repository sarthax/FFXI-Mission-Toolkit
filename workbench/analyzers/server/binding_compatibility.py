"""Snapshot-scoped, evidence-preserving comparison of indexed Lua binding surfaces.

Matches describe indexed API shape, never runtime or behavioral compatibility.
No extractor's failure to recognize a registration proves that it is absent.
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
from dataclasses import asdict
import hashlib
import json

from workbench.core.schema import AnalysisResult, Finding


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _id(value):
    return hashlib.sha256(_json(value).encode()).hexdigest()


def _signature(function):
    sig = function.get("signature") or {}
    return {key: sig.get(key) for key in
            ("return_type", "parameters", "const", "static", "noexcept")}


def _surface(payload):
    sid = payload.get("source_snapshot_id") or payload.get("analysis", {}).get("source_snapshot_id")
    if not isinstance(sid, str) or not sid:
        raise ValueError("Each input must identify its source_snapshot_id")
    bindings = deepcopy(payload.get("bindings", []))
    functions = deepcopy(payload.get("functions", []))
    for kind, rows, key in (("binding", bindings, "binding_id"), ("function", functions, "function_id")):
        seen = set()
        for row in rows:
            if row.get("source_snapshot_id") != sid:
                raise ValueError(f"{kind} snapshot missing or inconsistent with input snapshot {sid}")
            if not row.get(key) or row[key] in seen:
                raise ValueError(f"Missing or duplicate {key} within snapshot {sid}")
            seen.add(row[key])
    by_symbol = {}
    by_id = {f["function_id"]: f for f in functions}
    for f in functions:
        by_symbol.setdefault(f.get("qualified_name"), []).append(f)
    for b in bindings:
        if not b.get("lua_name"):
            raise ValueError("Binding lua_name is required")
        matches = by_symbol.get(b.get("cpp_symbol"), []) if b.get("cpp_symbol") else []
        selected = by_id.get(b.get("function_id"))
        # Recheck the whole symbol family; the old indexer can pick the first overload.
        signatures = {_json(_signature(f)) for f in matches}
        conflict = bool(b.get("function_id") and (not selected or selected not in matches))
        resolution = "RESOLVED"
        if conflict or not matches or not b.get("class_name") or not b.get("binding_system"):
            resolution = "UNRESOLVED"
        elif len(signatures) > 1 or sum(bool(f.get("definition")) for f in matches) > 1:
            resolution = "AMBIGUOUS"
        elif any(not (f.get("signature") or {}).get("return_type") for f in matches):
            resolution = "UNRESOLVED"
        b["resolution"] = resolution
        b["resolved_functions"] = sorted(matches, key=_json)
    return sid, sorted(bindings, key=_json)


def compare_bindings(source, target):
    """Return deterministic JSON plus canonical AnalysisResult/Finding records.

    Inputs are cpp_api_index JSON envelopes (all server families use that common
    schema). Snapshot IDs are mandatory on every binding and function. Legacy
    name-only caches require reindexing: their missing symbol data is not guessed.
    """
    source_sid, sources = _surface(source)
    target_sid, targets = _surface(target)
    identity = {"version": 1, "source": sources, "target": targets,
                "source_snapshot_id": source_sid, "target_snapshot_id": target_sid,
                "source_coverage": source.get("binding_coverage"),
                "target_coverage": target.get("binding_coverage")}
    analysis_id = "binding-compatibility:" + _id(identity)
    results = []
    for src in sources:
        exact = [t for t in targets if (t.get("lua_name"), t.get("class_name")) ==
                 (src.get("lua_name"), src.get("class_name"))]
        candidates = exact or [t for t in targets if
            t["lua_name"] == src["lua_name"] or
            (src.get("cpp_symbol") and t.get("cpp_symbol") == src["cpp_symbol"]) or
            (t.get("class_name") == src.get("class_name") and
             t["lua_name"].casefold() == src["lua_name"].casefold())]
        if exact:
            match_basis = ["LUA_NAME", "CLASS"]
        elif candidates:
            match_basis = sorted({basis for target in candidates for basis, matched in (
                ("LUA_NAME", target["lua_name"] == src["lua_name"]),
                ("CPP_SYMBOL", bool(src.get("cpp_symbol")) and target.get("cpp_symbol") == src["cpp_symbol"]),
                ("CASEFOLD_NAME_AND_CLASS", target.get("class_name") == src.get("class_name") and
                 target["lua_name"].casefold() == src["lua_name"].casefold()),
            ) if matched})
        else:
            match_basis = []
        changes = []
        if len(candidates) > 1 or src["resolution"] == "AMBIGUOUS" or any(
                t["resolution"] == "AMBIGUOUS" for t in candidates):
            category = "AMBIGUOUS"
        elif src["resolution"] != "RESOLVED" or any(
                t["resolution"] != "RESOLVED" for t in candidates):
            category = "UNRESOLVED"
        elif not candidates:
            category = "MISSING_BINDING"
        else:
            dst = candidates[0]
            for key in ("lua_name", "class_name", "binding_system", "cpp_symbol"):
                if src.get(key) != dst.get(key):
                    changes.append(key)
            if _signature(src["resolved_functions"][0]) != _signature(dst["resolved_functions"][0]):
                changes.append("function_signature")
            if "lua_name" in changes or "class_name" in changes:
                category = "RENAMED_CLASS_DRIFT_CANDIDATE"
            elif "cpp_symbol" in changes or "function_signature" in changes:
                category = "IMPLEMENTATION_DRIFT"
            elif "binding_system" in changes:
                category = "REPRESENTATION_DRIFT"
            else:
                category = "EXACT_MATCH"
        results.append({"category": category, "confidence": "INFERRED" if candidates and
                        category not in ("UNRESOLVED", "AMBIGUOUS") else "UNKNOWN",
                        "source": src, "target_candidates": candidates, "changed_fields": changes,
                        "match_basis": match_basis,
                        "evidence": {
                            "source": {key: src.get(key) for key in
                                       ("binding_id", "evidence_id", "path", "line", "source_snapshot_id")},
                            "targets": [{key: target.get(key) for key in
                                         ("binding_id", "evidence_id", "path", "line", "source_snapshot_id")}
                                        for target in candidates],
                        },
                        "source_snapshot_id": source_sid, "target_snapshot_id": target_sid,
                        "absence_scope": "INDEXED_SURFACE_ONLY" if not candidates else None})
    findings = [asdict(Finding(
        finding_id=analysis_id + ":" + _id(row), analysis_id=analysis_id,
        subject_id=row["source"]["binding_id"], field="binding_compatibility", value=row,
        status="UNKNOWN" if row["confidence"] == "UNKNOWN" else "DISCOVERED",
        confidence=row["confidence"], evidence_id=row["source"].get("evidence_id"),
        source_snapshot_id=source_sid,
        notes=["Indexed structural comparison only; no runtime/behavioral equivalence or absence proof."]
    )) for row in results]
    return {"schema": 1, "source_snapshot_id": source_sid, "target_snapshot_id": target_sid,
            "analysis": asdict(AnalysisResult(analysis_id, "BINDING_COMPATIBILITY", source_sid,
                target=target_sid, status="ANALYZED", source_snapshot_id=source_sid,
                findings=[f["finding_id"] for f in findings], tool_version="1",
                notes=["Both macro systems are compared together; extraction coverage is not assumed complete."])),
            "coverage": {"source": source.get("binding_coverage", {"status": "UNKNOWN"}),
                         "target": target.get("binding_coverage", {"status": "UNKNOWN"})},
            "summary": dict(sorted(Counter(r["category"] for r in results).items())),
            "results": results, "findings": findings}
