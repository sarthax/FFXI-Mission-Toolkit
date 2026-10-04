"""Deterministic source-native links for indexed FFXI server SQL records.

These links describe relationships already encoded by source schemas. They are
presentation/navigation evidence only and are not inserted into the canonical graph.
"""
from __future__ import annotations

import re
import sqlite3

_SERVER_PREFIXES=("sql","lsb","topaz","dsp")
_ITEM_DETAIL_SUFFIXES={"item_equipment","item_weapon","item_usable"}
_SAFE_IDENTIFIER=re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_SINGLE_KEY_COLUMNS=(
    "itemid","npcid","mobid","keyitem_id","zoneid","id","spellid","abilityid",
    "weaponskillid","traitid","poolid","groupid","instanceid","petid","mob_skill_id",
)


def _family_prefix(table: str) -> tuple[str,str] | None:
    for prefix in _SERVER_PREFIXES:
        marker=prefix+"_"
        if table.startswith(marker):
            return prefix,table[len(marker):]
    return None


def _table_exists(con: sqlite3.Connection, table: str) -> bool:
    if not _SAFE_IDENTIFIER.fullmatch(str(table or "")):
        return False
    return con.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone() is not None


def _columns(con: sqlite3.Connection, table: str) -> set[str]:
    if not _table_exists(con,table):
        return set()
    try:
        return {row[1].lower() for row in con.execute(f"PRAGMA table_info({table})")}
    except sqlite3.DatabaseError:
        return set()


def _identity_value(identity: dict[str,object], *names: str):
    folded={str(key).casefold():value for key,value in identity.items()}
    for name in names:
        if name.casefold() in folded:
            return folded[name.casefold()]
    return None


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


def _rows(
    con: sqlite3.Connection,
    table: str,
    select: tuple[str,...],
    where: dict[str,object],
    *,
    limit: int = 500,
):
    """Return a bounded deterministic row set for one schema-native non-unique relationship."""
    cols=_columns(con,table)
    if not set(column.lower() for column in (*select,*where)).issubset(cols):
        return []
    clause=" AND ".join(f"CAST({column} AS TEXT)=?" for column in where)
    order=",".join(select)
    return con.execute(
        f"SELECT {','.join(select)} FROM {table} WHERE {clause} ORDER BY {order} LIMIT ?",
        (*tuple(str(value) for value in where.values()),int(limit)),
    ).fetchall()


def _reference_mapping_link(
    con: sqlite3.Connection,
    source_table: str,
    source_identity: dict[str,object],
) -> list[dict]:
    """Resolve an explicitly mapped wiki claim to one exact indexed target, or fail closed."""
    if source_table!="reference_wiki_mappings":
        return []
    mapping_id=_identity_value(source_identity,"mapping_id")
    if mapping_id is None:
        return []
    row=_single_row(
        con,source_table,("target_table","target_key","mapping_status"),{"mapping_id":mapping_id},
    )
    if not row or str(row[2] or "").upper()!="MAPPED":
        return []
    target_table=str(row[0] or "")
    target_key=row[1]
    if target_key in (None,"") or not _table_exists(con,target_table):
        return []
    cols=_columns(con,target_table)
    identity_candidates=[column for column in _SINGLE_KEY_COLUMNS if column in cols]
    if len(identity_candidates)!=1:
        return []
    identity_column=identity_candidates[0]
    target=_single_row(con,target_table,(identity_column,),{identity_column:target_key})
    if not target:
        return []
    return [{
        "relationship":"REFERENCE_MAPPING_TARGET",
        "target_table":target_table,
        "target_identity":{identity_column:target[0]},
        "basis":"reference_wiki_mappings MAPPED target_table + target_key uniquely resolves",
    }]


