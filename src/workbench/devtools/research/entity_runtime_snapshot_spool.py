"""Read-only adapter for an operator-controlled, server-produced diagnostic spool.

Not an authentication mechanism: only configure a directory writable by the
trusted server instrumentation, never by game clients or remote HTTP users.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Mapping

MAX_BYTES = 64 * 1024


class RuntimeSnapshotSpool:
    """Read one fixed diagnostics file; never execute a script or discover paths."""

    def __init__(self, directory: Path):
        directory = Path(directory).resolve(strict=True)
        if not directory.is_dir():
            raise ValueError("Runtime diagnostic spool must be a directory")
        self.directory = directory

    def __call__(self, *, zone: int, server_entity_id: int,
                 instance_id: str) -> Mapping | None:
        # One fixed filename for the trusted diagnostic producer, not a
        # user-derived path, to avoid traversal and untrusted lookup.
        path = self.directory / "entity_runtime_snapshot.json"
        if path.is_symlink() or not path.is_file():
            return None
        try:
            with path.open("rb") as handle:
                raw = handle.read(MAX_BYTES + 1)
            if len(raw) > MAX_BYTES:
                return None
            document = json.loads(raw)
        except (OSError, ValueError, UnicodeDecodeError):
            return None
        if not isinstance(document, dict):
            return None
        # Require a top-level producer marker. Marker alone is not provenance
        # authentication; OS-level permissions are the actual trust boundary.
        if document.get("producer") != "server_diagnostic":
            return None
        entries = document.get("entities")
        if not isinstance(entries, list) or len(entries) > 256:
            return None
        matches = [entry for entry in entries if isinstance(entry, dict)
                   and entry.get("zone") == zone
                   and entry.get("server_entity_id") == server_entity_id
                   and entry.get("instance_id") == instance_id]
        # Refuse ambiguous/conflicting runtime reports.
        return matches[0] if len(matches) == 1 else None
