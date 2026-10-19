"""Normalize imported MOG-09 assertion values without inventing missing observations.

The runner's assertion payload is a *single reported source*; mapping both
sides of a comparison does not independently authenticate client or DSP data.
No raw artifact paths are opened, and existing evidence is never modified.
"""
from __future__ import annotations

from .assertion_engine import evaluate
from .test_specifications import specification

_NAMES = {
    "session established for expected character": ("session", "observed"),
    "precondition: Safe holds furnishings with nonzero aura (stored, not installed)": ("stored_furnishings", "observed"),
    "active KI equals oracle for empty layout": ("gm_active_ki", "observed"),
    "aura breakdown all zero": ("gm_aura", "observed"),
}
_ROWS = {
    "client bag equals persisted char_inventory location 0": ("client_bag", "db_bag"),
    "client Mog Safe equals persisted char_inventory location 1": ("client_safe", "db_safe"),
}


def normalize_mog09(record: dict) -> dict:
    if not isinstance(record, dict) or (record.get("feature_id"), record.get("case_id")) != ("moghancement", "MOG-09"):
        raise ValueError("only imported MOG-09 evidence supported")
    evidence = record.get("evidence")
    if not isinstance(evidence, dict) or not isinstance(evidence.get("assertions"), list):
        raise ValueError("MOG-09 assertion evidence missing")
    observations, sources, warnings = {}, {}, []
    for item in evidence["assertions"]:
        if not isinstance(item, dict) or not isinstance(item.get("name"), str):
            continue
        name = item["name"]
        if name in _NAMES:
            field, key = _NAMES[name]
            if key in item and field not in observations:
                observations[field] = item[key]
                sources[field] = "evidence.assertions[name=" + name + "]." + key
        elif name in _ROWS:
            client_field, db_field = _ROWS[name]
            if "observed" in item and client_field not in observations:
                observations[client_field] = item["observed"]
                sources[client_field] = "evidence.assertions[name=" + name + "].observed"
            if "expected" in item and db_field not in observations:
                observations[db_field] = item["expected"]
                sources[db_field] = "evidence.assertions[name=" + name + "].expected"
    context = {}
    raw = evidence.get("observations", {})
    if isinstance(raw, dict):
        prov = raw.get("provenance", {})
        if isinstance(prov, dict) and type(prov.get("charid")) is int:
            context["approved_charid"] = prov["charid"]
            warnings.append("approved_charid comes from runner-reported provenance, not independent operator approval")
    missing = [field for field in ("session", "stored_furnishings", "gm_active_ki", "gm_aura",
                                  "client_bag", "db_bag", "client_safe", "db_safe")
               if field not in observations]
    if missing:
        warnings.append("Unavailable values remain absent: " + ", ".join(missing))
    warnings.append("Client and DB inventory values originate from the same imported runner report, not a fresh independently authenticated capture")
    warnings.append("Client held key items and installed furniture layout are not independently evaluated by MOG-09")
    return {"observations": observations, "context": context, "field_sources": sources,
            "missing_fields": missing, "warnings": warnings, "source": "imported_runner_assertion_payload",
            "execution_enabled": False, "evidence_authenticated": False}


def evaluate_imported_mog09(record: dict) -> dict:
    normalized = normalize_mog09(record)
    result = evaluate(specification("moghancement", "MOG-09"),
                      normalized["observations"], context=normalized["context"])
    return {"normalization": normalized, "evaluation": result,
            "recorded_verdict": record.get("verdict"),
            "comparison_note": "Fresh deterministic re-evaluation of imported values, not a new live run"}
