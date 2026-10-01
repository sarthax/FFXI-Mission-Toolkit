#!/usr/bin/env python3
"""Compatibility launcher for the canonical Salvage reconstruction Capture CLI."""
from __future__ import annotations

import sys
from workbench.captures.cli import salvage_reconstruct as _canonical

if __name__ == "__main__":
    raise SystemExit(_canonical.main())

sys.modules[__name__] = _canonical
