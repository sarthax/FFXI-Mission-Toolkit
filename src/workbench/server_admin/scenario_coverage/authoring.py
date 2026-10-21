"""Read-only, source-declared behavior candidates for scenario coverage authoring.

A test-readiness case title describes an *intended test*, not a verified
Behavior Trace node, DSP oracle, or executed capability. Handoffs carry ONLY
a bounded reference to that existing row; the editor must resolve/review it
and must not auto-create, auto-save, or execute a draft.
"""
from __future__ import annotations

import re
from urllib.parse import quote

from workbench.server_admin.feature_testing.test_specifications import _ALLOWED_OBSERVATIONS

# Recovery is a category to investigate even when no source case declares it.
REVIEW_CATEGORIES = ("positive", "negative", "boundary", "persistence", "recovery")
_REF = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,119}\Z")
_SOURCE = "data/testing/feature_test_readiness.json"
_CONTRACT = "coverage_behavior_reference_v1"


def _bounded_ref(value: object) -> bool:
    return isinstance(value, str) and _REF.fullmatch(value) is not None


def _lookup(readiness: dict, feature_id: str, behavior_ref: str) -> tuple[dict, dict]:
    """Resolve only exact, committed feature/case identities."""
    if not _bounded_ref(feature_id) or not _bounded_ref(behavior_ref):
        raise ValueError("invalid bounded feature/behavior reference")
    if not isinstance(readiness, dict) or readiness.get("schema_version") != 1:
        raise ValueError("unsupported readiness source")
    features = readiness.get("features")
    if not isinstance(features, list):
        raise ValueError("invalid readiness inventory")
    matches = [f for f in features if isinstance(f, dict) and f.get("id") == feature_id]
    if len(matches) != 1 or not isinstance(matches[0].get("cases"), list):
        raise LookupError("feature not declared")
    feature = matches[0]
    cases = [c for c in feature["cases"] if isinstance(c, dict) and c.get("id") == behavior_ref]
    if len(cases) != 1:
        raise LookupError("behavior case not declared")
    return feature, cases[0]


def draft_context(readiness: dict, feature_id: str, behavior_ref: str) -> dict:
    """Return non-normative reference metadata; *no* spec, ID or assertion generation."""
    feature, case = _lookup(readiness, feature_id, behavior_ref)
    title = case.get("title")
    if not isinstance(title, str) or not 1 <= len(title) <= 240:
        raise ValueError("invalid source case description")
    kind = case.get("kind")
    if not isinstance(kind, str) or not 1 <= len(kind) <= 40:
        raise ValueError("invalid source scenario category")
    return {
        "contract": _CONTRACT,
        "feature_id": feature_id,
        "behavior_ref": behavior_ref,
        "label": title,
        "category": kind,
        "reference_kind": "declared_test_case_intent_not_behavior_trace_identity",
        "source": _SOURCE,
        "source_pointer": f"features[id={feature_id}].cases[id={behavior_ref}]",
        "source_revision": "UNPINNED",
        "proposed_case_id": None,
        "expected_oracle": "UNKNOWN",
        "assertions": [],
        "observations": [],
        "capability_bindings": [],
        "context_only": True,
        "design_only": True,
        "review_required": True,
        "auto_populate_allowed": False,
        "auto_save_allowed": False,
        "execution_enabled": False,
        "note": "Review the declared source case; nothing is an accepted requirement, ID, oracle, or executable specification.",
    }


def _context_url(feature_id: str, behavior_ref: str) -> str:
    return ("/feature-testing/coverage/context/"
            + quote(feature_id, safe="") + "/" + quote(behavior_ref, safe=""))


def _editor_url(feature_id: str, behavior_ref: str) -> str:
    # The editor GETs this read-only reference (same-origin, strict path
    # pattern) and starts an unsaved design-only draft; see the handoff doc.
    return "/scenario-developer?context_ref=" + quote(_context_url(feature_id, behavior_ref), safe="")


