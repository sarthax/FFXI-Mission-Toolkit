"""Static feature documentation audit. Findings are review queues, never runtime verdicts."""
from __future__ import annotations

from pathlib import Path
import json
import ast


def inspect_handler_source(source: str, handler_name: str, route_marker: str,
                           markers: list[str]) -> dict:
    """Bind the literal route decorator to the named top-level handler.

    Delegated/module-wide symbol matches are not direct handler evidence.
    """
    result = {"route_bound": False, "handler_source_markers": [],
              "module_only_source_markers": [], "missing_source_markers": []}
    try:
        module = ast.parse(source)
    except SyntaxError:
        result["missing_source_markers"] = list(markers)
        return result
    handlers = [node for node in module.body
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                and node.name == handler_name]
    if len(handlers) != 1 or not route_marker.startswith("@"):
        result["missing_source_markers"] = list(markers)
        return result
    handler = handlers[0]
    expected_decorator = route_marker[1:]
    result["route_bound"] = any(
        expected_decorator in (ast.get_source_segment(source, decorator) or "")
        for decorator in handler.decorator_list
    )
    body = ast.get_source_segment(source, handler) or ""
    result["handler_source_markers"] = [marker for marker in markers if marker in body]
    result["module_only_source_markers"] = [
        marker for marker in markers if marker not in body and marker in source
    ]
    result["missing_source_markers"] = [
        marker for marker in markers if marker not in source
    ]
    return result


from workbench.core.services.feature_catalog import ROOT, load_catalog
from workbench.core.services.feature_catalog_gui_inventory import inventory_gui


def audit_documentation(root: Path = ROOT) -> dict:
    features = load_catalog(root / "feature_catalog/features.json")
    gui = inventory_gui(root)
    curated = json.loads((root / "feature_catalog/documentation_review_cases.json").read_text(encoding="utf-8"))
    if curated.get("schema_version") != 1 or not isinstance(curated.get("cases"), list):
        raise ValueError("invalid documentation review cases")
    reviewed = []
    known = {item["id"]: item for item in features}
    seen = set()
    for case in curated["cases"]:
        if case["id"] in seen or case["feature_id"] not in known:
            raise ValueError("duplicate review case or unknown capability")
        seen.add(case["id"])
        relative = Path(case["template"])
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("unsafe review template path")
        template = root / relative
        present = template.is_file() and case["marker"] in template.read_text(encoding="utf-8")
        if case["status"] != "handler_source_verified_runtime_unverified":
            raise ValueError("unsupported review status")
        handler_relative = Path(case["handler_file"])
        if handler_relative.is_absolute() or ".." in handler_relative.parts:
            raise ValueError("unsafe handler source path")
        handler = root / handler_relative
        handler_source = handler.read_text(encoding="utf-8") if handler.is_file() else ""
        contract = case.get("contract", {})
        if (contract.get("method") not in {"GET", "POST"}
                or contract.get("boundary") not in {
                    "read_only_review", "read_only_history", "design_only",
                    "conversion_preview", "conversion_with_index_reads",
                    "guarded_execution_enqueue", "guarded_package_materialization",
                    "guarded_scope_write", "read_only_preview", "guarded_reward_execution"
                } or not isinstance(contract.get("inputs"), list) or not contract.get("outputs")
                or not contract.get("error_evidence")):
            raise ValueError("incomplete or unsupported source behavior contract")
        # Symbol checks are drift guards, not a parser or a proof of successful execution.
        contract_markers = [case["handler_marker"]] + case.get("contract_source_markers", [
            ('"' + name + '"') for name in contract["outputs"]
            if name != "build_plan"
        ])
        evidence = inspect_handler_source(
            handler_source, case["handler_name"], case["handler_marker"], contract_markers
        )
        handler_present = (evidence["route_bound"] and
                           ("." + contract["method"].lower() + "(") in case["handler_marker"])
        contract_source_present = not evidence["missing_source_markers"]
        checks = case.get("documentation_checks", [])
        if not isinstance(checks, list) or not checks:
            raise ValueError("missing documentation checks")
        discrepancies = []
        for check in checks:
            field, term = check.get("field"), check.get("term")
            if field not in ("purpose", "how_to_use", "caveat") or not isinstance(term, str) or not term.strip():
                raise ValueError("invalid documentation check")
            if term.casefold() not in known[case["feature_id"]].get(field, "").casefold():
                discrepancies.append({"field": field, "expected_term": term,
                                      "kind": "documentation_review_needed"})
        reviewed.append({**case, **evidence, "documentation_discrepancies": discrepancies,
                         "template_marker_present": present,
                         "handler_marker_present": handler_present,
                         "contract_source_present": contract_source_present,
                         "catalog_route": known[case["feature_id"]]["route"]})

    lifecycle_data = json.loads((root / "feature_catalog/reward_delivery_lifecycle.json").read_text(encoding="utf-8"))
    if lifecycle_data.get("schema_version") != 1 or not lifecycle_data.get("stages"):
        raise ValueError("invalid reward delivery lifecycle")
    lifecycle_stages = []
    for stage in lifecycle_data["stages"]:
        source_path = Path(stage["file"])
        if source_path.is_absolute() or ".." in source_path.parts:
            raise ValueError("unsafe reward lifecycle source path")
        source = root / source_path
        source_text = source.read_text(encoding="utf-8") if source.is_file() else ""
        lifecycle_stages.append({**stage, "source_markers_present": all(
            marker in source_text for marker in stage["markers"]
        )})

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
        "stage": "source_review",
        "reward_lifecycle": lifecycle_stages,
        "reward_lifecycle_missing_markers": [x["state"] for x in lifecycle_stages if not x["source_markers_present"]],
        "review_cases": reviewed,
        "review_case_count": len(reviewed),
        "review_case_delegated_markers": {
            case["id"]: case["module_only_source_markers"] for case in reviewed
            if case["module_only_source_markers"]
        },
        "documentation_discrepancy_count": sum(len(row["documentation_discrepancies"]) for row in reviewed),
        "review_case_missing_markers": [case["id"] for case in reviewed if not case["template_marker_present"] or not case["handler_marker_present"] or not case["contract_source_present"]],
        "features_checked": len(features),
        "findings": findings,
        "finding_count": len(findings),
        "control_candidates": candidates,
        "control_candidate_count": len(candidates),
        "truncated_templates": sorted(p["template"] for p in gui["pages"] if p["truncated"]),
        "limitations": (
            "Static source/catalog checks and curated template observations only. Controls are review candidates, not "
            "confirmed missing functions. Named HTTP decorators are checked on their actual "
            "functions, but module-level helper evidence is not direct handler evidence. "
            "Jinja branches, handler behavior and live runtime "
            "acceptance require separate review."
        ),
    }
