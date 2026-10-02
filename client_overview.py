"""Compatibility import for Client build/snapshot overview services.

Canonical implementation: ``workbench.client.snapshots.overview``.
"""
from __future__ import annotations

import sys
from workbench.client.snapshots import overview as _canonical

sys.modules[__name__] = _canonical
