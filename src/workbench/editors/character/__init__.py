"""Character administration services for live FFXI server databases."""

from .actions import AddItemRequest, ActionPreview, preview_add_item
from .connection import DatabaseProfile, connect_from_server_root, discover_database_profile
from .factory import CharacterEditorContext, open_character_editor
from .inventory import CapabilityInventory, inventory_summary
from .schema import CharacterSchema, discover_character_schema
from .service import CharacterEditorService

# Register framework compatibility before State Surface imports the progression inspector.
# This leaves the LSB exact-definition path unchanged and adds DSP/Topaz legacy handler support.
from . import progression_compat as _progression_compat  # noqa: F401,E402

# Import for route-registration side effects. These modules attach APIs to the existing
# Character Editor subrouter, which gui.py subsequently mounts on the live application.
from . import server_profiles_gui as _server_profiles_gui  # noqa: F401,E402
from . import state_surface_gui as _state_surface_gui  # noqa: F401,E402
from . import client_cache_gui as _client_cache_gui  # noqa: F401,E402


def _attach_root_server_admin_routes() -> None:
    """Bridge packaged server-admin routes into the legacy root router registration.

    ``gui_server.py`` currently has no router registry: it imports the Character Editor router
    and mounts it directly on the root FastAPI app.  Appending already-built AH route objects
    here preserves their own ``/auction-house`` paths (rather than nesting them below
    ``/character-editor``) and avoids another edit point in the monolithic server.  This bridge
    can disappear once root router registration is moved into a shared registry.
    """
    from . import gui as _character_gui
    from workbench.server_admin.auction_house.gui import router as _auction_house_router

    existing = {(getattr(route, "path", None), tuple(sorted(getattr(route, "methods", ()) or ()))) for route in _character_gui.router.routes}
    for route in _auction_house_router.routes:
        key = (getattr(route, "path", None), tuple(sorted(getattr(route, "methods", ()) or ())))
        if key not in existing:
            _character_gui.router.routes.append(route)
            existing.add(key)


_attach_root_server_admin_routes()


__all__ = [
    "ActionPreview",
    "AddItemRequest",
    "CapabilityInventory",
    "CharacterEditorContext",
    "CharacterEditorService",
    "CharacterSchema",
    "DatabaseProfile",
    "connect_from_server_root",
    "discover_character_schema",
    "discover_database_profile",
    "inventory_summary",
    "open_character_editor",
    "preview_add_item",
]
