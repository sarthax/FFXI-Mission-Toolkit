#!/usr/bin/env python3
"""Compatibility entry point for the packaged zone top-down cache builder."""
from __future__ import annotations

import sys

from workbench.devtools.spatial import build_topdown as _canonical

sys.modules[__name__] = _canonical

if __name__ == "__main__":
    _canonical.main()
