"""Static feature documentation audit. Findings are review queues, never runtime verdicts."""
from __future__ import annotations

from pathlib import Path
from workbench.core.services.feature_catalog import ROOT, load_catalog
from workbench.core.services.feature_catalog_gui_inventory import inventory_gui


def audit_documentation(root: Path = ROOT) -> dict:
    features = load_catalog(root / "feature_catalog/features.json")
    gui = inventory_gui(root)
    findings: list[dict] = []
    for feature in features:
        reasons = []
        if not feature.get("source_refs"):
            reasons.append("source_mapping_missing")
        if not feature.get("test_refs"):
            reasons.append("test_mapping_missing")
        for field in ("purpose", "how_to_use", "caveat"):
            value = feature.get(field, "")
            if not isinstance(value, str) or not value.strip():
                reasons.append(field + "_missing")
            elif value.strip() == feature.get("summary", "").strip():
                reasons.append(field + "_duplicates_summary")
        if reasons:
            findings.append({
                "feature_id": feature["id"], "module": feature["module"],
                "reasons": reasons, "priority": (
                    "high" if any(x.endswith("_missing") and not x.endswith("mapping_missing")
                                  for x in reasons) else "review"
                ),
            })
    candidates = []
    for page in gui["pages"]:
        # Controls are literal static candidates, not automatically missing functions.
        # No assertion of an undocumented behavior is made until human source review.
        for control in page["controls"]:
            candidates.append({
                "module": page["module"], "template": page["template"],
                "kind": control["kind"], "label": control["label"],
                "target": control["target"], "classification": "needs_review",
            })
    return {
        "stage": "static_triage",
        "features_checked": len(features),
        "findings": findings,
        "finding_count": len(findings),
        "control_candidates": candidates,
        "control_candidate_count": len(candidates),
        "truncated_templates": sorted(p["template"] for p in gui["pages"] if p["truncated"]),
        "limitations": (
            "Static source and catalog checks only. Controls are review candidates, not "
            "confirmed missing functions. Jinja branches, handler behavior and live runtime "
            "acceptance require separate review."
        ),
    }
