"""Discover and open the live character database from a configured server checkout.

Supports modern LandSandBoat settings/network.lua plus legacy Topaz/DSP map.conf formats.
Credentials are never returned by public/status helpers.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any

CONF_CANDIDATES = (
    "settings/network.lua",      # modern LandSandBoat
    "conf/map.conf",            # Topaz-era
    "conf/map_darkstar.conf",   # DarkStar Project
)
_LEGACY_KEYS = (
    "mysql_host",
    "mysql_port",
    "mysql_login",
    "mysql_password",
    "mysql_database",
)
_LSB_KEYS = (
    "SQL_HOST",
    "SQL_PORT",
    "SQL_LOGIN",
    "SQL_PASSWORD",
    "SQL_DATABASE",
)


@dataclass(frozen=True)
class DatabaseProfile:
    server_root: Path
    conf_path: Path
    host: str
    port: int
    user: str
    password: str
    database: str
    config_family: str

    def public_dict(self) -> dict[str, Any]:
        return {
            "server_root": str(self.server_root),
            "conf_path": str(self.conf_path),
            "host": self.host,
            "port": self.port,
            "user": self.user,
            "database": self.database,
            "config_family": self.config_family,
        }


def _find_conf(server_root: Path) -> Path:
    root = Path(server_root).expanduser().resolve()
    for rel in CONF_CANDIDATES:
        candidate = root / rel
        if candidate.is_file():
            return candidate
    raise FileNotFoundError(
        f"No supported MariaDB configuration found under {root}; tried "
        + ", ".join(CONF_CANDIDATES)
    )


def _strip_value(raw: str) -> str:
    value = raw.strip().rstrip(",").strip()
    return value.strip('"').strip("'")


def _parse_legacy_conf(path: Path, text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for key in _LEGACY_KEYS:
        match = re.search(rf"(?m)^\s*{re.escape(key)}\s*:\s*([^#\r\n]+?)\s*$", text)
        if match:
            values[key] = _strip_value(match.group(1))
    missing = [key for key in _LEGACY_KEYS if key not in values]
    if missing:
        raise ValueError(f"Missing MariaDB setting(s) in {path}: {', '.join(missing)}")
    return {
        "host": values["mysql_host"],
        "port": values["mysql_port"],
        "user": values["mysql_login"],
        "password": values["mysql_password"],
        "database": values["mysql_database"],
        "config_family": "legacy_conf",
    }


def _parse_lsb_network(path: Path, text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for key in _LSB_KEYS:
        match = re.search(rf"(?m)^\s*{re.escape(key)}\s*=\s*([^,\r\n]+)", text)
        if match:
            values[key] = _strip_value(match.group(1))
    missing = [key for key in _LSB_KEYS if key not in values]
    if missing:
        raise ValueError(f"Missing MariaDB setting(s) in {path}: {', '.join(missing)}")
    return {
        "host": values["SQL_HOST"],
        "port": values["SQL_PORT"],
        "user": values["SQL_LOGIN"],
        "password": values["SQL_PASSWORD"],
        "database": values["SQL_DATABASE"],
        "config_family": "lsb_settings",
    }


def _parse_conf(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8", errors="ignore")
    if path.as_posix().endswith("settings/network.lua"):
        return _parse_lsb_network(path, text)
    return _parse_legacy_conf(path, text)


def discover_database_profile(server_root: Path | str) -> DatabaseProfile:
    root = Path(server_root).expanduser().resolve()
    conf = _find_conf(root)
    values = _parse_conf(conf)
    return DatabaseProfile(
        server_root=root,
        conf_path=conf,
        host=values["host"],
        port=int(values["port"]),
        user=values["user"],
        password=values["password"],
        database=values["database"],
        config_family=values["config_family"],
    )


def connect(profile: DatabaseProfile, **kwargs):
    try:
        import mysql.connector
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("Character Editor live database access requires mysql-connector-python") from exc
    return mysql.connector.connect(
        host=profile.host,
        port=profile.port,
        user=profile.user,
        password=profile.password,
        database=profile.database,
        **kwargs,
    )


def connect_from_server_root(server_root: Path | str, **kwargs):
    return connect(discover_database_profile(server_root), **kwargs)
