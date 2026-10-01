#!/usr/bin/env python3
"""Compatibility entry point for the canonical Feature Checker service.

New code should import from ``workbench.core.services.feature_checker``. This root wrapper remains
only while historical tests, research helpers, and operator workflows still import or invoke
``feature_checker.py`` directly.
"""
from workbench.core.services.feature_checker import *  # noqa: F401,F403

if __name__ == "__main__":
    from workbench.core.services.feature_checker import main
    raise SystemExit(main())
