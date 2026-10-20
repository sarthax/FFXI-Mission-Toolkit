"""Curated static operator UI-to-handler crosswalk; no route execution or live acceptance.

Only literal source evidence is checked. Dynamic JavaScript/Jinja, request guards and
delegated helper behavior require separate runtime/negative-path validation.
"""
from __future__ import annotations

import ast
import json
import re
from pathlib import Path
from workbench.core.services.feature_catalog import ROOT, load_catalog

FORM = re.compile(r"<form\b[^>]*>[\s\S]*?</form\s*>", re.I)
LINK = re.compile(r"<a\b[^>]*>", re.I)
ATTR = re.compile(r"""\b([\w-]+)=["']([^"']*)["']""")


def _source(root: Path, relative: str) -> str:
    path = Path(relative)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError("Unsafe workflow source path")
    file = root / path
    return file.read_text(encoding="utf-8") if file.is_file() else ""


def inspect_ui_binding(template: str, case: dict) -> bool:
    """Check that a curated literal control occurs in the expected UI element."""
    marker, route = case["control_marker"], case["route"]
    kind, method = case["kind"], case["method"].lower()
    if kind == "form":
        for form in FORM.findall(template):
            tag = form.split(">", 1)[0] + ">"
            attrs = dict(ATTR.findall(tag))
            if (marker in form and attrs.get("method", "get").lower() == method
                    and attrs.get("action") == route):
                return True
        return False
    if kind == "link" and method == "get":
        for anchor in LINK.findall(template):
            attrs = dict(ATTR.findall(anchor))
            if marker in anchor and attrs.get("href", "").split("?", 1)[0].split("#", 1)[0] == route:
                return True
        return False
    if kind == "js_fetch":
        # This verifies explicit source snippets, not a live JS event-to-HTTP invocation.
        return marker in template and all(m in template for m in case.get("support_markers", []))
    return False


def inspect_route_binding(handler_source: str, case: dict) -> tuple[bool, str]:
    """Resolve named app or router decorator, including nested router factories."""
    try:
        module = ast.parse(handler_source)
    except SyntaxError:
        return False, ""
    nodes = module.body
    prefix = case.get("router_prefix", "")
    if case.get("handler_parent"):
        parents = [x for x in nodes if isinstance(x, (ast.FunctionDef, ast.AsyncFunctionDef))
                   and x.name == case["handler_parent"]]
        if len(parents) != 1:
            return False, ""
        parent = parents[0]
        if not any(
            isinstance(x, ast.Assign) and
            any(isinstance(t, ast.Name) and t.id == "router" for t in x.targets)
            and isinstance(x.value, ast.Call)
            and isinstance(x.value.func, ast.Name) and x.value.func.id == "APIRouter"
            and any(k.arg == "prefix" and isinstance(k.value, ast.Constant)
                    and k.value.value == prefix for k in x.value.keywords)
            for x in parent.body
        ):
            return False, ""
        nodes = parent.body
    elif prefix:
        return False, ""

    functions = [x for x in nodes if isinstance(x, (ast.FunctionDef, ast.AsyncFunctionDef))
                 and x.name == case["handler_name"]]
    if len(functions) != 1:
        return False, ""
    fn = functions[0]
    expected = case["route"]
    if not expected.startswith(prefix):
        return False, ""
    local_route = expected[len(prefix):]
    namespace = "router" if prefix else "app"
    matched = any(
        isinstance(deco, ast.Call) and isinstance(deco.func, ast.Attribute)
        and deco.func.attr == case["method"].lower()
        and isinstance(deco.func.value, ast.Name) and deco.func.value.id == namespace
        and bool(deco.args) and isinstance(deco.args[0], ast.Constant)
        and deco.args[0].value == local_route
        for deco in fn.decorator_list
    )
    return matched, ast.get_source_segment(handler_source, fn) or ""



def inspect_guard_helper_source(handler_source: str, case: dict, name: str) -> str:
    """Resolve a reviewed helper in the handler's immediate Python lexical scope."""
    try:
        module = ast.parse(handler_source)
    except SyntaxError:
        return ""
    nodes = module.body
    if case.get("handler_parent"):
        parents = [n for n in nodes if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                   and n.name == case["handler_parent"]]
        if len(parents) != 1:
            return ""
        nodes = parents[0].body
    matches = [n for n in nodes if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
               and n.name == name]
    if len(matches) != 1:
        return ""
    return ast.get_source_segment(handler_source, matches[0]) or ""


