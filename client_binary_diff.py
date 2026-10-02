#!/usr/bin/env python3
"""Compatibility launcher for the packaged Client binary diff CLI."""
from __future__ import annotations
import sys
from workbench.client.cli import binary_diff as _canonical

if __name__ == "__main__":
    raise SystemExit(_canonical.main())

sys.modules[__name__] = _canonical
