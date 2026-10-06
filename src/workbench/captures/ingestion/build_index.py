"""Canonical Capture ingestion entry point for the historical build_capture_index module.

The mature ingestion implementation is staged unchanged in ``_build_index_impl``. This adapter
keeps its mutable module globals/private helpers intact while rebinding cross-component
dependencies and repository paths to their canonical package owners.
"""
from __future__ import annotations

import sys

from workbench.captures import chat as capture_chat
from workbench.captures import integrity as capture_integrity
from workbench.captures import pcap_ingest
from workbench.captures import raw_packet_ingest
from workbench.devtools.entities import profile as entity_profile
from workbench.runtime.paths import DATABASE_PATH, REPO_ROOT

# The staged implementation still imports the historical root name during module initialization.
# Supply the canonical Development module so editable-install imports work outside repository cwd.
sys.modules.setdefault("entity_profile", entity_profile)

from . import _build_index_impl as _impl

_impl.entity_profile = entity_profile
_impl.capture_integrity = capture_integrity
_impl.raw_packet_ingest = raw_packet_ingest
_impl.capture_chat = capture_chat
_impl.pcap_ingest = pcap_ingest
_impl.TOOLS_ROOT = REPO_ROOT
_impl.DB_PATH = DATABASE_PATH


def _run_cli() -> int:
    result = _impl.main()
    return int(result or 0)


if __name__ == "__main__":
    raise SystemExit(_run_cli())
else:
    # Preserve module identity so existing callers that monkeypatch DB_PATH/private helpers continue
    # to mutate the globals used by the implementation functions themselves.
    sys.modules[__name__] = _impl
