"""Canonical Capture graph-connect adapter.

The mature implementation is staged losslessly in ``_graph_connect_impl``. This adapter binds
Capture-owned packet identity/correlation dependencies directly, then exposes the implementation
module itself so existing monkeypatch/private-helper behavior remains unchanged during Phase C.
"""
from __future__ import annotations

import sys

from workbench.captures import packet_correlation, packet_identity
from workbench.captures.correlation import _graph_connect_impl as _impl

_impl.packet_node_id = packet_identity.packet_node_id
_impl.packet_correlation = packet_correlation

sys.modules[__name__] = _impl
