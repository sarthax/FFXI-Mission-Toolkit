"""Named server/environment profiles for selecting an administered FFXI server.

This module is intentionally additive and independent from the legacy settings bridge so it can
land safely while Phase-D settings work is still in flight.  Integration adapters may later map
``get_active_server_root()`` and GUI selectors onto this store without changing this schema.

Secrets are not stored here.  Database credentials continue to come from each server checkout's
native configuration (LSB ``settings/network.lua`` or legacy ``conf/map*.conf``).
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sqlite3
from typing import Iterable

from workbench.runtime.paths import DATABASE_PATH

_ALLOWED_FAMILIES = {"auto", "lsb", "topaz", "dsp"}
_ALLOWED_ENVIRONMENTS = {"live", "test", "dev", "backup", "other"}


@dataclass(frozen=True)
class ServerProfile:
    profile_id: int
    name: str
    environment: str
    family: str
    server_root: str
    enabled: bool
    notes: str
    is_active: bool = False

    @property
    def root_path(self) -> Path:
        return Path(self.server_root).expanduser()

    def public_dict(self) -> dict:
        return {
            "profile_id": self.profile_id,
            "name": self.name,
            "environment": self.environment,
            "family": self.family,
            "server_root": self.server_root,
            "enabled": self.enabled,
            "notes": self.notes,
            "is_active": self.is_active,
        }


def connect(path: Path | str = DATABASE_PATH) -> sqlite3.Connection:
    con = sqlite3.connect(str(path))
    con.row_factory = sqlite3.Row
    init_db(con)
    return con


def _schema_ready(con: sqlite3.Connection) -> bool:
    """Return True when the profile schema is already usable without taking a write lock.

    Profile lookups are on hot read paths such as Entity Profile.  Running DDL plus
    ``INSERT OR IGNORE`` for every read turns those lookups into SQLite writers and can collide
    with an existing transaction on the shared toolkit database.  Keep the common initialized
    path strictly read-only and reserve schema writes for first-time setup/repair.
    """
    rows = con.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type='table' AND name IN ('server_profiles', 'server_profile_state')
        """
    ).fetchall()
    if {str(row[0]) for row in rows} != {"server_profiles", "server_profile_state"}:
        return False
    row = con.execute(
        "SELECT 1 FROM server_profile_state WHERE singleton=1"
    ).fetchone()
    return row is not None


def init_db(con: sqlite3.Connection) -> None:
    if _schema_ready(con):
        return
    con.executescript(
        """
        CREATE TABLE IF NOT EXISTS server_profiles (
            profile_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE COLLATE NOCASE,
            environment TEXT NOT NULL DEFAULT 'other',
            family TEXT NOT NULL DEFAULT 'auto',
            server_root TEXT NOT NULL,
            enabled INTEGER NOT NULL DEFAULT 1 CHECK(enabled IN (0,1)),
            notes TEXT NOT NULL DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS server_profile_state (
            singleton INTEGER PRIMARY KEY CHECK(singleton = 1),
            active_profile_id INTEGER NULL,
            FOREIGN KEY(active_profile_id) REFERENCES server_profiles(profile_id)
        );

        INSERT OR IGNORE INTO server_profile_state(singleton, active_profile_id)
        VALUES (1, NULL);
        """
    )
    con.commit()


def _clean_family(value: str) -> str:
    family = (value or "auto").strip().lower()
    if family not in _ALLOWED_FAMILIES:
        raise ValueError(f"Unsupported server family {value!r}; expected one of {sorted(_ALLOWED_FAMILIES)}")
    return family


def _clean_environment(value: str) -> str:
    environment = (value or "other").strip().lower()
    if environment not in _ALLOWED_ENVIRONMENTS:
        raise ValueError(
            f"Unsupported environment {value!r}; expected one of {sorted(_ALLOWED_ENVIRONMENTS)}"
        )
    return environment


def _clean_name(value: str) -> str:
    name = (value or "").strip()
    if not name:
        raise ValueError("Server profile name is required")
    if len(name) > 80:
        raise ValueError("Server profile name must be 80 characters or fewer")
    return name


def _clean_root(value: str | Path) -> str:
    root = str(Path(value).expanduser()) if str(value).strip() else ""
    if not root:
        raise ValueError("Server root path is required")
    return root


def _row_to_profile(row: sqlite3.Row, active_id: int | None) -> ServerProfile:
    return ServerProfile(
        profile_id=int(row["profile_id"]),
        name=str(row["name"]),
        environment=str(row["environment"]),
        family=str(row["family"]),
        server_root=str(row["server_root"]),
        enabled=bool(row["enabled"]),
        notes=str(row["notes"] or ""),
        is_active=int(row["profile_id"]) == active_id,
    )


def _active_id(con: sqlite3.Connection) -> int | None:
    init_db(con)
    row = con.execute(
        "SELECT active_profile_id FROM server_profile_state WHERE singleton=1"
    ).fetchone()
    return int(row[0]) if row and row[0] is not None else None


