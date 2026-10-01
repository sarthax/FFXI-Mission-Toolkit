#!/usr/bin/env python3
"""Compatibility entry point for the canonical Capture graph-connect service."""
from workbench.captures.correlation.graph_connect import *  # noqa: F401,F403

if __name__ == "__main__":
    raise SystemExit(main())
