#!/usr/bin/env python3
"""Compatibility launcher and alias for the packaged legacy local LLM client."""
from __future__ import annotations

import sys

from workbench.devtools.research.legacy_llm import client as _canonical

if __name__ == "__main__":
    raise SystemExit(_canonical.main())

sys.modules[__name__] = _canonical
