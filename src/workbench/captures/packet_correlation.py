"""Canonical Capture adapter for cross-source packet correlation."""
from __future__ import annotations

from workbench.captures import timeline_alignment as _timeline_alignment
from workbench.captures.packet_identity import canonical_opcode as _canonical_opcode
from workbench.captures import _packet_correlation_impl as _impl

_impl.ta = _timeline_alignment
_impl.canonical_opcode = _canonical_opcode

for _name in dir(_impl):
    if not _name.startswith("__"):
        globals()[_name] = getattr(_impl, _name)

ta = _timeline_alignment
canonical_opcode = _canonical_opcode
