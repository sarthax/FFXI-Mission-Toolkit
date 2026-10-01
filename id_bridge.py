#!/usr/bin/env python3
"""Compatibility CLI for the canonical ID Bridge service.

Implementation lives in ``workbench.core.services.id_bridge``. This root entry point is retained
because the documented operator workflow still uses commands such as ``python id_bridge.py ...``.
"""
from workbench.core.services.id_bridge import *  # noqa: F401,F403


if __name__ == "__main__":
    from workbench.core.services.id_bridge import main

    raise SystemExit(main())
