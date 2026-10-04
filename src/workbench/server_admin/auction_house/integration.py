"""Temporary integration bridge for the legacy monolithic GUI server.

The modern server-admin module owns its routes and navigation metadata here. The bridge can be
removed once ``gui_server.py`` gains a root router registry and the shell consumes module-owned
workspace contributions directly.
"""
from __future__ import annotations

from fastapi import APIRouter


def install_legacy_gui_bridge(root_router: APIRouter) -> None:
    """Expose AH at root paths and add it to the Server workspace exactly once."""
    from workbench import gui_shell

    from .gui import router as auction_house_router

    existing_routes = {
        (getattr(route, "path", None), tuple(sorted(getattr(route, "methods", ()) or ())))
        for route in root_router.routes
    }
    for route in auction_house_router.routes:
        key = (getattr(route, "path", None), tuple(sorted(getattr(route, "methods", ()) or ())))
        if key not in existing_routes:
            # Deliberately append the already-rooted route object. Calling include_router() on the
            # Character Editor carrier would incorrectly prepend /character-editor.
            root_router.routes.append(route)
            existing_routes.add(key)

    workspaces = []
    for workspace in gui_shell.WORKSPACES:
        if workspace.get("name") != "Server":
            workspaces.append(workspace)
            continue
        sections = list(workspace.get("sections", ()))
        if not any(section.get("href") == "/auction-house" for section in sections):
            insert_at = next(
                (index + 1 for index, section in enumerate(sections) if section.get("href") == "/character-editor"),
                len(sections),
            )
            sections.insert(insert_at, {"label": "Auction House", "href": "/auction-house"})
        updated = dict(workspace)
        updated["sections"] = tuple(sections)
        workspaces.append(updated)
    gui_shell.WORKSPACES = tuple(workspaces)

    # The shell's approved route map predates this modular route, so teach its runtime owner
    # resolver about the new workspace without editing the large shared route-map file in this
    # feature branch. Keep the wrapper idempotent because Character imports occur in many tests.
    current_owner = gui_shell.route_owner
    if not getattr(current_owner, "_auction_house_bridge", False):
        def _route_owner(path: str, method: str = "GET") -> dict:
            if method.upper() == "GET" and (path == "/auction-house" or path.startswith("/auction-house/")):
                return {
                    "home": "Server",
                    "section": "Auction House",
                    "path": "/auction-house",
                    "method": "GET",
                    "role": "page",
                    "disposition": "KEEP",
                }
            return current_owner(path, method)

        _route_owner._auction_house_bridge = True  # type: ignore[attr-defined]
        gui_shell.route_owner = _route_owner
