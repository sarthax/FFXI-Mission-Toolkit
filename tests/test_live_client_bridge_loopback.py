"""Real TCP loopback framing tests; no Ashita or game-process access."""
import socket
import struct
import threading

import pytest

from workbench.runtime.live_client.bridge_protocol import BridgeEnvelope, BridgeKind, BridgeLane
from workbench.runtime.live_client.bridge_loopback import (
    MAX_FRAME, connect, decode, encode, listen, receive, send,
)


def observation(client="a"):
    return BridgeEnvelope(1, BridgeLane.TELEMETRY, BridgeKind.OBSERVATION,
                          client, "session", "generation", 1, None, b'{"x":1}')


def test_localhost_roundtrip_two_independent_sources():
    server = listen()
    port = server.getsockname()[1]
    frames = []
    errors = []

    def accept():
        try:
            for _ in range(2):
                connection, _ = server.accept()
                with connection:
                    connection.settimeout(2)
                    frames.append(receive(connection))
        except Exception as exc:
            errors.append(exc)

    worker = threading.Thread(target=accept)
    worker.start()
    try:
        for client in ("first", "second"):
            with connect("127.0.0.1", port) as peer:
                send(peer, observation(client))
        worker.join(timeout=5)
        assert not worker.is_alive()
        assert not errors
        assert [frame.client_id for frame in frames] == ["first", "second"]
    finally:
        server.close()


def test_fragmented_transport_and_disconnect_fail_closed():
    left, right = socket.socketpair()
    try:
        payload = encode(observation())
        for piece in (payload[:2], payload[2:9], payload[9:]):
            left.sendall(piece)
        assert receive(right) == observation()
        left.close()
        with pytest.raises(ConnectionError, match="disconnected"):
            receive(right)
    finally:
        left.close()
        right.close()


def test_unbounded_or_malformed_frames_rejected_before_body():
    left, right = socket.socketpair()
    try:
        left.sendall(struct.pack("!I", MAX_FRAME + 1))
        with pytest.raises(ValueError, match="length"):
            receive(right)
    finally:
        left.close()
        right.close()
    with pytest.raises(ValueError, match="malformed"):
        decode(b'{"payload_base64":"!"}')
    with pytest.raises(ValueError):
        decode(b"not-json")


@pytest.mark.parametrize("host", ["0.0.0.0", "192.168.1.10", "localhost", "::1"])
def test_non_numeric_ipv4_loopback_listener_rejected(host):
    with pytest.raises(ValueError):
        listen(host)


def test_bounded_frame_roundtrip_keeps_original_bytes():
    value = BridgeEnvelope(1, BridgeLane.CAPTURE, BridgeKind.CAPTURE_EVENT,
                           "client", "session", "gen", 2, None, bytes(range(256)))
    wire = encode(value)
    assert decode(wire[4:]) == value
