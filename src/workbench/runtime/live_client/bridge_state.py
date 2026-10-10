"""Opt-in persisted receiver setup so Toolkit/Ashita restarts need no re-provisioning.

Stores the fixed local port, remembered Ashita folder and per-client credentials
in one private local JSON file (never committed). Same trust level as the
generated Ashita settings file. Delete the file or use "Reset credentials" to revoke.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
_TOKEN = re.compile(r"^[A-Za-z0-9_-]{32,256}$")
_FIELD = re.compile(r"^[A-Za-z0-9_.:-]{1,128}$")


class BridgeState:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.port: int | None = None
        self.ashita_root: str | None = None
        self.clients: dict[str, dict[str, str]] = {}
        self.load()

    def load(self) -> None:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        if type(data) is not dict:
            return
        port = data.get("port")
        if type(port) is int and 1024 <= port <= 65535:
            self.port = port
        root = data.get("ashita_root")
        if type(root) is str and 0 < len(root) <= 2048:
            self.ashita_root = root
        for client_id, entry in (data.get("clients") or {}).items():
            if (type(entry) is dict and _ID.match(client_id)
                    and all(type(entry.get(k)) is str for k in ("session_id", "generation", "token"))
                    and _FIELD.match(entry["session_id"]) and _FIELD.match(entry["generation"])
                    and _TOKEN.match(entry["token"])):
                self.clients[client_id] = {k: entry[k] for k in ("session_id", "generation", "token")}

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.path.with_suffix(".tmp")
        temp.write_text(json.dumps({"port": self.port, "ashita_root": self.ashita_root,
                                    "clients": self.clients}, indent=1), encoding="utf-8")
        os.replace(temp, self.path)

    def forget(self, client_id: str | None = None) -> None:
        if client_id is None:
            self.clients.clear()
        else:
            self.clients.pop(client_id, None)
        self.save()
