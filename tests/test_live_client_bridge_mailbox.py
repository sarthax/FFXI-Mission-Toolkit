"""Synthetic local broker tests; no real client IO or game writes."""
from dataclasses import replace

import pytest

from workbench.runtime.live_client.bridge_protocol import BridgeEnvelope, BridgeKind, BridgeLane, match_response
from workbench.runtime.live_client.bridge_mailbox import BridgeMailbox, SimulatedBridgeClient


def message(lane, sequence, *, kind=None, client="client-a", generation="generation-1"):
    if kind is None:
        kind = {BridgeLane.CONTROL: BridgeKind.COMMAND,
                BridgeLane.TELEMETRY: BridgeKind.OBSERVATION,
                BridgeLane.CAPTURE: BridgeKind.CAPTURE_EVENT}[lane]
    return BridgeEnvelope(1, lane, kind, client, "session-a", generation, sequence,
                          "req-1" if kind in (BridgeKind.COMMAND, BridgeKind.ACK, BridgeKind.REJECT) else None,
                          b"{}")


def test_capture_overload_does_not_delay_control_and_preserves_drop_count():
    mailbox = BridgeMailbox("client-a", "session-a", "generation-1",
                            control_limit=2, telemetry_limit=1, capture_limit=2)
    assert mailbox.submit(message(BridgeLane.CAPTURE, 1))
    assert mailbox.submit(message(BridgeLane.CAPTURE, 2))
    assert mailbox.submit(message(BridgeLane.CAPTURE, 3)) is False
    mailbox.submit(message(BridgeLane.TELEMETRY, 1))
    command = message(BridgeLane.CONTROL, 1)
    mailbox.submit(command)
    assert mailbox.capture_dropped == 1
    assert [mailbox.receive().lane for _ in range(4)] == [
        BridgeLane.CONTROL, BridgeLane.TELEMETRY,
        BridgeLane.CAPTURE, BridgeLane.CAPTURE,
    ]
    assert mailbox.receive() is None
    response = SimulatedBridgeClient(mailbox).respond(command, 2)
    assert response.kind is BridgeKind.REJECT
    assert match_response(command, response)
    assert b"writes_not_supported" in response.payload


def test_isolation_monotonic_sequence_and_full_control_fail_closed():
    box = BridgeMailbox("client-a", "session-a", "generation-1", control_limit=1)
    box.submit(message(BridgeLane.CONTROL, 1))
    with pytest.raises(BufferError):
        box.submit(message(BridgeLane.CONTROL, 2))
    with pytest.raises(ValueError, match="nonmonotonic"):
        box.submit(message(BridgeLane.CONTROL, 1))
    with pytest.raises(ValueError, match="generation"):
        box.submit(message(BridgeLane.CAPTURE, 1, generation="generation-2"))
    with pytest.raises(ValueError, match="generation"):
        box.submit(message(BridgeLane.CAPTURE, 1, client="client-b"))
    assert box.receive().sequence == 1
    box.submit(message(BridgeLane.CONTROL, 2))


def test_simulated_rejection_cannot_impersonate_another_client():
    box = BridgeMailbox("client-a", "session-a", "generation-1")
    with pytest.raises(ValueError, match="invalid simulated command response"):
        SimulatedBridgeClient(box).respond(message(BridgeLane.CONTROL, 1, client="client-b"), 2)
    with pytest.raises(ValueError, match="expected control"):
        SimulatedBridgeClient(box).respond(message(BridgeLane.CAPTURE, 1), 2)


@pytest.mark.parametrize("limit", [0, -1, True, 4097])
def test_invalid_queue_capacity_rejected(limit):
    with pytest.raises(ValueError):
        BridgeMailbox("client-a", "session-a", "generation-1", capture_limit=limit)
