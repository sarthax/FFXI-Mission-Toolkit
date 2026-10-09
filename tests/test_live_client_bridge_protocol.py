"""Fail-closed protocol invariants before any live IO is enabled."""
from dataclasses import replace

import pytest

from workbench.runtime.live_client.bridge_protocol import (
    BridgeEnvelope, BridgeKind, BridgeLane, lane_priority, match_response,
)


def envelope(kind=BridgeKind.COMMAND, lane=BridgeLane.CONTROL, **changes):
    data = dict(schema_version=1, lane=lane, kind=kind, client_id="client-a",
                session_id="session-a", generation="generation-1", sequence=1,
                request_id="req-1" if kind in (BridgeKind.COMMAND, BridgeKind.ACK, BridgeKind.REJECT) else None,
                payload=b"{}")
    data.update(changes)
    return BridgeEnvelope(**data)


def test_control_response_is_bound_to_generation_client_session_and_request():
    request = envelope()
    response = envelope(BridgeKind.ACK, sequence=2)
    assert match_response(request, response)
    assert match_response(request, envelope(BridgeKind.REJECT, sequence=2))
    for field, value in (("client_id", "client-b"), ("session_id", "session-b"),
                         ("generation", "generation-2"), ("request_id", "req-2"), ("sequence", 1)):
        assert not match_response(request, replace(response, **{field: value}))
    assert not match_response(request, envelope(BridgeKind.CAPTURE_EVENT, BridgeLane.CAPTURE, sequence=2))


@pytest.mark.parametrize("changes", [
    {"schema_version": 2}, {"schema_version": True},
    {"lane": BridgeLane.CAPTURE}, {"kind": BridgeKind.OBSERVATION},
    {"client_id": "../invalid"}, {"generation": ""}, {"sequence": -1},
    {"sequence": True}, {"request_id": None}, {"payload": "not bytes"},
    {"payload": b"x" * (64 * 1024 + 1)},
])
def test_invalid_commands_fail_closed(changes):
    with pytest.raises(ValueError):
        envelope(**changes)


def test_capture_and_telemetry_have_distinct_bounded_lanes():
    capture = envelope(BridgeKind.CAPTURE_EVENT, BridgeLane.CAPTURE, sequence=10)
    observation = envelope(BridgeKind.OBSERVATION, BridgeLane.TELEMETRY, sequence=11)
    assert capture.request_id is None and observation.request_id is None
    assert lane_priority(BridgeLane.CONTROL) < lane_priority(BridgeLane.TELEMETRY) < lane_priority(BridgeLane.CAPTURE)
    with pytest.raises(ValueError):
        replace(capture, request_id="req-1")
