import pytest
from workbench.runtime.live_client.bridge_mailbox import BridgeMailbox
from workbench.runtime.live_client.bridge_protocol import BridgeKind
from workbench.runtime.live_client.movement_control import ControlIdentity, MovementControlGate, Position

def fixture():
    box = BridgeMailbox("ashita-a", "session-a", "gen-1")
    gate = MovementControlGate(box, 235)
    identity = ControlIdentity("ashita-a", "session-a", "gen-1", 235)
    gate.observe(identity, Position(1, 2, 3), now=10)
    return gate, identity

def test_only_explicit_simulation_is_allowed():
    gate, identity = fixture()
    with pytest.raises(PermissionError):
        gate.simulate_nudge(identity, Position(2, 2, 3), "first", now=10.1)
    with pytest.raises(ValueError):
        gate.arm_simulation(explicit_consent=False)
    gate.arm_simulation(explicit_consent=True)
    reply = gate.simulate_nudge(identity, Position(2, 2, 3), "second", now=10.1)
    assert reply.kind is BridgeKind.REJECT
    assert b"writes_not_supported" in reply.payload
    with pytest.raises(ValueError):
        gate.simulate_nudge(identity, Position(99, 2, 3), "far", now=10.2)

def test_stale_identity_and_stop_disarm():
    gate, identity = fixture()
    gate.arm_simulation(explicit_consent=True)
    with pytest.raises(PermissionError):
        gate.simulate_nudge(identity, Position(1, 2, 3), "expired", now=20)
    assert not gate.armed
    gate.observe(identity, Position(1, 2, 3), now=21)
    gate.arm_simulation(explicit_consent=True)
    with pytest.raises(PermissionError):
        gate.simulate_nudge(ControlIdentity("ashita-b", "session-a", "gen-1", 235), Position(1, 2, 3), "wrong", now=21.1)
    assert not gate.armed
    gate.arm_simulation(explicit_consent=True)
    gate.stop()
    assert not gate.armed

def test_reject_nonfinite_target_and_invalid_zones():
    with pytest.raises(ValueError):
        Position(float("nan"), 1, 2)
    with pytest.raises(ValueError):
        Position(True, 1, 2)
    with pytest.raises(ValueError):
        ControlIdentity("a", "b", "c", 0)
