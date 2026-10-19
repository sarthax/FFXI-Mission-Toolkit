"""Bounded local TCP health probes; no process enumeration or remote scanning."""
from __future__ import annotations

import os
import socket
import time

SERVICES = {
    "dsp_map": ("MISSION_TOOLKIT_SUPERVISOR_DSP_HOST", "MISSION_TOOLKIT_SUPERVISOR_DSP_PORT"),
    "database": ("MISSION_TOOLKIT_SUPERVISOR_DB_HOST", "MISSION_TOOLKIT_SUPERVISOR_DB_PORT"),
    "ollama": ("MISSION_TOOLKIT_SUPERVISOR_OLLAMA_HOST", "MISSION_TOOLKIT_SUPERVISOR_OLLAMA_PORT"),
}
DEFAULT_PORT = {"dsp_map": None, "database": 3306, "ollama": 11434}


def service_health(name: str) -> dict:
    if name not in SERVICES:
        raise ValueError("unknown service")
    host_var, port_var = SERVICES[name]
    host = os.environ.get(host_var, "127.0.0.1")
    raw = os.environ.get(port_var)
    if raw is None and DEFAULT_PORT[name] is None:
        return {"service": name, "configured": False, "reachable": None}
    try:
        port = int(raw) if raw is not None else DEFAULT_PORT[name]
    except (ValueError, TypeError) as exc:
        raise ValueError("invalid configured port") from exc
    if not 1 <= port <= 65535:
        raise ValueError("invalid configured port")
    # Deliberately loopback-only to avoid turning an LLM endpoint into a network scanner.
    if host not in ("127.0.0.1", "::1", "localhost"):
        raise ValueError("only local loopback services can be checked")
    try:
        with socket.create_connection((host, port), timeout=0.5):
            return {"service": name, "configured": True, "reachable": True,
                    "check": "tcp_connect_only"}
    except OSError:
        return {"service": name, "configured": True, "reachable": False,
                "check": "tcp_connect_only"}
