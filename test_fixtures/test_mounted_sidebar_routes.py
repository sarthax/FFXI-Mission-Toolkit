#!/usr/bin/env python3
"""Verify real application route registration for documented sidebar destinations.

Inspects FastAPI routes after Workbench module integration, without requiring
server DB credentials or a running FFXI client. This is NOT a browser/render test.
"""
from __future__ import annotations

import json
import importlib.util
from pathlib import Path

# The full application host imports xi_tinkerer, an optional native wheel not
# installable from requirements.txt on the Linux regression runner. Explicitly
# record this as NOT RUN instead of pretending routes were verified.
if importlib.util.find_spec('xi_tinkerer') is None:
    print('Mounted sidebar GET route smoke: NOT RUN (xi_tinkerer native wheel unavailable)')
    raise SystemExit(0)

from workbench.app.host import app
from workbench.runtime.paths import REPO_ROOT


def main():
    routes = [r for r in app.routes if "GET" in (getattr(r, "methods", ()) or ())]
    paths = {r.path for r in routes}
    required = {
        "/domains/{key}",
        "/character-editor",
        "/zones/{zoneid}/view3d",
        "/live-client/replay/console",
        "/live-client/bridge/console",
        "/auction-house/help",
        "/synth",
        "/captures/review",
        "/tools/ws-calc",
        "/tools/melee-calc",
        "/tools/magic-calc",
        "/tools/heal-calc",
        "/tools/pet-calc",
    }
    missing = required - paths
    assert not missing, f"Missing mounted GET routes: {sorted(missing)}"

    shell = (Path(REPO_ROOT) / "src/workbench/gui_shell.py").read_text(encoding="utf-8")
    domain_keys = json.loads((Path(REPO_ROOT) / "src/workbench/domains/definitions.json").read_text(encoding="utf-8"))["domains"]
    for name in ("abyssea", "battlefields", "conflict", "combat", "dynamis", "escha", "hobbies", "helm", "events", "missions", "quests", "roe", "trust", "other"):
        assert name in domain_keys
        assert f'"href": "/domains/{name}' in shell
    print(f"Mounted sidebar GET route smoke: PASS ({len(required)} route patterns, {len(domain_keys)} domain definitions)")


if __name__ == "__main__":
    main()
