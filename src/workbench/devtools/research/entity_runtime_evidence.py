"""Read-only, conservative runtime entity evidence classifier.

Indexed configuration and client observation are not server runtime telemetry.
Unknown is the default until an authoritative instance-scoped runtime adapter exists.
"""
from __future__ import annotations

from collections.abc import Mapping

RUNTIME_STATES = frozenset({"active", "despawned", "hidden", "inactive", "unknown"})


def classify_runtime_entity(*, zone: int, server_entity_id: int | None,
                            indexed_match: Mapping | None = None,
                            client_observation: Mapping | None = None,
                            runtime_sample: Mapping | None = None,
                            instance_id: str | None = None) -> dict:
    """Return source-qualified evidence without upgrading a map match to runtime proof.

    runtime_sample must explicitly declare source='server_runtime', an exact zone,
    entity ID and instance ID. Other samples cannot establish a runtime state.
    """
    if type(zone) is not int or not 0 <= zone <= 65535:
        raise ValueError("Invalid zone")
    if server_entity_id is not None and (
        type(server_entity_id) is not int or not 0 <= server_entity_id <= 0xFFFFFFFF
    ):
        raise ValueError("Invalid reported server entity ID")
    output = {
        "zone": zone,
        "server_entity_id": server_entity_id,
        "instance_id": instance_id,
        "runtime_status": "unknown",
        "confidence": "unverified",
        "runtime_source": None,
        "indexed_status": indexed_match.get("status") if indexed_match else "unavailable",
        "client_observed": bool(client_observation and client_observation.get("fresh") is True),
        "reason": "No authoritative instance-scoped runtime entity sample",
    }
    sample = runtime_sample
    if not isinstance(sample, Mapping) or server_entity_id is None or not instance_id:
        return output
    if (sample.get("source") != "server_runtime"
        or sample.get("zone") != zone
        or sample.get("server_entity_id") != server_entity_id
        or sample.get("instance_id") != instance_id
        or sample.get("fresh") is not True):
        return output
    state = sample.get("state")
    if state not in RUNTIME_STATES or state == "unknown":
        return output
    output.update({
        "runtime_status": state,
        "confidence": "runtime_reported",
        "runtime_source": "server_runtime",
        "reason": "Fresh instance-scoped server runtime evidence",
    })
    return output
