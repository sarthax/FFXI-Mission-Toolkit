#!/usr/bin/env python3
"""Compatibility alias for packaged legacy read-only LLM database tools."""
from __future__ import annotations

import sys

from workbench.devtools.research.legacy_llm import db_tools as _canonical

sys.modules[__name__] = _canonical
