"""Read-only trusted server runtime provider contract.

The transport is injected by trusted server administration code, never supplied
directly by an Ashita client or user-controlled HTTP request.
"""
from __future__ import annotations

import time
from collections.abc import Callable, Mapping

from .entity_runtime_sample import classify_supplied_sample


class TrustedRuntimeProvider:
    """Bounded evidence consumer; does not discover servers or perform writes."""

    def __init__(self, read_server_entity: Callable[..., Mapping | None]):
        if not callable(read_server_entity):
            raise TypeError("read_server_entity must be callable")
        self._read = read_server_entity

    def inspect(self, *, zone: int, server_entity_id: int,
                instance_id: str, now: float | None = None) -> dict:
        if type(zone) is not int or not 0 <= zone <= 65535:
            raise ValueError("Invalid zone")
        if type(server_entity_id) is not int or not 0 <= server_entity_id <= 0xFFFFFFFF:
            raise ValueError("Invalid server entity ID")
        if not isinstance(instance_id, str) or not instance_id or len(instance_id) > 128:
            raise ValueError("Explicit server instance ID required")
        now = time.time() if now is None else now
        try:
            sample = self._read(zone=zone, server_entity_id=server_entity_id,
                                instance_id=instance_id)
        except (ConnectionError, OSError, TimeoutError):
            sample = None
        return classify_supplied_sample(
            zone=zone, server_entity_id=server_entity_id,
            instance_id=instance_id, now=now, sample=sample)
