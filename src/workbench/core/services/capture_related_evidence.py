"""Compatibility alias for the Capture-owned related-evidence service."""
from __future__ import annotations

import sys
from workbench.captures import related_evidence as _impl

sys.modules[__name__] = _impl
