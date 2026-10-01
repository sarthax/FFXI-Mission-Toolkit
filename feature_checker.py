#!/usr/bin/env python3
"""Compatibility entry point for the canonical Feature Checker service.

New code must import from ``workbench.core.services.feature_checker``. This root wrapper remains
only for the monolithic ``gui_server.py`` caller until that GUI import surface is migrated in its
own bounded slice.
"""
from workbench.core.services.feature_checker import *  # noqa: F401,F403

if __name__ == "__main__":
    from workbench.core.services.feature_checker import main
    raise SystemExit(main())
