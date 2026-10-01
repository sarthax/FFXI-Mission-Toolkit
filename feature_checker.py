#!/usr/bin/env python3
"""Compatibility entry point for the canonical Development Feature Checker service.

New code must import from ``workbench.devtools.features.checker``. This root wrapper remains only
for the monolithic ``gui_server.py`` caller until that GUI import surface is migrated in its own
bounded slice.
"""
from workbench.devtools.features.checker import *  # noqa: F401,F403

if __name__ == "__main__":
    from workbench.devtools.features.checker import main
    raise SystemExit(main())