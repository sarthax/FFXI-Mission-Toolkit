#!/usr/bin/env python3
"""Compatibility entry point for the canonical Development Feature Trace service."""
from workbench.devtools.features.trace import *  # noqa: F401,F403

if __name__ == "__main__":
    raise SystemExit(main())
