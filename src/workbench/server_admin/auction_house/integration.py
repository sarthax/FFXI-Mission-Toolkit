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

    from .activity_api import router as auction_house_activity_router
    from .admin_buy_api import router as auction_house_admin_buy_router
    from .batch_api import router as auction_house_batch_router
    from .cleanup_api import router as auction_house_cleanup_router
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
        auction_house_preset_api_router,
        auction_house_preset_ui_router,
        auction_house_economy_router,
        auction_house_reward_api_router,
        auction_house_reward_ui_router,
        auction_house_reward_history_api_router,
        auction_house_reward_history_ui_router,
        auction_house_activity_router,
        auction_house_status_router,
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
        ordered = (
            ("Auction House", "/auction-house", "/character-editor"),
            ("AH Listing Manager", "/auction-house/listing-manager", "/auction-house"),
            ("AH Seeder", "/auction-house/seeder", "/auction-house/listing-manager"),
            ("AH Cleanup", "/auction-house/cleanup", "/auction-house/seeder"),
            ("AH Presets", "/auction-house/presets", "/auction-house/cleanup"),
            ("AH Economy", "/auction-house/economy", "/auction-house/presets"),
            ("AH Rewards", "/auction-house/rewards", "/auction-house/economy"),
            ("AH Reward History", "/auction-house/reward-history", "/auction-house/rewards"),
            ("AH Activity", "/auction-house/activity", "/auction-house/reward-history"),
            ("AH Help / Status", "/auction-house/help", "/auction-house/activity"),
        )
        for label, href, after_href in ordered:
            if any(section.get("href") == href for section in sections):
                continue
            insert_at = next(
                (index + 1 for index, section in enumerate(sections) if section.get("href") == after_href),
                len(sections),
            )
            sections.insert(insert_at, {"label": label, "href": href})
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
            return current_owner(path, method)

        _route_owner._auction_house_bridge = True  # type: ignore[attr-defined]
        gui_shell.route_owner = _route_owner
