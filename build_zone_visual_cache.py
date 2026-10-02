#!/usr/bin/env python3
"""Compatibility entry point for the packaged zone visual-cache builder."""
from __future__ import annotations

import sys

from workbench.devtools.spatial import build_visual_cache as _canonical

sys.modules[__name__] = _canonical

if __name__ == "__main__":
    _canonical.main()
