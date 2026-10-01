"""Compatibility alias for Capture raw packet ingestion services."""
from __future__ import annotations

import sys
from workbench.captures import raw_packet_ingest as _canonical

sys.modules[__name__] = _canonical
