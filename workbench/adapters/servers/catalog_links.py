"""Deterministic source-native links for indexed FFXI server SQL records.

These links describe relationships already encoded by the server schemas. They are
presentation/navigation evidence only and are not inserted into the canonical graph.
"""
from __future__ import annotations

import sqlite3

_SERVER_PREFIXES=("sql","lsb","topaz","dsp")
_ITEM_DETAIL_SUFFIXES={"item_equipment","item_weapon","item_usable"}


def _family_prefix(table: str) -> tuple[str,str] | None:
    for prefix in _SERVER_PREFIXES:
        marker=prefix+"_"
        if table.startswith(marker):
            return prefix,table[len(marker):]
    return None


def _columns(con: sqlite3.Connection, table: str) -> set[str]:
    try:
        return {row[1].lower() for row in con.execute(f"PRAGMA table_info({table})")}
    except sqlite3.DatabaseError:
        return set()


def _single_row(con: sqlite3.Connection, table: str, select: tuple[str,...], where: dict[str,object]):
    cols=_columns(con,table)
    if not set(column.lower() for column in (*select,*where)).issubset(cols):
        return None
    clause=" AND ".join(f"CAST({column} AS TEXT)=?" for column in where)
    rows=con.execute(
        f"SELECT {','.join(select)} FROM {table} WHERE {clause} LIMIT 2",
        tuple(str(value) for value in where.values()),
    ).fetchall()
    return rows[0] if len(rows)==1 else None


def server_source_links(
    con: sqlite3.Connection,
    source_table: str,
    source_identity: dict[str,object],
) -> list[dict]:
    """Return deterministic target identities for a supported indexed server record."""
    family=_family_prefix(source_table)
    if family is None:
        return []
    prefix,suffix=family
    links=[]

    if suffix in _ITEM_DETAIL_SUFFIXES and source_identity.get("itemid") is not None:
        links.append({
            "relationship":"ITEM_DETAIL_FOR",
            "target_table":f"{prefix}_item_basic",
            "target_identity":{"itemid":source_identity["itemid"]},
            "basis":"same itemid in source schema",
        })

    if suffix=="mob_groups":
        zoneid=source_identity.get("zoneid")
        groupid=source_identity.get("groupid")
        if zoneid is not None and groupid is not None:
            row=_single_row(
                con,source_table,("poolid",),
                {"zoneid":zoneid,"groupid":groupid},
            )
            if row and row[0] is not None:
                links.append({
                    "relationship":"GROUP_USES_POOL",
                    "target_table":f"{prefix}_mob_pools",
                    "target_identity":{"poolid":row[0]},
                    "basis":"mob_groups.poolid",
                })

    if suffix=="mob_spawn_points":
        mobid=source_identity.get("mobid")
        if mobid is not None:
            row=_single_row(con,source_table,("groupid",),{"mobid":mobid})
            if row and row[0] is not None:
                zoneid=(int(mobid)>>12)&0xFFF
                links.append({
                    "relationship":"SPAWN_USES_GROUP",
                    "target_table":f"{prefix}_mob_groups",
                    "target_identity":{"zoneid":zoneid,"groupid":row[0]},
                    "basis":"mob_spawn_points.groupid + zone decoded from entity id",
                })

    return links
