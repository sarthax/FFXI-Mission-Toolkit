#!/usr/bin/env python3
"""Operator opt-in smoke for the *actual* Workbench app in a disposable checkout.

Default mode is preflight only: no workbench.app.host import, DB or network.
The real host initialises local SQLite/runtime state at import time, so --execute
requires an explicit acknowledgment and a Git checkout without existing DBs.
Do NOT run against the normal working Toolkit installation or its evidence.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UNSAFE_STATE = (
    "ffxi_zone_database.db", "workbench.db", ".openwebui_key",
    "data/live_client_bridge_state.json", ".env", "data/.env",
)
PAGE_PROBES = (
    ("/help", 200, "When a workflow does not produce the expected result"),
    ("/roadmap", 200, "Roadmap"),
    ("/feature-catalog", 200, 'id="operator-workflow-bindings"'),
    ("/features/trace?q=synthetic-missing-graph", 200,
     "Canonical Workbench graph is not available"),
    ("/features/trace/runtime.json?root=synthetic", 404,
     "Canonical Workbench graph is not available"),
    ("/live-client/bridge/console", 200, "Live dashboard"),
    ("/captures/review?status=pending&kind=synthetic-unmatched", 200,
     "Nothing here for this filter."),
    ("/captures/search?module=events&message_id=non-numeric", 422,
     "message_id must be an integer"),
)


def git_revision(root: Path) -> str | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"], capture_output=True,
            text=True, timeout=5, check=False,
        )
        value = result.stdout.strip()
        return value if result.returncode == 0 and re.fullmatch(r"[0-9a-f]{40}", value) else None
    except (OSError, subprocess.TimeoutExpired):
        return None


def sandbox_preflight(root: Path, *, native_present: bool | None = None) -> dict:
    """No runtime imports or writes. Never claim a root is disposable automatically."""
    root = root.resolve()
    if native_present is None:
        native_present = importlib.util.find_spec("xi_tinkerer") is not None
    marker = root / ".git"
    state = [item for item in UNSAFE_STATE if (root / item).exists()]
    return {
        "checkout_marker_present": marker.is_dir() or marker.is_file(),
        "native_wheel_available": bool(native_present),
        "state_blockers": state,
        "disposable_candidate": (marker.is_dir() or marker.is_file()) and not state,
    }


def _matches(app, method: str, path: str) -> bool:
    from starlette.routing import Match
    scope = {
        "type": "http", "path": path, "method": method,
        "root_path": "", "headers": [], "query_string": b"",
    }
    return any(route.matches(scope)[0] is Match.FULL for route in app.routes)


def route_registration(app, bindings: list[dict]) -> list[dict]:
    """Resolve method/path through actual app routes; never dispatch POST controls."""
    results = []
    for binding in bindings:
        original = binding["route"]
        concrete = re.sub(r"\{[^{}]+\}", "synthetic", original)
        matches = _matches(app, binding["method"], concrete)
        results.append({
            "workflow": binding["id"], "method": binding["method"],
            "route": original, "mounted": matches,
        })
    return results


def read_only_http(app, *, probes=PAGE_PROBES) -> list[dict]:
    """ASGI requests only; no server socket, scheduler lifespan or POST calls."""
    from fastapi.testclient import TestClient

    client = TestClient(app, raise_server_exceptions=False)
    outcomes = []
    for route, expected_status, text_marker in probes:
        try:
            response = client.get(route, follow_redirects=False)
            actual = response.status_code
            matched = text_marker in response.text
            outcomes.append({
                "route": route, "method": "GET",
                "expected_http": expected_status, "observed_http": actual,
                "marker_present": matched,
                "passed": actual == expected_status and matched,
            })
        except Exception as exc:
            outcomes.append({
                "route": route, "method": "GET",
                "expected_http": expected_status, "observed_http": None,
                "marker_present": False, "passed": False,
                "error_type": type(exc).__name__,
            })
    return outcomes


def evaluate(app, bindings: list[dict], *, probes=PAGE_PROBES) -> dict:
    mount = route_registration(app, bindings)
    http = read_only_http(app, probes=probes)
    return {
        "result": "PASS" if all(item["mounted"] for item in mount)
                    and all(item["passed"] for item in http) else "FAIL",
        "mounts": mount, "http": http,
        "lifespan_started": False,
        "synthetic_missing_graph": True,
        "no_post_dispatched": True,
    }


def _manifest(root: Path) -> list[dict]:
    payload = json.loads((root / "feature_catalog/operator_workflow_bindings.json").read_text(
        encoding="utf-8"))
    bindings = payload["cases"]
    if len(bindings) != 11 or len({row["id"] for row in bindings}) != 11:
        raise ValueError("Operator workflow binding manifest has unexpected shape")
    if any(row["method"] not in {"GET", "POST"} for row in bindings):
        raise ValueError("Unexpected operator workflow method")
    return bindings


def main(argv: list[str] | None = None, *, root: Path = ROOT) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true",
                        help="Import and probe the actual host; local disposable checkout ONLY")
    parser.add_argument("--ack-disposable-checkout", action="store_true",
                        help="Confirm the checkout is isolated and permitted to create empty runtime state")
    args = parser.parse_args(argv)
    preflight = sandbox_preflight(root)
    report = {
        "schema_version": 1,
        "case": "toolkit-full-host-operator-smoke",
        "observed_at_utc": datetime.now(timezone.utc).isoformat(),
        "revision": git_revision(root),
        "execution_scope": "full_host_read_only_requests" if args.execute else "preflight_only",
        "preflight": preflight,
        "result": "NOT_RUN", "reason": "",
        "limitations": ("No live client, DSP, Wiki import, gameplay or browser acceptance. "
                        "The real host may initialize *new* local SQLite and cache files. "
                        "Only run it in an operator-approved disposable checkout."),
    }
    if not args.execute:
        report["reason"] = "Preflight only; full host was not imported."
        print(json.dumps(report, sort_keys=True))
        return 0
    if not args.ack_disposable_checkout or not preflight["disposable_candidate"]:
        report["reason"] = "Refused: explicit disposable-checkout acknowledgment and clean checkout required."
        print(json.dumps(report, sort_keys=True))
        return 2
    if not preflight["native_wheel_available"]:
        report["reason"] = "NOT RUN: xi_tinkerer native wheel unavailable in this Python environment."
        print(json.dumps(report, sort_keys=True))
        return 2

    # Host import happens ONLY after all guards. Never invoke lifespan or start uvicorn.
    try:
        sys.path.insert(0, str(root / "src"))
        from workbench.app.host import app
        actual = evaluate(app, _manifest(root))
        report.update(actual)
        report["reason"] = ("Read-only route and HTTP probes completed in disposable checkout."
                            if actual["result"] == "PASS" else
                            "One or more mounted routes or HTTP probes failed.")
    except Exception as exc:
        report["result"] = "FAIL"
        report["reason"] = "Host import or probe error"
        report["error_type"] = type(exc).__name__
        # Do not include arbitrary exception messages: local paths or secrets may occur there.
    print(json.dumps(report, sort_keys=True))
    return 0 if report["result"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
