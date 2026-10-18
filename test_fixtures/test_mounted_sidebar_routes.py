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

import re

from starlette.routing import Match

from workbench.app.host import app
from workbench.runtime.paths import REPO_ROOT


def _mounted_get(path_pattern):
    """True if the mounted app resolves a GET for this pattern.

    Newer FastAPI keeps include_router() results as lazy _IncludedRouter entries in app.routes, so a flat
    scan of route.path misses every router-mounted page. Resolve a concrete request path through each
    top-level route's own matcher instead (works for both flat and included routes).
    """
    concrete = re.sub(r"\{[^}]+\}", "1", path_pattern)
    scope = {"type": "http", "path": concrete, "method": "GET", "root_path": "", "headers": [], "query_string": b""}
    return any(r.matches(scope)[0] == Match.FULL for r in app.routes)


def _render_get(path):
    """Dispatch one GET straight into the ASGI app (no httpx dependency) -> (status, body bytes)."""
    import asyncio
    scope = {"type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1", "method": "GET", "scheme": "http",
             "path": path, "raw_path": path.encode(), "root_path": "", "query_string": b"",
             "headers": [(b"host", b"127.0.0.1:8420")], "client": ("127.0.0.1", 1), "server": ("127.0.0.1", 8420)}
    out = {"status": 0, "body": b""}

    async def run():
        sent = False

        async def receive():
            nonlocal sent
            if not sent:
                sent = True
                return {"type": "http.request", "body": b"", "more_body": False}
            await asyncio.sleep(3600)

        async def send(m):
            if m["type"] == "http.response.start":
                out["status"] = m["status"]
            elif m["type"] == "http.response.body":
                out["body"] += m.get("body", b"")

        await asyncio.wait_for(app(scope, receive, send), 60)

    asyncio.run(run())
    return out["status"], out["body"]


def main():
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
    missing = {p for p in required if not _mounted_get(p)}
    assert not missing, f"Missing mounted GET routes: {sorted(missing)}"

    shell = (Path(REPO_ROOT) / "src/workbench/gui_shell.py").read_text(encoding="utf-8")
    domain_keys = json.loads((Path(REPO_ROOT) / "src/workbench/domains/definitions.json").read_text(encoding="utf-8"))["domains"]
    for name in ("abyssea", "battlefields", "conflict", "combat", "dynamis", "escha", "hobbies", "helm", "events", "missions", "quests", "roe", "trust", "other"):
        assert name in domain_keys
        assert f'"href": "/domains/{name}' in shell
    # Template-global regression: these pages import host template globals (current_theme) from the packaged host.
    for page in ("/synth", "/auction-house/help"):
        status, body = _render_get(page)
        assert status == 200, f"{page} rendered {status}: {body[:120]!r}"
    print(f"Mounted sidebar GET route smoke: PASS ({len(required)} route patterns, {len(domain_keys)} domain definitions)")


if __name__ == "__main__":
    main()
