#!/usr/bin/env python3
"""Compatibility entry point for the canonical Capture backtrace service."""
from workbench.captures.correlation.backtrace import *  # noqa: F401,F403

if __name__ == "__main__":
    raise SystemExit(main())
