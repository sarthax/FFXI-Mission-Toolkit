"""Persistent authenticated bridge stream regression tests, no game writes."""
import socket
import pytest
from workbench.runtime.live_client.bridge_handshake import make_hello, receive_session
from workbench.runtime.live_client.bridge_loopback import send
from workbench.runtime.live_client.bridge_peers import LocalPeerRegistry, PeerIdentity
from workbench.runtime.live_client.bridge_protocol import BridgeEnvelope, BridgeLane, BridgeKind


def msg(identity, seq, lane=BridgeLane.TELEMETRY):
    kind = BridgeKind.OBSERVATION if lane is BridgeLane.TELEMETRY else BridgeKind.CAPTURE_EVENT
    return BridgeEnvelope(1, lane, kind, identity.client_id, identity.session_id,
                          identity.generation, seq, None, b'{}')


def setup():
    peers = LocalPeerRegistry(ttl_seconds=30)
    identity = PeerIdentity("one", "session", "gen")
    token = peers.issue(identity, now=10)
    return peers, identity, token


def test_multiple_lanes_one_authenticated_stream_and_clean_eof():
    peers, identity, token = setup()
    left, right = socket.socketpair()
    try:
        left.sendall(make_hello(identity, token))
        messages = [msg(identity, 1), msg(identity, 1, BridgeLane.CAPTURE), msg(identity, 2)]
        for item in messages:
            send(left, item)
        left.shutdown(socket.SHUT_WR)
        assert receive_session(right, peers, now=11) == messages
    finally:
        left.close(); right.close()


def test_cross_client_and_repeated_sequence_rejected():
    peers, identity, token = setup()
    for second in (msg(PeerIdentity("other", "session", "gen"), 2), msg(identity, 1)):
        left, right = socket.socketpair()
        try:
            left.sendall(make_hello(identity, token))
            send(left, msg(identity, 1))
            send(left, second)
            left.shutdown(socket.SHUT_WR)
            with pytest.raises((PermissionError, ValueError)):
                receive_session(right, peers, now=11)
        finally:
            left.close(); right.close()


def test_incomplete_second_frame_rejects_partial_batch():
    peers, identity, token = setup()
    left, right = socket.socketpair()
    try:
        left.sendall(make_hello(identity, token))
        send(left, msg(identity, 1))
        left.sendall(b'\\x00')
        left.shutdown(socket.SHUT_WR)
        with pytest.raises(ConnectionError):
            receive_session(right, peers, now=11)
    finally:
        left.close(); right.close()


def test_explicit_frame_limit_prevents_unbounded_receive():
    peers, identity, token = setup()
    left, right = socket.socketpair()
    try:
        left.sendall(make_hello(identity, token))
        send(left, msg(identity, 1))
        assert receive_session(right, peers, max_messages=1, now=11) == [msg(identity, 1)]
    finally:
        left.close(); right.close()
