#!/usr/bin/env python3
"""Compatibility launcher for the canonical dialog drift audit."""
from __future__ import annotations

import sys
from workbench.reference.dialog import audit_drift as _canonical

if __name__ == "__main__":
    raise SystemExit(_canonical.main())

sys.modules[__name__] = _canonical
