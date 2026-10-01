"""Compatibility alias for the Capture-owned lobby ingestion service."""
from __future__ import annotations

import sys
from workbench.captures import lobby_ingest as _impl

sys.modules[__name__] = _impl
