"""Strict read-only validation of externally supplied runtime entity evidence.

This does not connect to a live server.  A trusted operator must provide a
server-origin sample; client observations or static SQL rows are not runtime proof.
"""
from __future__ import annotations

import math
from collections.abc import Mapping

from .entity_runtime_evidence import classify_runtime_entity

MAX_SAMPLE_AGE = 5.0


def validate_runtime_sample(sample: Mapping, *, now: float,
                            zone: int, server_entity_id: int,
                            instance_id: str) -> dict:
    """Validate freshness and identity before passing evidence to classifier."""
    if not isinstance(sample, Mapping):
        raise ValueError("Runtime sample must be a mapping")
    if not isinstance(instance_id, str) or not instance_id or len(instance_id) > 128:
        raise ValueError("Instance ID is required")
    timestamp = sample.get("observed_at")
    if type(timestamp) not in (int, float) or not math.isfinite(timestamp):
        raise ValueError("Runtime sample timestamp missing or invalid")
    if not math.isfinite(now):
        raise ValueError("Invalid validation time")
    age = now - timestamp
    if age < 0 or age > MAX_SAMPLE_AGE:
        raise ValueError("Runtime sample is stale or from the future")
    if sample.get("source") != "server_runtime":
        raise ValueError("Runtime sample source is not server_runtime")
    if sample.get("zone") != zone or sample.get("server_entity_id") != server_entity_id:
        raise ValueError("Runtime sample entity/zone mismatch")
    if sample.get("instance_id") != instance_id:
        raise ValueError("Runtime sample instance mismatch")
    if sample.get("state") not in {"active", "despawned", "hidden", "inactive"}:
        raise ValueError("Runtime state unsupported")
    checked = dict(sample)
    checked["fresh"] = True
    return checked


def classify_supplied_sample(*, zone: int, server_entity_id: int,
                             instance_id: str, now: float,
                             sample: Mapping | None) -> dict:
    """Fail closed on invalid evidence; never promote untrusted data to state."""
    checked = None
    if sample is not None:
        try:
            checked = validate_runtime_sample(
                sample, now=now, zone=zone,
                server_entity_id=server_entity_id, instance_id=instance_id)
        except (ValueError, TypeError):
            pass
    return classify_runtime_entity(zone=zone, server_entity_id=server_entity_id,
                                   instance_id=instance_id, runtime_sample=checked)
