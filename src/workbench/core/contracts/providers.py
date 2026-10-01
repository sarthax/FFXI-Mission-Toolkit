"""Protocol contracts for evidence exchange between Workbench components.

These contracts are deliberately data-oriented. Product components may implement them,
but Core must not import product implementations.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol, Sequence, runtime_checkable


@dataclass(frozen=True)
class EvidenceRecord:
    """Small cross-component evidence envelope."""

    evidence_id: str
    kind: str
    source: str
    subject: str
    payload: Mapping[str, Any] = field(default_factory=dict)
    confidence: str | None = None


@runtime_checkable
class CaptureEvidenceProvider(Protocol):
    def evidence_for(self, subject: str) -> Sequence[EvidenceRecord]: ...


@runtime_checkable
class ClientEvidenceProvider(Protocol):
    def evidence_for(self, subject: str) -> Sequence[EvidenceRecord]: ...


@runtime_checkable
class DevelopmentEvidenceProvider(Protocol):
    def evidence_for(self, subject: str) -> Sequence[EvidenceRecord]: ...


@runtime_checkable
class ReferenceEvidenceProvider(Protocol):
    def evidence_for(self, subject: str) -> Sequence[EvidenceRecord]: ...
