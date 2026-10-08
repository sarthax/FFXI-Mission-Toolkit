"""Fail-closed executable verification contract tests; no process access."""
import hashlib
from pathlib import Path
from tempfile import TemporaryDirectory
import pytest

from workbench.runtime.live_client.windows_identity import (
    VerifiedClientBuild, verify_client_executable,
)


def test_explicit_known_digest_only():
    with TemporaryDirectory() as directory:
        binary = Path(directory) / "test.exe"
        binary.write_bytes(b"fixture executable")
        digest = hashlib.sha256(binary.read_bytes()).hexdigest()
        allowed = (VerifiedClientBuild(digest, "test fixture"),)
        assert verify_client_executable(binary, allowed).label == "test fixture"
        with pytest.raises(PermissionError):
            verify_client_executable(binary, ())
        with pytest.raises(ValueError):
            verify_client_executable(binary, allowed, max_bytes=2)


def test_invalid_manifest_digest_and_filename():
    with pytest.raises(ValueError):
        VerifiedClientBuild("placeholder", "unverified")
    with TemporaryDirectory() as directory:
        binary = Path(directory) / "not-executable.txt"
        binary.write_bytes(b"fixture")
        with pytest.raises(ValueError):
            verify_client_executable(binary, ())
