"""Canonical Capture lobby-stream ingestion service."""
from __future__ import annotations

import sys
from workbench.captures import _lobby_ingest_impl as _impl

sys.modules[__name__] = _impl
