#!/usr/bin/env python3
"""Compatibility launcher for Validation engine-change indexing."""
from __future__ import annotations
import sys
from workbench.validation.environments import engine_change_index as _canonical

if __name__ == "__main__":
    raise SystemExit(_canonical.main())

sys.modules[__name__] = _canonical
