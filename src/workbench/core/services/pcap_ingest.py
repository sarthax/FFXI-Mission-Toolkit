"""Compatibility alias for the Capture-owned PCAP/PCAPNG ingestion service."""
from __future__ import annotations

import sys
from workbench.captures import pcap_ingest as _impl

sys.modules[__name__] = _impl
