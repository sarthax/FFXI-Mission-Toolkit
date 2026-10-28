"""R6 #1210 WP3: how well do scenarios cite DSP source, and how many citations are pinned? (design section 4/4a)

Impact selection can only be as precise as scenario citations. This pure, offline report makes that visible
before anyone trusts a selection: per feature, how many cases are fully pinned, partially pinned, cite only
unpinned DSP source, or cite none, plus how many legacy unpinned citations remain (the warn-only debt from the
pin policy). It reads scenario specifications only; it never runs git, reads a database or launches anything,
and a pin is a CLAIM about a commit, not proof the commit exists or the lines say what the author believes.
"""
from __future__ import annotations

from .scenario_contract_v2 import validate_contract_v2

CATEGORIES = ("fully_pinned", "partially_pinned", "unpinned_only", "no_dsp_source")


def _category(sources: list[dict]) -> str:
    if not sources:
        return "no_dsp_source"
    pinned = sum(1 for s in sources if s["revision"] is not None)
    if pinned == len(sources):
        return "fully_pinned"
    return "partially_pinned" if pinned else "unpinned_only"


def source_citation_coverage(scenarios: list[dict], repository: str | None = None) -> dict:
    """Summarize ``dsp_source`` citation pinning per feature.

    ``repository`` restricts which citations count (the repository name exactly as written in
    ``contract_v2.sources``); ``None`` counts every ``dsp_source`` citation. Scenarios without a ``contract_v2``
    namespace are counted as ``no_dsp_source``; scenarios whose v2 metadata fails validation are listed under
    ``invalid_scenarios`` and excluded from the counts, never guessed at.
    """
    if not isinstance(scenarios, list):
        raise ValueError("scenarios must be a list of scenario specifications")
    features: dict[str, dict] = {}
    invalid, seen = [], set()
    for spec in scenarios:
        feature = spec.get("feature_id") if isinstance(spec, dict) else None
        case = spec.get("case_id") if isinstance(spec, dict) else None
        if not isinstance(feature, str) or not feature or not isinstance(case, str) or not case:
            invalid.append({"feature_id": feature, "case_id": case, "error": "missing feature_id or case_id"})
            continue
        if (feature, case) in seen:
            raise ValueError(f"duplicate scenario {feature}/{case}")
        seen.add((feature, case))
        sources: list[dict] = []
        if spec.get("contract_v2") is not None:
            try:
                validate_contract_v2(spec)
            except (ValueError, KeyError, TypeError) as exc:
                invalid.append({"feature_id": feature, "case_id": case, "error": str(exc)})
                continue
            sources = [s for s in spec["contract_v2"]["sources"] if s["classification"] == "dsp_source"
                       and (repository is None or s["repository"] == repository)]
        row = features.setdefault(feature, {
            "feature_id": feature, "cases_total": 0, "pinned_citations": 0, "unpinned_citations": 0,
            **{name: [] for name in CATEGORIES}})
        row["cases_total"] += 1
        row[_category(sources)].append(case)
        row["pinned_citations"] += sum(1 for s in sources if s["revision"] is not None)
        row["unpinned_citations"] += sum(1 for s in sources if s["revision"] is None)

    rows = []
    for feature in sorted(features):
        row = features[feature]
        for name in CATEGORIES:
            row[name] = sorted(row[name])
        rows.append(row)
    totals = {"cases_total": sum(r["cases_total"] for r in rows),
              "pinned_citations": sum(r["pinned_citations"] for r in rows),
              "unpinned_citations": sum(r["unpinned_citations"] for r in rows),
              **{name: sum(len(r[name]) for r in rows) for name in CATEGORIES}}
    return {
        "schema_version": 1, "repository": repository, "features": rows, "totals": totals,
        "invalid_scenarios": sorted(invalid, key=lambda i: (str(i["feature_id"]), str(i["case_id"]))),
        "note": "A pin is a claim about a commit, not verification. Unpinned citations can only reach file-level "
                "impact matches (DIRECT_PATH).",
    }
