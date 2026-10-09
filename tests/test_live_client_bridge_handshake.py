"""Socket-level authentication tests with explicit operator-issued tokens."""
import socket

import pytest

from workbench.runtime.live_client.bridge_handshake import accept_one, make_hello
from workbench.runtime.live_client.bridge_loopback import send
from workbench.runtime.live_client.bridge_peers import LocalPeerRegistry, PeerIdentity
from workbench.runtime.live_client.bridge_protocol import BridgeEnvelope, BridgeKind, BridgeLane


def observation(identity):
    return BridgeEnvelope(1, BridgeLane.TELEMETRY, BridgeKind.OBSERVATION,
                          identity.client_id, identity.session_id, identity.generation,
                          1, None, b'{}')


def exchange(registry, identity, token, message=None, now=10):
    left, right = socket.socketpair()
    try:
        left.sendall(make_hello(identity, token))
        send(left, message or observation(identity))
        return accept_one(right, registry, now=now)
    finally:
        left.close(); right.close()


def test_authenticated_peer_accepts_matching_client_observation():
    peers = LocalPeerRegistry(ttl_seconds=5)
    identity = PeerIdentity("client", "session", "generation")
    token = peers.issue(identity, now=10)
    assert exchange(peers, identity, token) == observation(identity)


def test_wrong_token_rejected_before_message_dispatch():
    peers = LocalPeerRegistry(ttl_seconds=5)
    identity = PeerIdentity("client", "session", "generation")
    peers.issue(identity, now=10)
    with pytest.raises(PermissionError, match="untrusted"):
        exchange(peers, identity, "wrong")


def test_generation_replacement_revokes_stale_socket_identity():
    peers = LocalPeerRegistry(ttl_seconds=5)
    old = PeerIdentity("client", "session", "generation")
    old_token = peers.issue(old, now=10)
    new = PeerIdentity("client", "new-session", "new-generation")
    peers.issue(new, now=11)
    with pytest.raises(PermissionError):
        exchange(peers, old, old_token, now=11)


def test_mismatched_frame_rejected_after_handshake():
    peers = LocalPeerRegistry(ttl_seconds=5)
    identity = PeerIdentity("client", "session", "generation")
    token = peers.issue(identity, now=10)
    with pytest.raises(PermissionError, match="identity changed"):
        exchange(peers, identity, token, observation(
            PeerIdentity("client-other", "session", "generation")))


def test_expired_lease_rejected():
    peers = LocalPeerRegistry(ttl_seconds=5)
    identity = PeerIdentity("client", "session", "generation")
    token = peers.issue(identity, now=10)
    with pytest.raises(PermissionError):
        exchange(peers, identity, token, now=15)


def test_incomplete_handshake_fails_closed():
    peers = LocalPeerRegistry()
    left, right = socket.socketpair()
    try:
        left.sendall(bytes((0, 5)) + b'bad')
        left.close()
        with pytest.raises(ConnectionError):
            accept_one(right, peers)
    finally:
        left.close(); right.close()
