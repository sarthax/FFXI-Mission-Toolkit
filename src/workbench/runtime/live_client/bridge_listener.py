"""Explicitly started, bounded localhost receiver for authenticated observations.

No startup side effects, game writes, or capture database mutation.
"""
from __future__ import annotations

import socket
from dataclasses import dataclass, field

from .bridge_handshake import receive_session
from .bridge_loopback import listen
from .bridge_peers import LocalPeerRegistry
from .bridge_protocol import BridgeEnvelope
from .bridge_mailbox import BridgeMailbox
from .bridge_control_broker import ControlBroker
from .bridge_peers import PeerIdentity


@dataclass
class BridgeListener:
    peers: LocalPeerRegistry
    host: str = "127.0.0.1"
    port: int = 0
    timeout: float = 2.0
    controls: ControlBroker | None = None
    max_messages: int = 256
    _server: socket.socket | None = field(default=None, init=False, repr=False)
    _mailboxes: dict[str, BridgeMailbox] = field(default_factory=dict, init=False, repr=False)

    def start(self) -> tuple[str, int]:
        if self._server is not None:
            raise RuntimeError("bridge listener already started")
        if type(self.timeout) not in (float, int) or not 0 < self.timeout <= 30:
            raise ValueError("invalid listener timeout")
        if type(self.max_messages) is not int or not 1 <= self.max_messages <= 4096:
            raise ValueError("invalid session frame limit")
        server = listen(self.host, self.port)
        self._server = server
        return server.getsockname()

    def accept_batch(self, *, now: float | None = None) -> list[BridgeEnvelope]:
        if self._server is None:
            raise RuntimeError("bridge listener not started")
        connection, address = self._server.accept()
        with connection:
            if address[0] != "127.0.0.1":
                raise PermissionError("non-loopback peer")
            connection.settimeout(self.timeout)
            messages = receive_session(connection, self.peers, max_messages=self.max_messages, now=now)
            if len(messages) == 1 and messages[0].kind.value == 'heartbeat':
                from .bridge_protocol import BridgeKind, BridgeLane
                from .bridge_loopback import send
                probe = messages[0]
                response = BridgeEnvelope(1, BridgeLane.CONTROL, BridgeKind.HEARTBEAT,
                    probe.client_id, probe.session_id, probe.generation, probe.sequence + 1,
                    None, b'read_only')
                if self.controls is not None:
                    pending = self.controls.next_for(PeerIdentity(probe.client_id, probe.session_id, probe.generation))
                    if pending is not None:
                        response = pending
                send(connection, response)
        # Control probes and their responses are handled without telemetry queue mutation.
        if len(messages) == 1 and messages[0].lane.value == 'control':
            msg = messages[0]
            if msg.kind.value in ('ack', 'reject'):
                if self.controls is None or not self.controls.resolve(
                    PeerIdentity(msg.client_id, msg.session_id, msg.generation), msg):
                    raise PermissionError('unknown or stale control response')
            return messages
        # Reject the entire batch before any queue mutation if it spans identities.
        if messages:
            first = messages[0]
            source = (first.client_id, first.session_id, first.generation)
            if any((m.client_id, m.session_id, m.generation) != source for m in messages):
                raise ValueError("mixed session stream")
            previous = self._mailboxes.get(first.client_id)
            if previous is None or (previous.session_id, previous.generation) != source[1:]:
                previous = BridgeMailbox(*source)
            for message in messages:
                previous.submit(message)
            self._mailboxes[first.client_id] = previous
        return messages

    def mailbox(self, client_id: str) -> BridgeMailbox | None:
        return self._mailboxes.get(client_id)

    def stop(self) -> None:
        server, self._server = self._server, None
        if server is not None:
            server.close()
        self._mailboxes.clear()

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *_exc):
        self.stop()
