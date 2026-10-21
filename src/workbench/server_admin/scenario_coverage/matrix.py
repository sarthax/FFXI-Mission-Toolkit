"""Evidence-conservative Feature -> Scenario matrix projection (#1207).

No writes, runtime probes, GM commands, or arbitrary graph linking. Inputs are
read-only catalog snapshots plus imported history. A trusted assessment is a
separate future integration seam, NEVER sourced from a run's evidence_json;
the production router deliberately passes none.
"""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from urllib.parse import quote

CATEGORIES = ("positive", "negative", "boundary", "persistence")
COVERAGE_STATES = ("complete", "partial", "untested", "blocked")
# Navigation links are human research paths, not verified graph relationships.
FEATURE_NAVIGATION = {
    "assault_nyzul": ("assault", "nyzul"),
    "missions_quests": ("mission-browser",),
}

def spec_digest(spec: dict) -> str:
    """Digest of the complete declared spec, not a Git commit or approval."""
    raw = json.dumps(spec, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _latest_record(records: list[dict]) -> dict | None:
    if not records:
        return None
    ordered = sorted(records, key=lambda x: (str(x.get("observed_at", "")), str(x.get("run_id", ""))), reverse=True)
    run = ordered[0]["run_id"]
    selected = [r for r in ordered if r.get("run_id") == run]
    verdicts = {r.get("verdict") for r in selected}
    verdict = ("FAIL" if "FAIL" in verdicts else
               "BLOCKED" if "BLOCKED" in verdicts else
               "UNKNOWN" if "SKIPPED" in verdicts else
               "PASS" if verdicts == {"PASS"} else "UNKNOWN")
    return {
        "run_id": run,
        "observed_at": ordered[0].get("observed_at"),
        "verdict": verdict,
        "stage_verdicts": [{"stage": r.get("stage"), "verdict": r.get("verdict")} for r in selected],
        "dsp_commit": ordered[0].get("dsp_commit"),
        "headless_commit": ordered[0].get("headless_commit"),
        "toolkit_commit": ordered[0].get("toolkit_commit"),
        "record": ordered[0],
        "all_stage_records": selected,
    }


def _spec_comparison(record: dict | None, digest: str | None) -> str:
    if not record or not digest:
        return "UNKNOWN"
    evidence = record.get("evidence")
    if not isinstance(evidence, dict):
        return "UNKNOWN"
    reported = evidence.get("spec_digest")
    if not isinstance(reported, str) or not reported:
        return "REVISION_UNPINNED"
    return "MATCH" if reported == digest else "VERSION_MISMATCH"


def _run_revision_status(latest: dict | None, digest: str | None) -> str:
    """Every stage of one imported run must refer to the same spec/source revision."""
    if latest is None:
        return "UNKNOWN"
    stages = latest["all_stage_records"]
    statuses = [_spec_comparison(row, digest) for row in stages]
    versions = {(row.get("dsp_commit"), row.get("headless_commit"), row.get("toolkit_commit"))
                for row in stages}
    if "VERSION_MISMATCH" in statuses or len(versions) != 1:
        return "VERSION_MISMATCH"
    if "REVISION_UNPINNED" in statuses:
        return "REVISION_UNPINNED"
    return "MATCH" if statuses and set(statuses) == {"MATCH"} else "UNKNOWN"


def _safe_recalculation(record: dict | None, spec: dict | None, match: str) -> dict:
    if not record:
        return {"verdict": "UNKNOWN", "reason": "No imported observation"}
    if spec is None:
        return {"verdict": "UNKNOWN", "reason": "No canonical specification"}
    if match != "MATCH":
        return {"verdict": "UNKNOWN", "reason": "Scenario revision missing or mismatched"}
    if (spec.get("feature_id"), spec.get("case_id")) != ("moghancement", "MOG-09"):
        return {"verdict": "UNKNOWN", "reason": "No deterministic import normalizer for this case"}
    # Re-evaluated values are read from this same imported report; even a
    # matching digest and PASS are NOT independent verification.
    try:
        from workbench.server_admin.feature_testing.normalized_evidence import normalize_mog09
        from workbench.server_admin.feature_testing.assertion_engine import evaluate
        observation = normalize_mog09(record)
        result = evaluate(spec, observation["observations"], context=observation["context"])
        return {"verdict": result["verdict"], "reason": "Deterministic replay of same imported report; not independent proof",
                "authenticated": False,
                "missing_fields": observation["missing_fields"]}
    except (ValueError, TypeError, KeyError) as exc:
        return {"verdict": "UNKNOWN", "reason": "Imported observations cannot be safely recalculated"}


def _trusted_case(trust: dict | None, key: tuple, digest: str | None) -> dict:
    """Only an out-of-band, trusted service could eventually fill this seam.

    The web endpoint never accepts user-supplied trust or reads it from evidence.
    """
    entry = (trust or {}).get(key)
    if not isinstance(entry, dict) or digest is None:
        return {"oracle": False, "readback": False, "verified": False}
    version_ok = entry.get("spec_digest") == digest
    oracle = version_ok and entry.get("oracle") is True
    readback = version_ok and entry.get("readback") is True
    verified = oracle and readback and entry.get("independent_run") is True and entry.get("complete") is True
    return {"oracle": oracle, "readback": readback, "verified": verified}


def _case_row(feature: dict, case: dict, spec: dict | None, history: list[dict],
              trusted: dict | None, *, history_complete: bool) -> dict:
    fid, cid = feature["id"], case["id"]
    digest = spec_digest(spec) if spec else None
    latest = _latest_record(history)
    revision = _run_revision_status(latest, digest)
    evidence = _safe_recalculation(latest["record"] if latest else None, spec, revision)
    attest = _trusted_case(trusted, (fid, cid), digest)
    gaps = list(dict.fromkeys([*feature.get("gaps", []), *case.get("blocking_gaps", [])]))
    run_mode = case.get("run_mode", "")
    if isinstance(run_mode, str) and run_mode.startswith("blocked"):
        gaps.append("Execution lane blocked: " + run_mode)
    if not spec:
        gaps.append("No canonical scenario specification")
    elif spec.get("execution_status") == "design_only":
        gaps.append("Design-only specification; no executable runner")
    if not attest["oracle"]:
        gaps.append("Authoritative, source-cited expected-outcome oracle not independently verified")
    if not attest["readback"]:
        gaps.append("Independent observer/readback and completeness not verified")
    if revision == "VERSION_MISMATCH":
        gaps.append("Imported run is tied to a different scenario digest")
    elif revision == "REVISION_UNPINNED":
        gaps.append("Imported result has no scenario specification digest")
    if latest and not history_complete:
        gaps.append("Recent-history window truncated; latest evidence may be incomplete")
    gaps = list(dict.fromkeys(gaps))
    verified = bool(attest["verified"] and latest and revision == "MATCH"
                    and latest["verdict"] == "PASS" and not gaps)
    if verified:
        state = "complete"
    elif gaps:
        state = "blocked"
    elif latest:
        state = "partial"
    else:
        state = "untested"
    maturity = ("unwritten" if not spec else
                "design_only" if spec.get("execution_status") == "design_only" else
                "runner_declared_not_approved")
    readiness = ("blocked" if gaps else "requires_local_operator_preflight")
    return {
        "id": cid, "title": case.get("title") or (spec or {}).get("name") or cid,
        "category": case.get("kind", "unspecified"),
        "specified": spec is not None, "spec_maturity": maturity,
        "spec_digest": digest, "runner": (spec or {}).get("runner"),
        "readiness": readiness, "state": state,
        "oracle": "SOURCE_VERIFIED" if attest["oracle"] else "UNKNOWN",
        "readback": "INDEPENDENT" if attest["readback"] else "UNKNOWN",
        "independent_confidence": "VERIFIED_BY_SEPARATE_TRUSTED_SOURCE" if verified else "UNVERIFIED",
        "version_comparison": revision,
        "recorded": ({k:v for k,v in latest.items() if k not in ("record", "all_stage_records")} if latest else None),
        "recalculated": evidence, "gaps": gaps,
        "scenario_url": "/feature-testing/scenario/" + quote(fid, safe="") + "/" + quote(cid, safe=""),
        "run_url": "/feature-testing/run/" + quote(str(latest["run_id"]), safe="") if latest else None,
    }


def build_matrix(readiness_catalog: dict, specifications: list[dict],
                 imported_records: list[dict], feature_catalog: list[dict],
                 *, trusted_assessments: dict | None = None,
                 history_complete: bool = True) -> dict:
    """Pure, deterministic view; never equate planned/spec/executed/verified.

    The trusted_assessments test seam is intentionally NOT supplied by the web
    router: historical import fields are never allowed to create trust.
    """
    if readiness_catalog.get("schema_version") != 1 or not isinstance(readiness_catalog.get("features"), list):
        raise ValueError("unsupported readiness catalog")
    if not isinstance(specifications, list) or not isinstance(imported_records, list) or not isinstance(feature_catalog, list):
        raise ValueError("invalid projection inputs")
    spec_map = {}
    for spec in specifications:
        if not isinstance(spec, dict) or not isinstance(spec.get("feature_id"), str) or not isinstance(spec.get("case_id"), str):
            raise ValueError("invalid specification identity")
        key = (spec["feature_id"], spec["case_id"])
        if key in spec_map:
            raise ValueError("duplicate canonical specification")
        spec_map[key] = spec
    records_by = {}
    for record in imported_records:
        if not isinstance(record, dict):
            raise ValueError("invalid imported record")
        records_by.setdefault((record.get("feature_id"), record.get("case_id")), []).append(record)
    navigation = {x["id"]: x for x in feature_catalog if isinstance(x, dict) and isinstance(x.get("id"), str)}
    projected = []
    referenced = set()
    for feature in readiness_catalog["features"]:
        if not isinstance(feature, dict) or not isinstance(feature.get("id"), str) or not isinstance(feature.get("cases"), list):
            raise ValueError("invalid readiness feature")
        fid = feature["id"]
        cases = []
        seen = set()
        categories = {name: {"planned": 0, "specified": 0, "recorded": 0, "independent": 0} for name in CATEGORIES}
        for case in feature["cases"]:
            if not isinstance(case, dict) or not isinstance(case.get("id"), str) or case["id"] in seen:
                raise ValueError("invalid or duplicate case")
            seen.add(case["id"])
            key = (fid, case["id"])
            referenced.add(key)
            entry = _case_row(feature, case, spec_map.get(key), records_by.get(key, []),
                              trusted_assessments, history_complete=history_complete)
            cases.append(entry)
            cat = entry["category"]
            if cat not in categories:
                categories[cat] = {"planned": 0, "specified": 0, "recorded": 0, "independent": 0}
            totals = categories[cat]
            totals["planned"] += 1
            totals["specified"] += int(entry["specified"])
            totals["recorded"] += int(entry["recorded"] is not None)
            totals["independent"] += int(entry["independent_confidence"] == "VERIFIED_BY_SEPARATE_TRUSTED_SOURCE")
        states = {c["state"] for c in cases}
        status = ("complete" if cases and states == {"complete"} else
                  "partial" if "complete" in states or "partial" in states else
                  "blocked" if "blocked" in states else "untested")
        doc_links = [{"label": navigation[x]["name"], "url": navigation[x]["route"],
                      "provenance": "catalog navigation only; linkage unverified"}
                     for x in FEATURE_NAVIGATION.get(fid, ()) if x in navigation]
        projected.append({
            "id": fid, "name": feature.get("name", fid), "domain": fid,
            "state": status, "cases": cases, "categories": categories,
            "feature_gaps": feature.get("gaps", []),
            "documentation": doc_links,
            "catalog_search_url": "/feature-catalog?q=" + quote(feature.get("name", fid), safe=""),
            "trace_url": "/features/trace?q=" + quote(feature.get("name", fid), safe=""),
            "behavior_url": "/behavior",
            "relationship_confidence": "research_navigation_only",
        })
    orphan_specs = sorted([{"feature_id": a, "case_id": b} for a,b in spec_map if (a,b) not in referenced],
                          key=lambda x: (x["feature_id"], x["case_id"]))
    orphan_evidence = sorted([{"feature_id": str(a), "case_id": str(b)}
                              for a,b in records_by if (a,b) not in referenced],
                             key=lambda x:(x["feature_id"],x["case_id"]))
    return {
        "features": projected, "domains": [{"id": f["id"], "name": f["name"]} for f in projected],
        "states": COVERAGE_STATES, "categories": CATEGORIES,
        "orphan_specifications": orphan_specs, "orphan_evidence": orphan_evidence,
        "history_complete": bool(history_complete),
        "disclaimer": "No percentages. Imported PASS and deterministic replay are not independent verification. "
                      "Unmatched feature identifiers and source/trace links are not inferred.",
        "execution_enabled": False,
    }


def filter_matrix(matrix: dict, *, domain: str = "", readiness: str = "") -> dict:
    """Bounded exact filters; unknown input does not silently switch to all."""
    valid_domains = {x["id"] for x in matrix["domains"]}
    if domain and domain not in valid_domains:
        raise ValueError("unknown coverage domain")
    if readiness and readiness not in COVERAGE_STATES:
        raise ValueError("unknown coverage state")
    return {**matrix, "selected_domain": domain, "selected_readiness": readiness,
            "features": [f for f in matrix["features"] if
                         (not domain or f["domain"] == domain) and
                         (not readiness or f["state"] == readiness)]}
