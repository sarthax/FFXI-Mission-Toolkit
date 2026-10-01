"""Shared cross-component contracts for the modular Workbench architecture."""

from .providers import (
    CaptureEvidenceProvider,
    ClientEvidenceProvider,
    DevelopmentEvidenceProvider,
    EvidenceRecord,
    ReferenceEvidenceProvider,
)

__all__ = [
    "CaptureEvidenceProvider",
    "ClientEvidenceProvider",
    "DevelopmentEvidenceProvider",
    "EvidenceRecord",
    "ReferenceEvidenceProvider",
]