def audit_workflow_bindings(root: Path = ROOT) -> dict:
    curated = json.loads(_source(root, "feature_catalog/operator_workflow_bindings.json"))
    if curated.get("schema_version") != 1 or not isinstance(curated.get("cases"), list):
        raise ValueError("Invalid operator workflow contract set")
    features = {row["id"] for row in load_catalog(root / "feature_catalog/features.json")}
    seen: set[str] = set()
    seen_failure_ids: set[str] = set()
    source_cache: dict[str, str] = {}
    cases = []
    for item in curated["cases"]:
        if item["id"] in seen or item["feature_id"] not in features:
            raise ValueError("Duplicate operator workflow or unknown capability")
        seen.add(item["id"])
        if item["kind"] not in {"form", "link", "js_fetch"} or item["method"] not in {"GET", "POST"}:
            raise ValueError("Invalid operator workflow method/kind")
        if item["boundary"] not in {
            "read_only_research", "read_only_telemetry", "local_browser_read",
            "starts_background_job", "guarded_local_settings_write", "creates_export_artifact"
        }:
            raise ValueError("Unrecognized operator workflow safety boundary")
        if not item.get("handler_markers") or not item.get("interpretation"):
            raise ValueError("Incomplete operator workflow evidence")
        def read(path: str) -> str:
            if path not in source_cache:
                source_cache[path] = _source(root, path)
            return source_cache[path]

        template = read(item["template"])
        handler = read(item["handler_file"])
        ui_found = inspect_ui_binding(template, item)
        route_found, function_text = inspect_route_binding(handler, item)
        missing_handler_markers = [m for m in item["handler_markers"] if m not in function_text]
        helper = item.get("helper")
        helper_found = True
        if helper:
            helper_text = read(helper["file"])
            helper_found = (helper["call"] in function_text and
                            re.search(r"^def " + re.escape(helper["name"]) + r"\(",
                                      helper_text, re.M) is not None)
        failures = []
        for failure in item.get("failure_paths", []):
            if (failure.get("id") in seen_failure_ids or
                    failure.get("state") not in {
                        "blocked", "guarded", "invalid_input", "pending", "empty_or_ambiguous"
                    } or not failure.get("label") or not failure.get("signal") or
                    not failure.get("recovery") or not failure.get("handler_markers")):
                raise ValueError("Invalid or duplicate operator failure path")
            seen_failure_ids.add(failure["id"])
            missing = [marker for marker in failure["handler_markers"]
                       if marker not in function_text]
            guard = failure.get("guard_helper")
            missing_guard = []
            if guard:
                if not guard.get("name") or not guard.get("markers"):
                    raise ValueError("Incomplete failure guard source evidence")
                guard_text = inspect_guard_helper_source(handler, item, guard["name"])
                missing_guard = [marker for marker in guard["markers"] if marker not in guard_text]
            failures.append({
                **failure, "missing_handler_markers": missing,
                "missing_guard_markers": missing_guard,
                "source_verified": bool(route_found and not missing and not missing_guard),
                "verification": "static_handler_branch_only_runtime_unverified",
            })
        if not failures:
            raise ValueError("Operator workflow requires reviewed failure or degraded states")
        failure_sources_verified = all(f["source_verified"] for f in failures)
        cases.append({
            **item, "failure_paths": failures, "failure_sources_verified": failure_sources_verified,
            "ui_found": ui_found, "route_found": route_found,
            "missing_handler_markers": missing_handler_markers, "helper_found": helper_found,
            "source_verified": (ui_found and route_found and not missing_handler_markers
                                and helper_found and failure_sources_verified),
            "verification": "static_source_only_runtime_unverified",
        })
    return {
        "case_count": len(cases), "cases": cases,
        "failure_count": sum(len(c["failure_paths"]) for c in cases),
        "failure_source_drift": [
            f["id"] for c in cases for f in c["failure_paths"] if not f["source_verified"]
        ],
        "missing": [c["id"] for c in cases if not c["source_verified"]],
        "boundary_counts": {
            boundary: sum(c["boundary"] == boundary for c in cases)
            for boundary in sorted({c["boundary"] for c in cases})
        },
        "limitations": "Literal form/link/fetch evidence and bound Python handlers only. "
                       "Failure and degraded-state signals are handler-local static branch evidence, "
                       "not exercised HTTP error paths. JavaScript/Jinja, external jobs, "
                       "permissions, DB state and client/server acceptance remain unverified.",
    }
