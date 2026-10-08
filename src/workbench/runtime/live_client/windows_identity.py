"""Fail-closed Windows client identity manifest for future read-only adapters.

Only explicitly registered, verified binary digests are eligible. A filename,
reported version or PID alone never establishes compatibility.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path


@dataclass(frozen=True)
class VerifiedClientBuild:
    sha256: str
    label: str

    def __post_init__(self) -> None:
        if len(self.sha256) != 64 or any(ch not in "0123456789abcdef" for ch in self.sha256):
            raise ValueError("expected lowercase SHA-256 digest")
        if not self.label.strip():
            raise ValueError("build label required")


def verify_client_executable(path: Path, builds: tuple[VerifiedClientBuild, ...],
                             *, max_bytes: int = 128 * 1024 * 1024) -> VerifiedClientBuild:
    """Hash a specifically selected executable, without attaching to any process."""
    path = Path(path)
    if not path.is_file() or not path.name.lower().endswith(".exe"):
        raise ValueError("select an existing Windows executable")
    if not 0 < path.stat().st_size <= max_bytes:
        raise ValueError("executable outside bounded size limit")
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    match = next((build for build in builds if build.sha256 == digest.hexdigest()), None)
    if match is None:
        raise PermissionError("unverified client build: refuse memory adapter connection")
    return match
