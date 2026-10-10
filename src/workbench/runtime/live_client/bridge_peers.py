"""Explicit local peer registration for a future Live Client bridge service.

Not a remote authentication service. The caller must deliver the random token
out-of-band to the trusted same-host peer and protect local access to it.
"""
from __future__ import annotations

from dataclasses import dataclass
import hmac
import secrets
import time

from .bridge_protocol import BridgeEnvelope


@dataclass(frozen=True)
class PeerIdentity:
    client_id: str
    session_id: str
    generation: str


class LocalPeerRegistry:
    def __init__(self, *, ttl_seconds: float = 30, max_ttl_seconds: float = 3600):
        if max_ttl_seconds not in (3600, 7 * 86400):
            raise ValueError("invalid peer lease cap")
        if type(ttl_seconds) not in (float, int) or not 1 <= ttl_seconds <= max_ttl_seconds:
            raise ValueError("invalid peer lease")
        self.ttl_seconds = ttl_seconds
        self._peers: dict[str, tuple[PeerIdentity, str, float]] = {}

    def issue(self, identity: PeerIdentity, *, now: float | None = None) -> str:
        if not all(isinstance(v, str) and 0 < len(v) <= 128
                   for v in (identity.client_id, identity.session_id, identity.generation)):
            raise ValueError("invalid bridge peer identity")
        clock = time.monotonic() if now is None else now
        if type(clock) not in (float, int) or not 0 <= clock < float("inf"):
            raise ValueError("invalid peer clock")
        token = secrets.token_urlsafe(32)
        self._peers[identity.client_id] = (identity, token, clock + self.ttl_seconds)
        return token

    def restore(self, identity: PeerIdentity, token: str, *, now: float | None = None) -> None:
        """Re-register previously issued credentials (opt-in persisted setup)."""
        if type(token) is not str or not 32 <= len(token) <= 256:
            raise ValueError("invalid restored bridge token")
        self.issue(identity, now=now)  # validates identity and clock
        _, _, expiry = self._peers[identity.client_id]
        self._peers[identity.client_id] = (identity, token, expiry)

    def authenticate(self, identity: PeerIdentity, token: str, *,
                     now: float | None = None) -> bool:
        clock = time.monotonic() if now is None else now
        if type(clock) not in (float, int) or not 0 <= clock < float("inf"):
            return False
        entry = self._peers.get(identity.client_id)
        if not entry or type(token) is not str:
            return False
        expected, secret, expiry = entry
        return clock < expiry and identity == expected and hmac.compare_digest(token, secret)

    def refresh(self, identity: PeerIdentity, token: str, *, now: float | None = None) -> bool:
        clock = time.monotonic() if now is None else now
        if not self.authenticate(identity, token, now=clock):
            return False
        self._peers[identity.client_id] = (identity, token, clock + self.ttl_seconds)
        return True

    def revoke(self, client_id: str) -> None:
        self._peers.pop(client_id, None)

    def accepts(self, message: BridgeEnvelope, token: str, *, now: float | None = None) -> bool:
        return self.authenticate(
            PeerIdentity(message.client_id, message.session_id, message.generation),
            token, now=now,
        )
