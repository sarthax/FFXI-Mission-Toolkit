#!/usr/bin/env python3
"""Compatibility entry point for the canonical dialog drift overview service."""
from __future__ import annotations

import sys
from workbench.devtools.reference.dialog import drift_overview as _canonical

sys.modules[__name__] = _canonical
