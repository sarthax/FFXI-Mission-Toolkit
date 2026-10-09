"""One-connection authenticated handshake for opt-in localhost bridge peers.

The operator must arrange secret delivery outside this socket. No automatic
server or Ashita adapter exists. An accepted peer is not authorized to write.
"""
from __future__ import annotations

import json
import socket

from .bridge_loopback import read_exact
from .bridge_peers import LocalPeerRegistry, PeerIdentity
from .bridge_protocol import BridgeEnvelope
from .bridge_loopback import receive

MAX_HELLO = 1024


def _read_hello(sock: socket.socket) -> dict:
    length = int.from_bytes(read_exact(sock, 2), "big")
    if not 0 < length <= MAX_HELLO:
        raise ValueError("invalid bridge handshake length")
    try:
        data = json.loads(read_exact(sock, length).decode("utf-8"))
    except (UnicodeError, ValueError) as exc:
        raise ValueError("invalid bridge handshake") from exc
    if type(data) is not dict or set(data) != {"client_id", "session_id", "generation", "token"}:
        raise ValueError("invalid bridge handshake fields")
    if any(type(data[k]) is not str for k in data):
        raise ValueError("invalid bridge handshake field")
    return data


def make_hello(identity: PeerIdentity, token: str) -> bytes:
    body = json.dumps({"client_id": identity.client_id, "session_id": identity.session_id,
                       "generation": identity.generation, "token": token},
                      separators=(",", ":")).encode("utf-8")
    if not 0 < len(body) <= MAX_HELLO:
        raise ValueError("invalid bridge handshake length")
    return len(body).to_bytes(2, "big") + body


def accept_one(sock: socket.socket, peers: LocalPeerRegistry, *, now: float | None = None) -> BridgeEnvelope:
    """Authenticate first; accept exactly one matching envelope, no write dispatch."""
    hello = _read_hello(sock)
    identity = PeerIdentity(hello["client_id"], hello["session_id"], hello["generation"])
    if not peers.authenticate(identity, hello["token"], now=now):
        raise PermissionError("untrusted bridge peer")
    message = receive(sock)
    if not peers.accepts(message, hello["token"], now=now):
        raise PermissionError("bridge peer identity changed or lease expired")
    return message
