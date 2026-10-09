"""Opt-in loopback listener tests, without starting FFXI or writing game state."""
import threading

import pytest

from workbench.runtime.live_client.bridge_handshake import make_hello
from workbench.runtime.live_client.bridge_listener import BridgeListener
from workbench.runtime.live_client.bridge_loopback import connect, send
from workbench.runtime.live_client.bridge_peers import LocalPeerRegistry, PeerIdentity
from workbench.runtime.live_client.bridge_protocol import BridgeEnvelope, BridgeKind, BridgeLane


def frame(identity, number, lane=BridgeLane.TELEMETRY):
    kind = BridgeKind.OBSERVATION if lane is BridgeLane.TELEMETRY else BridgeKind.CAPTURE_EVENT
    return BridgeEnvelope(1, lane, kind, identity.client_id, identity.session_id,
                          identity.generation, number, None, b'{}')


def submit(address, identity, token, messages):
    with connect(*address) as sock:
        sock.sendall(make_hello(identity, token))
        for message in messages:
            send(sock, message)


def test_listener_accepts_two_separate_authenticated_clients_and_lanes():
    peers = LocalPeerRegistry(ttl_seconds=30)
    a = PeerIdentity("client-a", "session-a", "gen-a")
    b = PeerIdentity("client-b", "session-b", "gen-b")
    ta = peers.issue(a, now=10)
    tb = peers.issue(b, now=10)
    with BridgeListener(peers) as listener:
        address = listener._server.getsockname()
        for identity, token, frames in (
            (a, ta, [frame(a, 1), frame(a, 1, BridgeLane.CAPTURE)]),
            (b, tb, [frame(b, 1)]),
        ):
            sender = threading.Thread(target=submit, args=(address, identity, token, frames))
            sender.start()
            assert listener.accept_batch(now=11) == frames
            sender.join(timeout=3)
            assert not sender.is_alive()
        assert listener.mailbox("client-a").pending(BridgeLane.CAPTURE) == 1
        assert listener.mailbox("client-b").pending(BridgeLane.TELEMETRY) == 1
        assert listener.mailbox("client-a").receive().lane is BridgeLane.TELEMETRY
    assert listener.mailbox("client-a") is None


def test_listener_rejects_wrong_token_and_does_not_queue_observation():
    peers = LocalPeerRegistry(ttl_seconds=30)
    identity = PeerIdentity("client", "session", "gen")
    peers.issue(identity, now=10)
    with BridgeListener(peers) as listener:
        sender = threading.Thread(target=submit, args=(listener._server.getsockname(), identity, "wrong", [frame(identity, 1)]))
        sender.start()
        with pytest.raises(PermissionError):
            listener.accept_batch(now=11)
        sender.join(timeout=3)
        assert listener.mailbox("client") is None


def test_listener_rejects_unstarted_or_duplicate_start():
    listener = BridgeListener(LocalPeerRegistry())
    with pytest.raises(RuntimeError):
        listener.accept_batch()
    listener.start()
    try:
        with pytest.raises(RuntimeError):
            listener.start()
    finally:
        listener.stop()
