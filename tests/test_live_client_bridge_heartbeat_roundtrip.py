"""Authenticated read-only round-trip on the existing Live Client socket."""
import threading
from workbench.runtime.live_client.bridge_peers import LocalPeerRegistry, PeerIdentity
from workbench.runtime.live_client.bridge_listener import BridgeListener
from workbench.runtime.live_client.bridge_protocol import BridgeEnvelope, BridgeLane, BridgeKind
from workbench.runtime.live_client.bridge_loopback import connect, receive, send
from workbench.runtime.live_client.bridge_handshake import make_hello


def test_authenticated_heartbeat_receives_read_only_reply():
    peers = LocalPeerRegistry(ttl_seconds=30)
    ident = PeerIdentity("client-a", "session-a", "gen-1")
    token = peers.issue(ident, now=10)
    frame = BridgeEnvelope(1, BridgeLane.CONTROL, BridgeKind.HEARTBEAT,
                           ident.client_id, ident.session_id, ident.generation, 1, None, b"")
    observed = []

    with BridgeListener(peers) as server:
        def peer():
            with connect(*server._server.getsockname()) as sock:
                sock.sendall(make_hello(ident, token))
                send(sock, frame)
                sock.shutdown(1)
                observed.append(receive(sock))
        worker = threading.Thread(target=peer)
        worker.start()
        received = server.accept_batch(now=11)
        worker.join(timeout=4)
        assert not worker.is_alive()
        assert received == [frame]
        assert len(observed) == 1
        assert observed[0].kind is BridgeKind.HEARTBEAT
        assert observed[0].payload == b"read_only"
        assert (observed[0].client_id, observed[0].session_id, observed[0].generation) == (
            ident.client_id, ident.session_id, ident.generation)
        assert server.mailbox(ident.client_id) is None
