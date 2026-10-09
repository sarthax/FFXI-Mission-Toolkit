"""Bridge telemetry reuses the existing source validator without game IO."""
import json
from dataclasses import replace

import pytest

from workbench.runtime.live_client.bridge_protocol import BridgeEnvelope, BridgeKind, BridgeLane
from workbench.runtime.live_client.bridge_telemetry import decode_bridge_telemetry, validated_telemetry_batch


def message(client="client-a", *, payload=None):
    row = {"schema_version": 1, "client_id": client, "client_version": "unverified",
           "character": "Hero", "adapter": "ashita-v4-api-experimental",
           "observed_at": 100,
           "position": {"zone_id": 100, "x": 1, "y": 2, "z": 3, "heading": 0.5},
           "entities": []}
    return BridgeEnvelope(1, BridgeLane.TELEMETRY, BridgeKind.OBSERVATION,
                          "client-a", "session", "generation", 1, None,
                          json.dumps(row if payload is None else payload).encode())


def test_authenticated_bridge_observation_decodes_into_existing_frame():
    frame = decode_bridge_telemetry(message())
    assert frame.snapshot.client_id == "client-a"
    assert frame.snapshot.position.zone_id == 100
    assert frame.snapshot.position.heading == .5


def test_untrusted_client_identity_and_invalid_frame_fail_closed():
    with pytest.raises(ValueError, match="identity mismatch"):
        decode_bridge_telemetry(message("client-b"))
    bad = message(payload={"schema_version": 1, "client_id": "client-a"})
    with pytest.raises(KeyError):
        decode_bridge_telemetry(bad)
    with pytest.raises(ValueError, match="not a bridge telemetry"):
        decode_bridge_telemetry(replace(message(), lane=BridgeLane.CAPTURE,
                                        kind=BridgeKind.CAPTURE_EVENT))


def test_batch_validation_never_returns_partial_results():
    good = message()
    bad = message("other")
    with pytest.raises(ValueError):
        validated_telemetry_batch([good, bad])
    assert len(validated_telemetry_batch([good])) == 1