def add_behavior_drilldown(matrix: dict, readiness: dict, specs: list[dict],
                           history: list[dict] | None = None) -> dict:
    """Enrich the existing matrix without overwriting its coverage verdicts."""
    if not isinstance(matrix, dict) or not isinstance(matrix.get("features"), list):
        raise ValueError("invalid base coverage model")
    if not isinstance(specs, list) or not isinstance(history, (list, type(None))):
        raise ValueError("invalid projection inputs")
    by_spec = {(s.get("feature_id"), s.get("case_id")): s for s in specs if isinstance(s, dict)}
    history = history or []
    projected = []
    for original in matrix["features"]:
        feature_id = original["id"]
        source_features = [f for f in readiness.get("features", []) if isinstance(f, dict) and f.get("id") == feature_id]
        if len(source_features) != 1:
            raise ValueError("ambiguous readiness feature")
        source_feature = source_features[0]
        source_cases = {c["id"]: c for c in source_feature.get("cases", [])}
        behaviors = []
        for row in original["cases"]:
            case_id = row["id"]
            if not _bounded_ref(feature_id) or not _bounded_ref(case_id) or case_id not in source_cases:
                raise ValueError("unresolved scenario intent")
            intent = source_cases[case_id]
            spec = by_spec.get((feature_id, case_id))
            declared_obs = list(spec.get("observations", [])) if spec is not None else []
            unsupported = sorted(set(declared_obs) - _ALLOWED_OBSERVATIONS)
            required_evidence = intent.get("evidence_required", [])
            if not isinstance(required_evidence, list):
                required_evidence = []
            candidate_capabilities = source_feature.get("headless_candidates", [])
            if not isinstance(candidate_capabilities, list):
                candidate_capabilities = []
            run_mode = intent.get("run_mode", "")
            run_blocked = isinstance(run_mode, str) and run_mode.startswith("blocked")
            if not row["specified"]:
                executable = "BLOCKED_NO_SPECIFICATION"
            elif spec.get("execution_status") != "verified_runner":
                executable = "BLOCKED_DESIGN_ONLY"
            elif unsupported:
                executable = "BLOCKED_UNSUPPORTED_OBSERVATION"
            elif run_blocked:
                executable = "BLOCKED_CAPABILITY_GAP"
            else:
                executable = "NOT_ESTABLISHED_LOCAL_PREFLIGHT_REQUIRED"
            recorded = row.get("recorded")
            verified = row.get("independent_confidence") == "VERIFIED_BY_SEPARATE_TRUSTED_SOURCE"
            status = ("VERIFIED" if verified else "IMPORTED_NOT_INDEPENDENT"
                      if recorded else "SPECIFIED_UNOBSERVED"
                      if row["specified"] else "DECLARED_UNSPECIFIED")
            revisions = {tuple(str(x.get(z, "")) for z in ("dsp_commit", "headless_commit", "toolkit_commit"))
                         for x in history if isinstance(x, dict) and
                         (x.get("feature_id"), x.get("case_id")) == (feature_id, case_id)}
            cross_run_warning = len(revisions) > 1
            revision_alert = ("CONFLICTING_OR_STALE_REVISION" if row["version_comparison"] == "VERSION_MISMATCH"
                              else "UNPINNED_SCENARIO_REVISION" if row["version_comparison"] == "REVISION_UNPINNED"
                              else "HISTORICAL_ENGINE_REVISIONS_DIFFER" if cross_run_warning else None)
            context_path = _context_url(feature_id, case_id)
            behaviors.append({
                "behavior_ref": case_id,
                "intent": row["title"], "category": row["category"],
                "source_kind": "declared_test_case_intent_not_verified_behavior",
                "source": _SOURCE,
                "coverage_status": status,
                "planned": True,
                "specified": row["specified"],
                "executable": executable,
                "observed": "IMPORTED_UNVERIFIED" if recorded else "NOT_OBSERVED",
                "verified": verified,
                "version_alert": revision_alert,
                "version_comparison": row["version_comparison"],
                "observed_verdict": recorded["verdict"] if recorded else "UNKNOWN",
                "recalculated_verdict": row["recalculated"]["verdict"],
                "evidence_requirements": [x for x in required_evidence if isinstance(x, str)][:20],
                "unsupported_observations": unsupported,
                "candidate_capabilities": [x for x in candidate_capabilities if isinstance(x, str)][:20],
                "capability_status": "UNVERIFIED_CANDIDATES" if candidate_capabilities else "NO_REGISTERED_CAPABILITIES",
                "oracle_status": row["oracle"], "readback_status": row["readback"],
                "gaps": row["gaps"],
                "scenario_url": row["scenario_url"], "run_url": row["run_url"],
                "run_history_url": "/feature-testing?tab=runs&feature=" + quote(feature_id, safe=""),
                "context_url": context_path,
                "editor_url": _editor_url(feature_id, case_id),
                "editor_context_consumed": False,
            })
        categories = []
        for category in REVIEW_CATEGORIES:
            matches = [x for x in behaviors if x["category"] == category]
            categories.append({
                "category": category, "declared": len(matches),
                "specified": sum(x["specified"] for x in matches),
                "observed": sum(x["observed"] == "IMPORTED_UNVERIFIED" for x in matches),
                "verified": sum(x["verified"] for x in matches),
                "missing_category": not matches,
                "interpretation": "No scenario of this category declared; NOT a fabricated requirement"
                                  if not matches else "Declared scenario-intent inventory only",
            })
        projected.append({**original,
                          "behavior_drilldown": behaviors,
                          "category_gaps": categories,
                          "intent_source": _SOURCE,
                          "behavior_trace_relation": "UNVERIFIED_NOT_A_GRAPH_EDGE"})
    return {**matrix, "features": projected,
            "handoff_contract": _CONTRACT,
            "handoff_note": "Context references are read-only. Agent B's editor currently ignores context_ref; no draft is automatically populated or saved.",
            "execution_enabled": False}
