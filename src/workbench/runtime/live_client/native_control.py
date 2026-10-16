"""Toolkit side of the native plugin's file control channel.

The Ashita plugin (workbench_native_probe) only accepts commands when the admin has set
``allow_file_commands=1`` in ``<Ashita>/config/workbench_native/settings.ini``.  Commands are one
atomic ``command.txt`` write; results come back through ``status.txt``.  Positions use SERVER
order (what ``!logpos`` prints: x, y = height, z); the plugin converts to SDK axes in one place.
Results are client-local until compared against ``!logpos`` / telemetry: never claimed otherwise.
"""
from __future__ import annotations

import math
import os
import re
import time
from pathlib import Path

CONSENT = "DEV-SERVER-ONLY"
MAX_ABS_COORD = 4096.0
STATUS_FRESH_SECONDS = 3.0
_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,32}$")
_MODES = ("warp", "autorun", "local")
MAX_CHAT_LEN = 120


class NativeControlError(Exception):
    def __init__(self, code: str, message: str | None = None):
        super().__init__(message or code)
        self.code = code


def channel_dir(ashita_root: str | os.PathLike) -> Path:
    return Path(ashita_root) / "config" / "workbench_native"


def parse_kv(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in text.splitlines()[:64]:
        line = line.strip()
        if not line or line[0] in "#;" or "=" not in line:
            continue
        key, _, value = line.partition("=")
        out[key.strip()] = value.strip()
    return out


def read_status(ashita_root: str | os.PathLike) -> dict:
    """Parsed status.txt plus `online` (fresh heartbeat) and `age_seconds`."""
    path = channel_dir(ashita_root) / "status.txt"
    try:
        text = path.read_text(encoding="ascii", errors="replace")
        age = max(0.0, time.time() - path.stat().st_mtime)
    except OSError:
        return {"online": False, "reason": "no_status_file", "age_seconds": None}
    kv = parse_kv(text)
    num = lambda k: float(kv[k]) if k in kv and re.fullmatch(r"-?\d+(\.\d+)?", kv[k]) else None
    return {
        "online": age <= STATUS_FRESH_SECONDS,
        "age_seconds": round(age, 2),
        "nonce": kv.get("nonce", ""),
        "channel_enabled": kv.get("allow_file_commands") == "1",
        "chat_enabled": kv.get("allow_chat_commands") == "1",
        "armed": kv.get("enabled") == "1",
        "mode": kv.get("mode", ""),
        "auto_arm": kv.get("auto_arm", ""),
        "player_valid": kv.get("player_valid") == "1",
        "zone": int(num("zone") or 0),
        "zoning": kv.get("zoning") == "1",
        "position": {"x": num("pos_x"), "y": num("pos_y"), "z": num("pos_z")},
        "speed": {"active": kv.get("speed_active") == "1", "percent": num("speed_percent"),
                  "raw": num("speed_raw")},
        "last": {"seq": int(num("last_seq") or 0), "id": kv.get("last_id", ""),
                 "ok": kv.get("last_ok") == "1", "reason": kv.get("last_reason", "")},
        "move": {k[5:]: v for k, v in kv.items() if k.startswith("move_")},
        "scope": "client_local", "server_confirmed": False,
    }


def _finite(value, name: str) -> float:
    try:
        v = float(value)
    except (TypeError, ValueError):
        raise NativeControlError("invalid_" + name) from None
    if not math.isfinite(v):
        raise NativeControlError("invalid_" + name)
    return v


def build_command(cmd: str, fields: dict) -> dict[str, str]:
    """Validate and normalise one command's fields (raises NativeControlError)."""
    out: dict[str, str] = {"cmd": cmd}
    if cmd in ("stop", "disable", "speed_off"):
        return out
    if cmd == "enable":
        if fields.get("consent") != CONSENT:
            raise NativeControlError("consent_required")
        mode = fields.get("mode", "warp")
        if mode not in _MODES:
            raise NativeControlError("invalid_mode")
        return {**out, "mode": mode, "consent": CONSENT}
    if cmd == "warp_to":
        wid = str(fields.get("id") or f"tk{int(time.time() * 1000) % 10**9}")
        if not _ID_RE.match(wid):
            raise NativeControlError("invalid_id")
        for axis in "xyz":
            if abs(_finite(fields.get(axis), axis)) > MAX_ABS_COORD:
                raise NativeControlError("target_out_of_bounds")
        return {**out, "id": wid, **{a: repr(round(float(fields[a]), 3)) for a in "xyz"}}
    if cmd == "chat":
        text = str(fields.get("text") or "")
        if (not 2 <= len(text) <= MAX_CHAT_LEN or text[0] != "!" or text[1] == " "
                or any(not 0x20 <= ord(c) <= 0x7E or c == ";" for c in text)):
            raise NativeControlError("invalid_chat_line", "only '!' GM commands of printable ASCII "
                                     f"(max {MAX_CHAT_LEN} chars, no ';') can be sent")
        return {**out, "text": text}
    if cmd == "speed":
        pct = _finite(fields.get("value"), "speed")
        if not 25 <= pct <= 400:
            raise NativeControlError("invalid_speed")
        return {**out, "value": repr(round(pct, 1))}
    raise NativeControlError("unknown_command")


def send_command(ashita_root: str | os.PathLike, cmd: str, fields: dict | None = None,
                 wait_seconds: float = 3.0) -> dict:
    """Send one command and wait for the plugin to report its outcome."""
    body = build_command(cmd, fields or {})
    status = read_status(ashita_root)
    if not status["online"]:
        raise NativeControlError("plugin_offline", "native plugin status is stale or missing "
                                 "(is workbench_native_probe loaded?)")
    if not status["channel_enabled"]:
        raise NativeControlError("channel_disabled", "set allow_file_commands=1 in "
                                 "config/workbench_native/settings.ini")
    if cmd == "chat" and not status["chat_enabled"]:
        raise NativeControlError("chat_disabled", "set allow_chat_commands=1 in "
                                 "config/workbench_native/settings.ini and reload the plugin")
    seq = int(time.time() * 1000)
    lines = [f"seq={seq}", f"nonce={status['nonce']}", f"ts_ms={seq}"]
    lines += [f"{k}={v}" for k, v in body.items()]
    directory = channel_dir(ashita_root)
    tmp = directory / "command.tmp"
    tmp.write_text("\n".join(lines) + "\n", encoding="ascii")
    os.replace(tmp, directory / "command.txt")
    deadline = time.time() + wait_seconds
    while time.time() < deadline:
        time.sleep(0.15)
        current = read_status(ashita_root)
        if current["last"]["seq"] == seq:
            return {"sent": True, "seq": seq, "outcome": current["last"], "status": current}
    return {"sent": True, "seq": seq, "outcome": None, "status": read_status(ashita_root),
            "note": "no outcome yet: the plugin may be zoning or the game window may be idle"}
