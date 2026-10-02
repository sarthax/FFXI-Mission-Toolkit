"""Compatibility import alias for Client zone animation metadata."""
from __future__ import annotations

import sys

from workbench.client.models import zone_animation_meta as _canonical

sys.modules[__name__] = _canonical
