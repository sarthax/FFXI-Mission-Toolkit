#!/usr/bin/env python3
"""Compatibility alias for packaged legacy LLM call logging."""
from __future__ import annotations

import sys

from workbench.devtools.research.legacy_llm import log as _canonical

sys.modules[__name__] = _canonical
