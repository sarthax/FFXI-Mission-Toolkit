#!/usr/bin/env python3
"""Compatibility entry point for the packaged NPC index builder."""
from __future__ import annotations

import sys

from workbench.devtools.indexing import build_npc_index as _canonical

sys.modules[__name__] = _canonical

if __name__ == "__main__":
    _canonical.main()
