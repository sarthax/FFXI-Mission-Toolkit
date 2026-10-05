"""Canonical Capture PCAP/PCAPNG ingestion service."""
from __future__ import annotations

import sys
from workbench.captures import integrity as _integrity
from workbench.captures import raw_packet_ingest as _raw_packet_ingest
from workbench.captures import lobby_ingest as _lobby_ingest
from workbench.captures import protocol_metadata as _protocol_metadata
from workbench.captures import _pcap_ingest_impl as _impl

_impl.capture_integrity = _integrity
_impl.raw_packet_ingest = _raw_packet_ingest
_impl.lobby_ingest = _lobby_ingest

_original_ingest_pcap = _impl.ingest_pcap


def _ingest_pcap_with_protocol_metadata(con, capture_id, src, relname):
    result = _original_ingest_pcap(con, capture_id, src, relname)
    _protocol_metadata.refresh_source_flow_metadata(con, capture_id, relname)
    return result


_impl.ingest_pcap = _ingest_pcap_with_protocol_metadata

sys.modules[__name__] = _impl