def server_source_links(
    con: sqlite3.Connection,
    source_table: str,
    source_identity: dict[str,object],
) -> list[dict]:
    """Return deterministic target identities for a supported indexed source record."""
    reference_links=_reference_mapping_link(con,source_table,source_identity)
    if reference_links:
        return reference_links

    family=_family_prefix(source_table)
    if family is None:
        return []
    prefix,suffix=family
    links=[]

    itemid=_identity_value(source_identity,"itemid")
    if suffix in _ITEM_DETAIL_SUFFIXES and itemid is not None:
        links.append({
            "relationship":"ITEM_DETAIL_FOR",
            "target_table":f"{prefix}_item_basic",
            "target_identity":{"itemid":itemid},
            "basis":"same itemid in source schema",
        })

    if suffix=="mob_groups":
        zoneid=_identity_value(source_identity,"zoneid")
        groupid=_identity_value(source_identity,"groupid")
        if zoneid is not None and groupid is not None:
            row=_single_row(
                con,source_table,("poolid","dropid"),
                {"zoneid":zoneid,"groupid":groupid},
            )
            if row and row[0] is not None:
                links.append({
                    "relationship":"GROUP_USES_POOL",
                    "target_table":f"{prefix}_mob_pools",
                    "target_identity":{"poolid":row[0]},
                    "basis":"mob_groups.poolid",
                })
            if row and row[1] not in (None,0,"0"):
                drop_table=f"{prefix}_mob_droplist"
                drop_columns=("dropid","dropType","groupId","groupRate","itemId","itemRate")
                for drop_row in _rows(con,drop_table,drop_columns,{"dropid":row[1]}):
                    links.append({
                        "relationship":"GROUP_HAS_DROP",
                        "target_table":drop_table,
                        "target_identity":dict(zip(drop_columns,drop_row)),
                        "basis":"mob_groups.dropid -> mob_droplist.dropid",
                    })

    if suffix=="mob_droplist":
        item_id=_identity_value(source_identity,"itemId","itemid")
        if item_id not in (None,0,"0"):
            item_table=f"{prefix}_item_basic"
            if _single_row(con,item_table,("itemid",),{"itemid":item_id}):
                links.append({
                    "relationship":"DROP_GIVES_ITEM",
                    "target_table":item_table,
                    "target_identity":{"itemid":item_id},
                    "basis":"mob_droplist.itemId -> item_basic.itemid",
                })

    if suffix=="blue_spell_list":
        spellid=_identity_value(source_identity,"spellid")
        if spellid is not None:
            row=_single_row(con,source_table,("mob_skill_id",),{"spellid":spellid})
            if row and row[0] is not None:
                links.append({
                    "relationship":"BLUE_SPELL_SPELL",
                    "target_table":f"{prefix}_spell_list",
                    "target_identity":{"spellid":spellid},
                    "basis":"blue_spell_list.spellid",
                })
                links.append({
                    "relationship":"BLUE_SPELL_MOB_SKILL",
                    "target_table":f"{prefix}_mob_skills",
                    "target_identity":{"mob_skill_id":row[0]},
                    "basis":"blue_spell_list.mob_skill_id",
                })

    if suffix=="instance_entities":
        instanceid=_identity_value(source_identity,"instanceid")
        entity_id=_identity_value(source_identity,"id")
        if instanceid is not None:
            links.append({
                "relationship":"INSTANCE_MEMBER_OF",
                "target_table":f"{prefix}_instance_list",
                "target_identity":{"instanceid":instanceid},
                "basis":"instance_entities.instanceid",
            })
        if entity_id is not None:
            npc_table=f"{prefix}_npc_list"
            npc_row=_single_row(con,npc_table,("npcid",),{"npcid":entity_id})
            if npc_row:
                links.append({
                    "relationship":"INSTANCE_ENTITY_NPC",
                    "target_table":npc_table,
                    "target_identity":{"npcid":entity_id},
                    "basis":"instance_entities.id matches npc_list.npcid",
                })
            mob_table=f"{prefix}_mob_spawn_points"
            mob_row=_single_row(con,mob_table,("mobid",),{"mobid":entity_id})
            if mob_row:
                links.append({
                    "relationship":"INSTANCE_ENTITY_MOB",
                    "target_table":mob_table,
                    "target_identity":{"mobid":entity_id},
                    "basis":"instance_entities.id matches mob_spawn_points.mobid",
                })

    if suffix=="pet_list":
        petid=_identity_value(source_identity,"petid")
        if petid is not None:
            row=_single_row(con,source_table,("poolid",),{"petid":petid})
            if row and row[0] is not None:
                links.append({
                    "relationship":"PET_USES_POOL",
                    "target_table":f"{prefix}_mob_pools",
                    "target_identity":{"poolid":row[0]},
                    "basis":"pet_list.poolid",
                })

    if suffix=="mob_spawn_points":
        mobid=_identity_value(source_identity,"mobid")
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
