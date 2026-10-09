"""Accepted bridge traffic refreshes the same lease without rotating secrets."""
import json
import socket

import pytest

from workbench.runtime.live_client.bridge_handshake import make_hello, receive_session
from workbench.runtime.live_client.bridge_loopback import send
from workbench.runtime.live_client.bridge_peers import LocalPeerRegistry, PeerIdentity
from workbench.runtime.live_client.bridge_protocol import BridgeEnvelope, BridgeKind, BridgeLane


def _deliver(registry, identity, token, *, now, valid=True):
    left, right = socket.socketpair()
    try:
        left.sendall(make_hello(identity, token))
        payload = {"schema_version": 1, "client_id": identity.client_id,
                   "client_version": "unverified-ashita-v4-api",
                   "character": "Test", "adapter": "ashita-v4-api-experimental",
                   "observed_at": now,
                   "position": {"zone_id": 100, "x": 0, "y": 0, "z": 0, "heading": 0},
                   "entities": []}
        lane = BridgeLane.TELEMETRY if valid else BridgeLane.CONTROL
        kind = BridgeKind.OBSERVATION if valid else BridgeKind.COMMAND
        envelope = BridgeEnvelope(1, lane, kind, identity.client_id,
                                  identity.session_id, identity.generation,
                                  1, "probe" if not valid else None, json.dumps(payload).encode())
        send(left, envelope)
        left.shutdown(socket.SHUT_WR)
        return receive_session(right, registry, now=now)
    finally:
        left.close()
        right.close()


def test_accepted_bridge_telemetry_extends_same_token_lease():
    registry = LocalPeerRegistry(ttl_seconds=10)
    identity = PeerIdentity("ashita-a", "session", "generation")
    token = registry.issue(identity, now=0)
    assert len(_deliver(registry, identity, token, now=9)) == 1
    assert registry.authenticate(identity, token, now=18)
    assert not registry.authenticate(identity, token, now=19)
    assert len(_deliver(registry, identity, token, now=18)) == 1
    assert registry.authenticate(identity, token, now=27)


def test_rejected_control_message_cannot_renew_lease():
    registry = LocalPeerRegistry(ttl_seconds=10)
    identity = PeerIdentity("ashita-a", "session", "generation")
    token = registry.issue(identity, now=0)
    with pytest.raises(PermissionError):
        _deliver(registry, identity, token, now=9, valid=False)
    assert not registry.authenticate(identity, token, now=10)


def test_expired_lease_cannot_be_revived_by_late_traffic():
    registry = LocalPeerRegistry(ttl_seconds=10)
    identity = PeerIdentity("ashita-a", "session", "generation")
    token = registry.issue(identity, now=0)
    with pytest.raises(PermissionError):
        _deliver(registry, identity, token, now=11)
    assert not registry.authenticate(identity, token, now=11)
