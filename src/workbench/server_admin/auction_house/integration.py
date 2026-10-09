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
    from workbench.server_admin.voidwatch.api import router as voidwatch_router

    from .activity_api import router as auction_house_activity_router
    from .admin_buy_api import router as auction_house_admin_buy_router
    from .batch_api import router as auction_house_batch_router
    from .cleanup_api import router as auction_house_cleanup_router
    from .console_api import router as auction_house_console_router
    from .buyer_api import router as auction_house_buyer_router
    from .arbitrage_api import router as auction_house_arbitrage_router
    from .intel_api import router as auction_house_intel_router
    from .economy_api import router as auction_house_economy_router
    from .gui import router as auction_house_router
    from .legacy_test_api import router as auction_house_test_write_router
    from .listing_api import router as auction_house_listing_router
    from .player_listing_api import router as auction_house_player_listing_router
    from .player_purchase_api import router as auction_house_player_purchase_router
    from .preset_api import router as auction_house_preset_api_router
    from .preset_ui import router as auction_house_preset_ui_router
    from .reward_api import router as auction_house_reward_api_router
    from .reward_history_api import router as auction_house_reward_history_api_router
    from .reward_history_ui import router as auction_house_reward_history_ui_router
    from .reward_ui import router as auction_house_reward_ui_router
    from .seeder_ui import router as auction_house_seeder_ui_router
    from .status_ui import router as auction_house_status_router
    from workbench.server_admin.synth.api import router as synth_router
    from .synthetic_seed_api import router as auction_house_synthetic_seed_router

    existing_routes = {
        (getattr(route, "path", None), tuple(sorted(getattr(route, "methods", ()) or ())))
        for route in root_router.routes
    }
    for carrier in (
        auction_house_router,
        auction_house_test_write_router,
        auction_house_listing_router,
        auction_house_admin_buy_router,
        auction_house_player_purchase_router,
        auction_house_player_listing_router,
        auction_house_batch_router,
        auction_house_synthetic_seed_router,
        auction_house_seeder_ui_router,
        auction_house_cleanup_router,
        auction_house_console_router,
        auction_house_buyer_router,
        auction_house_arbitrage_router,
        auction_house_intel_router,
        auction_house_preset_api_router,
        auction_house_preset_ui_router,
        auction_house_economy_router,
        auction_house_reward_api_router,
        auction_house_reward_ui_router,
        auction_house_reward_history_api_router,
        auction_house_reward_history_ui_router,
        auction_house_activity_router,
        auction_house_status_router,
        synth_router,
        voidwatch_router,
    ):
        for route in carrier.routes:
            key = (getattr(route, "path", None), tuple(sorted(getattr(route, "methods", ()) or ())))
            if key not in existing_routes:
                root_router.routes.append(route)
                existing_routes.add(key)

    workspaces = []
    for workspace in gui_shell.WORKSPACES:
        if workspace.get("name") != "Server":
            workspaces.append(workspace)
            continue
        sections = list(workspace.get("sections", ()))
        # One sidebar entry: every AH tool lives inside the console hub at /auction-house.
        if not any(section.get("href") == "/auction-house" for section in sections):
            insert_at = next(
                (index + 1 for index, section in enumerate(sections) if section.get("href") == "/character-editor"),
                len(sections),
            )
            sections.insert(insert_at, {"label": "Auction House", "href": "/auction-house"})
        if not any(section.get("href") == "/synth" for section in sections):
            ah_at = next((index + 1 for index, section in enumerate(sections) if section.get("href") == "/auction-house"), len(sections))
            sections.insert(ah_at, {"label": "Synth & Crafting", "href": "/synth"})
        updated = dict(workspace)
        updated["sections"] = tuple(sections)
        workspaces.append(updated)
    gui_shell.WORKSPACES = tuple(workspaces)

    current_owner = gui_shell.route_owner
    if not getattr(current_owner, "_auction_house_bridge", False):
        def _route_owner(path: str, method: str = "GET") -> dict:
            if path == "/auction-house" or path.startswith("/auction-house/"):
                return {
                    "home": "Server",
                    "section": "Auction House",
                    "path": "/auction-house",
                    "method": method.upper(),
                    "role": "page" if method.upper() == "GET" else "action",
                    "disposition": "KEEP",
                }
            if path == "/synth" or path.startswith("/synth/"):
                return {"home": "Server", "section": "Synth & Crafting", "path": "/synth", "method": method.upper(),
                        "role": "page" if method.upper() == "GET" else "action", "disposition": "KEEP"}
            return current_owner(path, method)

        _route_owner._auction_house_bridge = True  # type: ignore[attr-defined]
        gui_shell.route_owner = _route_owner
