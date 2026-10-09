"""Full simulated TCP to read-only Live Client feed; no Ashita/game writes."""
import json
import threading

import pytest

from workbench.runtime.live_client.bridge_handshake import make_hello
from workbench.runtime.live_client.bridge_listener import BridgeListener
from workbench.runtime.live_client.bridge_live_feeds import BridgeLiveFeeds
from workbench.runtime.live_client.bridge_loopback import connect, send
from workbench.runtime.live_client.bridge_peers import LocalPeerRegistry, PeerIdentity
from workbench.runtime.live_client.bridge_protocol import BridgeEnvelope, BridgeLane, BridgeKind


def frame(identity, sequence, observed, lane=BridgeLane.TELEMETRY):
    payload = {"schema_version":1, "client_id":identity.client_id,
               "client_version":"unverified-ashita-v4-api",
               "character":"Hero", "adapter":"ashita-v4-api-experimental",
               "observed_at":observed,
               "position":{"zone_id":100,"x":float(sequence),"y":2,"z":3,"heading":0},
               "entities":[]}
    return BridgeEnvelope(1, lane,
        BridgeKind.OBSERVATION if lane is BridgeLane.TELEMETRY else BridgeKind.CAPTURE_EVENT,
        identity.client_id, identity.session_id, identity.generation, sequence, None,
        json.dumps(payload).encode())


def transmit(address, identity, token, messages):
    with connect(*address) as sock:
        sock.sendall(make_hello(identity, token))
        for message in messages:
            send(sock, message)


def run_batch(receiver, address, identity, token, messages, now=11):
    worker = threading.Thread(target=transmit, args=(address,identity,token,messages))
    worker.start()
    try:
        return receiver.accept_and_update(now=now)
    finally:
        worker.join(timeout=3)
        assert not worker.is_alive()


def test_tcp_telemetry_updates_real_read_only_feed_with_capture_lane_separate():
    peers = LocalPeerRegistry(ttl_seconds=30)
    identity = PeerIdentity("ashita-1","run-1","generation-1")
    token = peers.issue(identity, now=10)
    with BridgeListener(peers) as listener:
        receiver = BridgeLiveFeeds(listener)
        address = listener._server.getsockname()
        result = run_batch(receiver,address,identity,token,
                           [frame(identity,1,100),frame(identity,1,100,BridgeLane.CAPTURE),frame(identity,2,101)])
        assert len(result) == 2
        feed = receiver.feed("ashita-1")
        assert feed.snapshot().position.x == 2
        assert feed.supports_writes is False
        assert listener.mailbox("ashita-1").pending(BridgeLane.CAPTURE) == 1
        with pytest.raises(PermissionError):
            feed.apply(None,{})


def test_stale_batch_is_rejected_without_mutating_previous_feed():
    peers = LocalPeerRegistry(ttl_seconds=30)
    identity = PeerIdentity("ashita-1","run-1","generation-1")
    token = peers.issue(identity, now=10)
    with BridgeListener(peers) as listener:
        receiver = BridgeLiveFeeds(listener); address = listener._server.getsockname()
        run_batch(receiver,address,identity,token,[frame(identity,1,100)])
        with pytest.raises(ValueError, match="stale bridge telemetry"):
            run_batch(receiver,address,identity,token,[frame(identity,2,100)])
        assert receiver.feed("ashita-1").snapshot().observed_at == 100


def test_new_authenticated_generation_replaces_old_feed():
    peers = LocalPeerRegistry(ttl_seconds=30)
    initial = PeerIdentity("ashita-1","run-1","gen-1")
    token = peers.issue(initial, now=10)
    with BridgeListener(peers) as listener:
        receiver = BridgeLiveFeeds(listener); address = listener._server.getsockname()
        run_batch(receiver,address,initial,token,[frame(initial,1,100)])
        following = PeerIdentity("ashita-1","run-2","gen-2")
        new_token = peers.issue(following,now=12)
        run_batch(receiver,address,following,new_token,[frame(following,1,50)],now=13)
        assert receiver.feed("ashita-1").snapshot().observed_at == 50
        assert receiver.feed("ashita-1").supports_writes is False
