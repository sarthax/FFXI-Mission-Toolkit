"""Atomic diagnostic snapshot writer for trusted DSP-side instrumentation.

This is not a map-server probe: callers must supply verified runtime samples
from a server-owned read-only diagnostic hook, never SQL or client telemetry.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile

MAX_ENTITIES = 256
MAX_BYTES = 64 * 1024


def publish_snapshot(directory: Path, entities: list[dict]) -> Path:
    """Atomically replace one operator-controlled runtime diagnostics snapshot."""
    directory = Path(directory).resolve(strict=True)
    if not directory.is_dir() or directory.is_symlink():
        raise ValueError("Trusted diagnostic directory required")
    if not isinstance(entities, list) or len(entities) > MAX_ENTITIES:
        raise ValueError("Too many runtime entities")
    expected = {"source", "zone", "server_entity_id", "instance_id", "observed_at", "state"}
    for entity in entities:
        if not isinstance(entity, dict) or not expected.issubset(entity):
            raise ValueError("Incomplete server diagnostic entity")
        if entity["source"] != "server_runtime":
            raise ValueError("Client and index data cannot be published as runtime state")
    data = json.dumps({"producer": "server_diagnostic", "entities": entities},
                      separators=(",", ":"), allow_nan=False).encode("utf-8")
    if len(data) > MAX_BYTES:
        raise ValueError("Snapshot exceeds size limit")
    destination = directory / "entity_runtime_snapshot.json"
    if destination.is_symlink():
        raise ValueError("Refusing symlinked snapshot destination")
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=directory, prefix=".runtime-", suffix=".tmp",
                                         delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, destination)
        return destination
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
