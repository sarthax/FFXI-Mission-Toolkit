"""Canonical Capture adapter for raw packet-source ingestion."""
from __future__ import annotations

import sys

from workbench.captures import integrity as _integrity
from workbench.captures import chat as _chat
from workbench.captures import _raw_packet_ingest_impl as _impl

_impl.capture_integrity = _integrity
_impl.capture_chat = _chat
sys.modules[__name__] = _impl
