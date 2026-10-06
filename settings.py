#!/usr/bin/env python3
"""Compatibility import for the canonical runtime settings store."""
from __future__ import annotations

import sys

from workbench.runtime import settings_store as _canonical

sys.modules[__name__] = _canonical
