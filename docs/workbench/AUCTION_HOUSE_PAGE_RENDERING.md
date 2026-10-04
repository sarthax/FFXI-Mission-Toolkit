# Auction House page rendering integration

The Auction House router owns its own `Jinja2Templates` environment. The legacy GUI host configures shared `base.html` helpers such as `current_theme`, `shell_context`, `backport_enabled`, review helpers, and other globals only after modular routers are imported.

Character Editor was explicitly synchronized by `gui_server.py`; Auction House was not. As a result, `/auction-house` could return HTTP 500 during Jinja rendering before any Auction House database request executed.

The Auction House page now synchronizes the already-running host template globals immediately before rendering. The lookup is lazy and supports both `gui_server` import mode and direct `python gui_server.py` execution (`__main__`). This keeps standalone router imports/tests free of a circular dependency while preserving the shared application shell.

This change affects HTML rendering only. Auction House database reads, previews, write-readiness checks, and the disabled write executor are unchanged.
