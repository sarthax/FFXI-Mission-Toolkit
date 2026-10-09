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


@dataclass
class ManagedLiveReceiver:
    port: int = 0
    peers: LocalPeerRegistry = field(default_factory=lambda: LocalPeerRegistry(ttl_seconds=3600))
    listener: BridgeListener = field(init=False)
    feeds: BridgeLiveFeeds = field(init=False)
    _thread: threading.Thread | None = field(default=None, init=False, repr=False)
    _stopping: threading.Event = field(default_factory=threading.Event, init=False, repr=False)
    _lock: threading.RLock = field(default_factory=threading.RLock, init=False, repr=False)
    _last_received: dict[str, float] = field(default_factory=dict, init=False, repr=False)
    _last_error: str | None = field(default=None, init=False)

    def __post_init__(self):
        self.listener = BridgeListener(self.peers, port=self.port, timeout=2)
        self.feeds = BridgeLiveFeeds(self.listener)

    def start(self) -> tuple[str, int]:
        with self._lock:
            if self._thread is not None:
                raise RuntimeError("receiver already started")
            address = self.listener.start()
            self._stopping.clear()
            self._thread = threading.Thread(target=self._serve, name="workbench-live-receiver", daemon=True)
            self._thread.start()
            return address

    def provision(self, client_id: str) -> dict[str, object]:
        """Explicitly provision a client; keep the returned secret local."""
        with self._lock:
            if self._thread is None:
                raise RuntimeError("start receiver first")
            identity = PeerIdentity(client_id, secrets.token_hex(12), secrets.token_hex(12))
            token = self.peers.issue(identity)
            self.feeds.forget(client_id)
            self._last_received.pop(client_id, None)
            return {"host": "127.0.0.1", "port": self.listener._server.getsockname()[1],
                    "client_id": identity.client_id, "session_id": identity.session_id,
                    "generation": identity.generation, "token": token}

    def _serve(self) -> None:
        # Short accept timeout lets the worker exit without blocking teardown.
        self.listener._server.settimeout(0.3)
        while not self._stopping.is_set():
            try:
                with self._lock:
                    frames = self.feeds.accept_and_update()
                    if frames:
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
            self._thread = None
            self._last_received.clear()
            self._last_error = None

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *_):
        self.stop()
