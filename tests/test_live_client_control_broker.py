"""Control request delivery accepts only a read-only capability probe."""
import threading
from workbench.runtime.live_client.bridge_control_broker import ControlBroker
from workbench.runtime.live_client.bridge_peers import LocalPeerRegistry, PeerIdentity
from workbench.runtime.live_client.bridge_listener import BridgeListener
from workbench.runtime.live_client.bridge_protocol import BridgeEnvelope, BridgeKind, BridgeLane
from workbench.runtime.live_client.bridge_loopback import connect, receive, send
from workbench.runtime.live_client.bridge_handshake import make_hello


def test_probe_round_trip_is_scoped_and_rejected_by_client():
    peers = LocalPeerRegistry(ttl_seconds=30)
    ident = PeerIdentity("ashita-a", "session-a", "gen-a")
    token = peers.issue(ident, now=10)
    broker = ControlBroker(ttl=3)
    request = broker.schedule_probe(ident, now=10)
    observed = []

    with BridgeListener(peers, controls=broker) as listener:
        def poll():
            with connect(*listener._server.getsockname()) as sock:
                sock.sendall(make_hello(ident, token))
                send(sock, BridgeEnvelope(1, BridgeLane.CONTROL, BridgeKind.HEARTBEAT,
                     ident.client_id, ident.session_id, ident.generation, 1, None, b""))
                sock.shutdown(1)
                observed.append(receive(sock))
        worker = threading.Thread(target=poll)
        worker.start()
        listener.accept_batch(now=11)
        worker.join(timeout=3)
        assert not worker.is_alive()
        assert observed == [request]
        assert broker.status("ashita-a", now=11)["state"] == "delivered"
        def reply():
            with connect(*listener._server.getsockname()) as sock:
                sock.sendall(make_hello(ident, token))
                send(sock, BridgeEnvelope(1, BridgeLane.CONTROL, BridgeKind.REJECT,
                    ident.client_id, ident.session_id, ident.generation,
                    request.sequence+1, request.request_id, b"unsupported_game_writes"))
        worker = threading.Thread(target=reply)
        worker.start()
        listener.accept_batch(now=11.5)
        worker.join(timeout=3)
        assert broker.status("ashita-a", now=11.5)["state"] == "rejected"
        assert listener.mailbox("ashita-a") is None


def test_stale_or_wrong_identity_cannot_take_probe():
    broker = ControlBroker(ttl=2)
    a = PeerIdentity("a", "s", "g")
    broker.schedule_probe(a, now=10)
    assert broker.next_for(PeerIdentity("a", "s", "restarted"), now=10.1) is None
    assert broker.status("a", now=10.1)["state"] == "cancelled"
    broker.schedule_probe(a, now=11)
    assert broker.next_for(a, now=14) is None
    assert broker.status("a", now=14)["state"] == "expired"


def test_no_second_outstanding_probe_and_stopped_cancel():
    broker = ControlBroker()
    ident = PeerIdentity("a", "s", "g")
    broker.schedule_probe(ident, now=10)
    try:
        broker.schedule_probe(ident, now=10.1)
    except ValueError:
        pass
    else:
        assert False, "duplicate probe must be rejected"
    broker.cancel()
    assert broker.next_for(ident, now=11) is None
