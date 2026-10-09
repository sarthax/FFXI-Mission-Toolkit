"""Decode live bridge observations with the existing strict telemetry contract.

This is a read-only handoff; no capture database or game writes. Source labels
must match the authenticated envelope, not merely the untrusted JSON payload.
"""
from __future__ import annotations

import json

from .bridge_protocol import BridgeEnvelope, BridgeKind, BridgeLane
from .telemetry import TelemetryFrame, decode_frame


def decode_bridge_telemetry(message: BridgeEnvelope) -> TelemetryFrame:
    if message.lane is not BridgeLane.TELEMETRY or message.kind is not BridgeKind.OBSERVATION:
        raise ValueError("not a bridge telemetry observation")
    try:
        raw = json.loads(message.payload.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("invalid bridge telemetry JSON") from exc
    if not isinstance(raw, dict):
        raise ValueError("invalid bridge telemetry payload")
    if raw.get("client_id") != message.client_id:
        raise ValueError("bridge telemetry client identity mismatch")
    return decode_frame(raw)


def validated_telemetry_batch(messages: list[BridgeEnvelope]) -> tuple[TelemetryFrame, ...]:
    """Validate the full batch before exposing any observation to consumers."""
    if not isinstance(messages, list):
        raise ValueError("invalid bridge observation batch")
    if len(messages) > 4096:
        raise ValueError("bridge observation batch too large")
    return tuple(decode_bridge_telemetry(message) for message in messages)
