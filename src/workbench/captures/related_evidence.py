"""Canonical Capture related-evidence service."""
from __future__ import annotations

import sys
from workbench.captures import integrity as _integrity
from workbench.captures import _related_evidence_impl as _impl

_impl.capture_integrity = _integrity
sys.modules[__name__] = _impl
