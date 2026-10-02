"""Discover and open the live character database from the active server checkout.

The Mission Toolkit already uses map.conf / map_darkstar.conf for live MariaDB access.
Character Editor reuses that convention so administrators do not need to duplicate credentials.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any

CONF_CANDIDATES = (
    "conf/map.conf",
    "conf/map_darkstar.conf",
)
_REQUIRED_KEYS = (
    "mysql_host",
    "mysql_port",
    "mysql_login",
    "mysql_password",
    "mysql_database",
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

    def public_dict(self) -> dict[str, Any]:
        """Safe metadata for UI/status surfaces. Never expose the password."""
        return {
            "server_root": str(self.server_root),
            "conf_path": str(self.conf_path),
            "host": self.host,
            "port": self.port,
            "user": self.user,
            "database": self.database,
        }


def _find_conf(server_root: Path) -> Path:
    root = Path(server_root).expanduser().resolve()
    for rel in CONF_CANDIDATES:
        candidate = root / rel
        if candidate.is_file():
            return candidate
    raise FileNotFoundError(
        f"No MariaDB map configuration found under {root}; tried "
        + ", ".join(CONF_CANDIDATES)
    )


def _parse_conf(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8", errors="ignore")
    values: dict[str, str] = {}
    for key in _REQUIRED_KEYS:
        match = re.search(rf"(?m)^\s*{re.escape(key)}\s*:\s*([^#\r\n]+?)\s*$", text)
        if match:
            values[key] = match.group(1).strip().strip('"').strip("'")
    missing = [key for key in _REQUIRED_KEYS if key not in values]
    if missing:
        raise ValueError(f"Missing MariaDB setting(s) in {path}: {', '.join(missing)}")
    return values


def discover_database_profile(server_root: Path | str) -> DatabaseProfile:
    root = Path(server_root).expanduser().resolve()
    conf = _find_conf(root)
    values = _parse_conf(conf)
    return DatabaseProfile(
        server_root=root,
        conf_path=conf,
        host=values["mysql_host"],
        port=int(values["mysql_port"]),
        user=values["mysql_login"],
        password=values["mysql_password"],
        database=values["mysql_database"],
    )


def connect(profile: DatabaseProfile, **kwargs):
    """Open a mysql.connector connection without leaking credentials into logs."""
    try:
        import mysql.connector
    except ImportError as exc:  # pragma: no cover - environment-specific dependency
        raise RuntimeError(
            "Character Editor live database access requires mysql-connector-python"
        ) from exc
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
