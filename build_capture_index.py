#!/usr/bin/env python3
"""Compatibility entry point for the canonical Capture index ingestion module."""
from __future__ import annotations

import sys

from workbench.captures.ingestion import build_index as _canonical

if __name__ == "__main__":
    raise SystemExit(_canonical.main())

# Preserve historical module-global monkeypatch behavior for imported callers/tests.
sys.modules[__name__] = _canonical
