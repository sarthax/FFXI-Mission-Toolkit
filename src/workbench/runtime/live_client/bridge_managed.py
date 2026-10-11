"""Opt-in local Live Client receiver with explicit lifecycle and connection status.

No file recording, process attachment, GUI auto-start, or game-state writes.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import secrets
import threading
import time

from .bridge_listener import BridgeListener
from .bridge_live_feeds import BridgeLiveFeeds
from .bridge_peers import LocalPeerRegistry, PeerIdentity
from .bridge_state import BridgeState
from pathlib import Path


@dataclass
class ManagedLiveReceiver:
    port: int = 0
    state_path: Path | None = None  # opt-in persistence of port + credentials
    peers: LocalPeerRegistry = field(default=None)
    listener: BridgeListener = field(init=False)
    feeds: BridgeLiveFeeds = field(init=False)
    _thread: threading.Thread | None = field(default=None, init=False, repr=False)
    _stopping: threading.Event = field(default_factory=threading.Event, init=False, repr=False)
    _lock: threading.RLock = field(default_factory=threading.RLock, init=False, repr=False)
    _last_received: dict[str, float] = field(default_factory=dict, init=False, repr=False)
    _last_error: str | None = field(default=None, init=False)
    _known_clients: set[str] = field(default_factory=set, init=False, repr=False)

    _state: BridgeState | None = field(default=None, init=False, repr=False)

    def _new_peers(self) -> LocalPeerRegistry:
        # Persisted credentials get a 7-day idle lease (refreshed on every batch).
        if self._state is not None:
            return LocalPeerRegistry(ttl_seconds=7 * 86400, max_ttl_seconds=7 * 86400)
        return LocalPeerRegistry(ttl_seconds=3600)

    def __post_init__(self):
        if self.state_path is not None:
            self._state = BridgeState(self.state_path)
            if self.port == 0 and self._state.port:
                self.port = self._state.port
        if self.peers is None:
            self.peers = self._new_peers()
        self.listener = BridgeListener(self.peers, port=self.port, timeout=2)
        self.feeds = BridgeLiveFeeds(self.listener)

    def start(self) -> tuple[str, int]:
        with self._lock:
            if self._thread is not None:
                raise RuntimeError("receiver already started")
            try:
                address = self.listener.start()
            except OSError:
                if not self.listener.port:
                    raise
                # Saved port is taken; fall back to a fresh one (settings get rewritten).
                self.listener.port = 0
                address = self.listener.start()
            if self._state is not None:
                if self._state.port != address[1]:
                    self._state.port = address[1]
                    self._state.save()
                for client_id, c in self._state.clients.items():
                    self.peers.restore(PeerIdentity(client_id, c["session_id"], c["generation"]), c["token"])
                    self._known_clients.add(client_id)
            self._stopping.clear()
            self._thread = threading.Thread(target=self._serve, name="workbench-live-receiver", daemon=True)
            self._thread.start()
            return address

    @property
    def running(self) -> bool:
        return self._thread is not None

    def remembered_ashita_root(self) -> str | None:
        return self._state.ashita_root if self._state else None

    def remember_ashita_root(self, root: str) -> None:
        if self._state is not None and self._state.ashita_root != root:
            self._state.ashita_root = root
            self._state.save()

    def reset_credentials(self, client_id: str | None = None) -> None:
        with self._lock:
            if self._state is not None:
                self._state.forget(client_id)
            targets = [client_id] if client_id else list(self._known_clients)
            for target in targets:
                self.peers.revoke(target)
                self._known_clients.discard(target)
                self.feeds.forget(target)
                self._last_received.pop(target, None)

    def provision(self, client_id: str, *, reuse: bool = False) -> dict[str, object]:
        """Explicitly provision a client; keep the returned secret local.

        reuse=True returns the persisted credentials unchanged when they exist.
        """
        with self._lock:
            if self._thread is None:
                raise RuntimeError("start receiver first")
            port = self.listener._server.getsockname()[1]
            saved = self._state.clients.get(client_id) if self._state else None
            if reuse and saved:
                self.peers.restore(PeerIdentity(client_id, saved["session_id"], saved["generation"]), saved["token"])
                self._known_clients.add(client_id)
                return {"host": "127.0.0.1", "port": port, "client_id": client_id, **saved}
            identity = PeerIdentity(client_id, secrets.token_hex(12), secrets.token_hex(12))
            token = self.peers.issue(identity)
            self._known_clients.add(client_id)
            self.feeds.forget(client_id)
            self._last_received.pop(client_id, None)
            if self._state is not None:
                self._state.clients[client_id] = {"session_id": identity.session_id,
                                                  "generation": identity.generation, "token": token}
                self._state.save()
            return {"host": "127.0.0.1", "port": self.listener._server.getsockname()[1],
                    "client_id": identity.client_id, "session_id": identity.session_id,
                    "generation": identity.generation, "token": token}

    def _serve(self) -> None:
        # Short accept timeout lets the worker exit without blocking teardown.
        self.listener._server.settimeout(0.3)
        while not self._stopping.is_set():
            try:
                frames = self.feeds.accept_and_update()
                if frames:
                    with self._lock:
                        self._last_received[frames[-1].snapshot.client_id] = time.monotonic()
                        self._last_error = None
            except TimeoutError:
                continue
            except OSError as exc:
                if self._stopping.is_set():
                    break
                with self._lock:
                    self._last_error = type(exc).__name__
            except (ValueError, PermissionError, ConnectionError, BufferError) as exc:
                with self._lock:
                    self._last_error = type(exc).__name__

    def clients(self) -> tuple[str, ...]:
        with self._lock:
            return tuple(sorted(self._known_clients))

    def status(self, client_id: str) -> dict[str, object]:
        with self._lock:
            feed = self.feeds.feed(client_id)
            age = time.monotonic() - self._last_received[client_id] if client_id in self._last_received else None
            return {"running": self._thread is not None,
                    "connected": age is not None and age <= 5,
                    "age_seconds": age, "last_error": self._last_error,
                    "snapshot": feed.snapshot() if feed else None}

    def stop(self) -> None:
        self._stopping.set()
        thread = self._thread
        if thread is not None:
            thread.join(timeout=3)
        with self._lock:
            self.listener.stop()
            # Shutdown invalidates every previously issued session/credential.
            self.peers = self._new_peers()
            self.listener.peers = self.peers
            self.feeds = BridgeLiveFeeds(self.listener)
            self._thread = None
            self._last_received.clear()
            self._known_clients.clear()
            self._last_error = None

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *_):
        self.stop()
