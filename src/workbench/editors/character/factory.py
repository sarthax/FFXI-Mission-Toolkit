"""High-level Character Editor construction from a configured server checkout."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .adapters import detect_adapter
from .connection import DatabaseProfile, connect, discover_database_profile
from .schema import discover_character_schema
from .service import CharacterEditorService


@dataclass
class CharacterEditorContext:
    profile: DatabaseProfile
    adapter: Any
    service: CharacterEditorService

    def public_status(self) -> dict[str, Any]:
        return {
            "database": self.profile.public_dict(),
            "adapter": {
                "family": self.adapter.family,
                "confidence": self.adapter.confidence,
                "evidence": list(self.adapter.evidence),
            },
            "capabilities": self.service.capability_manifest(),
        }

    def close(self) -> None:
        try:
            self.service.connection.close()
        except Exception:
            pass


def open_character_editor(server_root: Path | str, **connect_kwargs) -> CharacterEditorContext:
    """Open a live Character Editor context for DSP, Topaz, or LSB.

    Detection uses both checkout markers and the connected live schema. Credentials remain
    internal to DatabaseProfile and are never included in public_status(). The resolved server
    root is attached to the service so lineage-local enum/catalog readers can use that exact
    checkout instead of a bundled/current-LSB fallback.
    """
    profile = discover_database_profile(server_root)
    connection = connect(profile, **connect_kwargs)
    try:
        schema = discover_character_schema(connection)
        adapter = detect_adapter(profile.server_root, schema)
        service = CharacterEditorService(
            connection,
            adapter_family=adapter.family,
            adapter_confidence=adapter.confidence,
        )
        service.server_root = profile.server_root
        return CharacterEditorContext(profile=profile, adapter=adapter, service=service)
    except Exception:
        connection.close()
        raise