def list_profiles(con: sqlite3.Connection, *, include_disabled: bool = True) -> list[ServerProfile]:
    init_db(con)
    sql = "SELECT * FROM server_profiles"
    params: tuple = ()
    if not include_disabled:
        sql += " WHERE enabled=1"
    sql += " ORDER BY enabled DESC, name COLLATE NOCASE, profile_id"
    active_id = _active_id(con)
    return [_row_to_profile(row, active_id) for row in con.execute(sql, params).fetchall()]


def get_profile(con: sqlite3.Connection, profile_id: int) -> ServerProfile | None:
    init_db(con)
    row = con.execute("SELECT * FROM server_profiles WHERE profile_id=?", (int(profile_id),)).fetchone()
    return _row_to_profile(row, _active_id(con)) if row else None


def create_profile(
    con: sqlite3.Connection,
    *,
    name: str,
    server_root: str | Path,
    family: str = "auto",
    environment: str = "other",
    enabled: bool = True,
    notes: str = "",
    make_active: bool = False,
) -> ServerProfile:
    init_db(con)
    cur = con.execute(
        """
        INSERT INTO server_profiles(name, environment, family, server_root, enabled, notes)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            _clean_name(name),
            _clean_environment(environment),
            _clean_family(family),
            _clean_root(server_root),
            1 if enabled else 0,
            (notes or "").strip(),
        ),
    )
    profile_id = int(cur.lastrowid)
    if make_active:
        con.execute(
            "UPDATE server_profile_state SET active_profile_id=? WHERE singleton=1",
            (profile_id,),
        )
    con.commit()
    profile = get_profile(con, profile_id)
    assert profile is not None
    return profile


def update_profile(
    con: sqlite3.Connection,
    profile_id: int,
    *,
    name: str,
    server_root: str | Path,
    family: str = "auto",
    environment: str = "other",
    enabled: bool = True,
    notes: str = "",
) -> ServerProfile:
    init_db(con)
    profile_id = int(profile_id)
    if get_profile(con, profile_id) is None:
        raise KeyError(f"Unknown server profile {profile_id}")
    con.execute(
        """
        UPDATE server_profiles
        SET name=?, environment=?, family=?, server_root=?, enabled=?, notes=?
        WHERE profile_id=?
        """,
        (
            _clean_name(name),
            _clean_environment(environment),
            _clean_family(family),
            _clean_root(server_root),
            1 if enabled else 0,
            (notes or "").strip(),
            profile_id,
        ),
    )
    if not enabled and _active_id(con) == profile_id:
        con.execute("UPDATE server_profile_state SET active_profile_id=NULL WHERE singleton=1")
    con.commit()
    profile = get_profile(con, profile_id)
    assert profile is not None
    return profile


def set_active_profile(con: sqlite3.Connection, profile_id: int | None) -> ServerProfile | None:
    init_db(con)
    if profile_id is None:
        con.execute("UPDATE server_profile_state SET active_profile_id=NULL WHERE singleton=1")
        con.commit()
        return None
    profile = get_profile(con, int(profile_id))
    if profile is None:
        raise KeyError(f"Unknown server profile {profile_id}")
    if not profile.enabled:
        raise ValueError("Disabled server profiles cannot be selected")
    con.execute(
        "UPDATE server_profile_state SET active_profile_id=? WHERE singleton=1",
        (int(profile_id),),
    )
    con.commit()
    return get_profile(con, int(profile_id))


def get_active_profile(con: sqlite3.Connection) -> ServerProfile | None:
    active_id = _active_id(con)
    if active_id is None:
        return None
    profile = get_profile(con, active_id)
    if profile is None or not profile.enabled:
        return None
    return profile


def delete_profile(con: sqlite3.Connection, profile_id: int) -> None:
    init_db(con)
    profile_id = int(profile_id)
    if _active_id(con) == profile_id:
        con.execute("UPDATE server_profile_state SET active_profile_id=NULL WHERE singleton=1")
    con.execute("DELETE FROM server_profiles WHERE profile_id=?", (profile_id,))
    con.commit()


def seed_legacy_profiles(
    con: sqlite3.Connection,
    candidates: Iterable[tuple[str, str | Path | None, str]],
    *,
    active_name: str | None = None,
) -> list[ServerProfile]:
    """Import existing single-path settings without depending on the legacy settings module.

    ``candidates`` contains ``(friendly_name, root, family)`` tuples. Existing profile names are
    left untouched, making this safe to call repeatedly during a future compatibility migration.
    """
    init_db(con)
    existing = {p.name.casefold(): p for p in list_profiles(con)}
    for name, root, family in candidates:
        if not root or name.casefold() in existing:
            continue
        created = create_profile(
            con,
            name=name,
            server_root=root,
            family=family,
            environment="other",
            enabled=True,
        )
        existing[created.name.casefold()] = created
    if active_name:
        selected = existing.get(active_name.casefold())
        if selected and selected.enabled:
            set_active_profile(con, selected.profile_id)
    return list_profiles(con)
