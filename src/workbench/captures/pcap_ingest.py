"""Canonical Capture PCAP/PCAPNG ingestion service."""
from __future__ import annotations

import sys
from workbench.captures import integrity as _integrity
from workbench.captures import raw_packet_ingest as _raw_packet_ingest
from workbench.captures import lobby_ingest as _lobby_ingest
from workbench.captures import _pcap_ingest_impl as _impl

_impl.capture_integrity = _integrity
_impl.raw_packet_ingest = _raw_packet_ingest
_impl.lobby_ingest = _lobby_ingest

sys.modules[__name__] = _impl
