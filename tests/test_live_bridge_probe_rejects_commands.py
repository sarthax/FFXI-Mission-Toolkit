import threading
import pytest
from workbench.runtime.live_client.bridge_peers import LocalPeerRegistry, PeerIdentity
from workbench.runtime.live_client.bridge_listener import BridgeListener
from workbench.runtime.live_client.bridge_protocol import BridgeEnvelope, BridgeLane, BridgeKind
from workbench.runtime.live_client.bridge_loopback import connect, send
from workbench.runtime.live_client.bridge_handshake import make_hello

def test_inbound_game_command_is_still_denied():
    peers = LocalPeerRegistry(ttl_seconds=30)
    ident = PeerIdentity("client-a", "session-a", "gen-1")
    token = peers.issue(ident, now=10)
    request = BridgeEnvelope(1, BridgeLane.CONTROL, BridgeKind.COMMAND,
        ident.client_id, ident.session_id, ident.generation, 1, "command-1", b"{}")
    with BridgeListener(peers) as receiver:
        def submit():
            with connect(*receiver._server.getsockname()) as sock:
                sock.sendall(make_hello(ident, token))
                send(sock, request)
                sock.shutdown(1)
        worker = threading.Thread(target=submit)
        worker.start()
        with pytest.raises(PermissionError, match="commands"):
            receiver.accept_batch(now=11)
        worker.join(timeout=4)
        assert not worker.is_alive()
        assert receiver.mailbox(ident.client_id) is None
