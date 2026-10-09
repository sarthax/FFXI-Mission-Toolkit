"""Opt-in loopback-only framed transport for bridge envelopes.

No Ashita hookup and no game writes. Caller owns socket lifecycle and endpoint
authentication; this helper refuses non-loopback addresses and unbounded frames.
"""
from __future__ import annotations

import base64
import ipaddress
import json
import socket
import struct

from .bridge_protocol import BridgeEnvelope, BridgeKind, BridgeLane

MAX_FRAME = 96 * 1024


def _loopback(host: str) -> str:
    try:
        address = ipaddress.ip_address(host)
    except ValueError as exc:
        raise ValueError("bridge host must be numeric loopback") from exc
    if not address.is_loopback or address.version != 4:
        raise ValueError("bridge transport must bind IPv4 loopback")
    return str(address)


def encode(envelope: BridgeEnvelope) -> bytes:
    doc = {
        "schema_version": envelope.schema_version,
        "lane": envelope.lane.value, "kind": envelope.kind.value,
        "client_id": envelope.client_id, "session_id": envelope.session_id,
        "generation": envelope.generation, "sequence": envelope.sequence,
        "request_id": envelope.request_id,
        "payload_base64": base64.b64encode(envelope.payload).decode("ascii"),
    }
    body = json.dumps(doc, separators=(",", ":"), allow_nan=False).encode("utf-8")
    if not body or len(body) > MAX_FRAME:
        raise ValueError("bridge frame too large")
    return struct.pack("!I", len(body)) + body


def decode(body: bytes) -> BridgeEnvelope:
    if type(body) is not bytes or not 0 < len(body) <= MAX_FRAME:
        raise ValueError("invalid bridge frame size")
    try:
        doc = json.loads(body.decode("utf-8"))
        fields = {"schema_version", "lane", "kind", "client_id", "session_id",
                  "generation", "sequence", "request_id", "payload_base64"}
        if type(doc) is not dict or set(doc) != fields:
            raise ValueError("invalid bridge fields")
        payload = base64.b64decode(doc["payload_base64"], validate=True)
        return BridgeEnvelope(doc["schema_version"], BridgeLane(doc["lane"]),
                              BridgeKind(doc["kind"]), doc["client_id"],
                              doc["session_id"], doc["generation"], doc["sequence"],
                              doc["request_id"], payload)
    except (UnicodeError, json.JSONDecodeError, KeyError, TypeError,
            ValueError, base64.binascii.Error) as exc:
        raise ValueError("malformed bridge frame") from exc


def read_exact(sock: socket.socket, count: int) -> bytes:
    chunks = bytearray()
    while len(chunks) < count:
        part = sock.recv(count - len(chunks))
        if not part:
            raise ConnectionError("bridge peer disconnected")
        chunks.extend(part)
    return bytes(chunks)


def receive(sock: socket.socket) -> BridgeEnvelope:
    (size,) = struct.unpack("!I", read_exact(sock, 4))
    if not 0 < size <= MAX_FRAME:
        raise ValueError("invalid bridge frame length")
    return decode(read_exact(sock, size))


def send(sock: socket.socket, envelope: BridgeEnvelope) -> None:
    sock.sendall(encode(envelope))


def listen(host: str = "127.0.0.1", port: int = 0) -> socket.socket:
    address = _loopback(host)
    if type(port) is not int or not 0 <= port <= 65535:
        raise ValueError("invalid bridge port")
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind((address, port))
        sock.listen(1)
        sock.settimeout(5)
        return sock
    except Exception:
        sock.close()
        raise


def connect(host: str, port: int, timeout: float = 5) -> socket.socket:
    address = _loopback(host)
    if type(port) is not int or not 1 <= port <= 65535:
        raise ValueError("invalid bridge port")
    if type(timeout) not in (float, int) or not 0 < timeout <= 30:
        raise ValueError("invalid bridge timeout")
    return socket.create_connection((address, port), timeout=timeout)
