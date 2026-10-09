"""End-to-end opt-in manager: localhost telemetry without JSONL."""
import json
import time

from workbench.runtime.live_client.bridge_managed import ManagedLiveReceiver
from workbench.runtime.live_client.bridge_handshake import make_hello
from workbench.runtime.live_client.bridge_loopback import connect, send
from workbench.runtime.live_client.bridge_peers import PeerIdentity
from workbench.runtime.live_client.bridge_protocol import BridgeEnvelope, BridgeKind, BridgeLane


def push(config, observed):
    identity = PeerIdentity(config["client_id"], config["session_id"], config["generation"])
    payload = {"schema_version": 1, "client_id": identity.client_id,
               "client_version": "unverified-ashita-v4-api",
               "character": "Hero", "adapter": "ashita-v4-api-experimental",
               "observed_at": observed, "position":
               {"zone_id": 235, "x": float(observed), "y": 2, "z": 3, "heading": 0},
               "entities": []}
    msg = BridgeEnvelope(1, BridgeLane.TELEMETRY, BridgeKind.OBSERVATION,
                         identity.client_id, identity.session_id, identity.generation,
                         1, None, json.dumps(payload).encode())
    with connect(config["host"], config["port"]) as sock:
        sock.sendall(make_hello(identity, config["token"]))
        send(sock, msg)


def test_explicit_receiver_start_provision_receives_live_snapshot_and_stops():
    receiver = ManagedLiveReceiver()
    with receiver:
        config = receiver.provision("ashita-a")
        assert config["host"] == "127.0.0.1"
        push(config, 100)
        deadline = time.monotonic() + 4
        while receiver.status("ashita-a")["snapshot"] is None and time.monotonic() < deadline:
            time.sleep(.02)
        state = receiver.status("ashita-a")
        assert state["connected"] is True
        assert state["snapshot"].position.x == 100
        assert receiver.feeds.feed("ashita-a").supports_writes is False
    assert receiver.status("ashita-a")["running"] is False


def test_reprovision_revokes_previous_generation():
    receiver = ManagedLiveReceiver()
    with receiver:
        original = receiver.provision("ashita-a")
        replacement = receiver.provision("ashita-a")
        assert original["token"] != replacement["token"]
        assert original["generation"] != replacement["generation"]
        assert receiver.peers.authenticate(
            PeerIdentity(original["client_id"],original["session_id"],original["generation"]),
            original["token"]) is False
