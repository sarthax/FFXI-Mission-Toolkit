"""Read-only native live capture envelope contract.

Transport-independent validation for a future bounded Ashita plugin event queue.
No packet injection, writes, or process attachment.
"""
from __future__ import annotations

from dataclasses import dataclass
import re

MAX_PACKET_BYTES = 4096
MAX_CLIENT_ID = 128
_HEX = re.compile(r"^[0-9a-fA-F]*$")


@dataclass(frozen=True)
class LivePacketEnvelope:
    schema_version: int
    client_id: str
    session_id: str
    sequence: int
    observed_at_ns: int
    direction: str
    opcode: int
    raw_hex: str
    is_injected: bool
    is_blocked: bool
    dropped_before: int = 0

    @classmethod
    def from_mapping(cls, value: dict) -> "LivePacketEnvelope":
        if not isinstance(value, dict):
            raise ValueError("packet envelope must be an object")
        required = {
            "schema_version", "client_id", "session_id", "sequence", "observed_at_ns",
            "direction", "opcode", "raw_hex", "is_injected", "is_blocked",
        }
        if not required.issubset(value):
            raise ValueError("packet envelope missing required fields")
        if set(value) - required - {"dropped_before"}:
            raise ValueError("packet envelope contains unknown fields")
        for key in ("schema_version", "sequence", "observed_at_ns", "opcode", "dropped_before"):
            item = value.get(key, 0)
            if type(item) is not int or item < 0:
                raise ValueError(f"invalid {key}")
        if value["schema_version"] != 1 or value["sequence"] < 1 or value["observed_at_ns"] < 1:
            raise ValueError("unsupported schema version or invalid sequence/time")
        for key in ("client_id", "session_id"):
            item = value[key]
            if not isinstance(item, str) or not 1 <= len(item) <= MAX_CLIENT_ID or any(ord(c) < 32 for c in item):
                raise ValueError(f"invalid {key}")
        if value["direction"] not in ("incoming", "outgoing"):
            raise ValueError("invalid packet direction")
        if value["opcode"] > 65535:
            raise ValueError("opcode out of range")
        raw = value["raw_hex"]
        if not isinstance(raw, str) or len(raw) % 2 or len(raw) > MAX_PACKET_BYTES * 2 or not _HEX.fullmatch(raw):
            raise ValueError("invalid raw packet hex")
        if not raw:
            raise ValueError("empty packet")
        if type(value["is_injected"]) is not bool or type(value["is_blocked"]) is not bool:
            raise ValueError("invalid hook flags")
        return cls(**value)

    @property
    def raw_bytes(self) -> bytes:
        return bytes.fromhex(self.raw_hex)


class LiveCaptureSequence:
    """Check monotonic per-session order and cumulative source-side drops."""

    def __init__(self) -> None:
        self._last: dict[tuple[str, str], tuple[int, int, int]] = {}

    def accept(self, packet: LivePacketEnvelope) -> None:
        key = (packet.client_id, packet.session_id)
        previous = self._last.get(key)
        if previous is not None:
            sequence, observed_ns, drops = previous
            if packet.sequence <= sequence:
                raise ValueError("duplicate or out-of-order packet")
            if packet.sequence - sequence - 1 != packet.dropped_before - drops:
                raise ValueError("packet sequence gap does not match reported drops")
            if packet.observed_at_ns < observed_ns or packet.dropped_before < drops:
                raise ValueError("time or drop counter regressed")
        elif packet.sequence != packet.dropped_before + 1:
            raise ValueError("initial sequence must account for prior drops")
        self._last[key] = (packet.sequence, packet.observed_at_ns, packet.dropped_before)
