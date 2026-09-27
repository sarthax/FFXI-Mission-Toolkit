"""Explicit catalog-provider registry for Feature Trace.

Providers describe identities already indexed by the Workbench. They do not create graph
relationships. Unknown/custom tables remain eligible for the compatibility fallback in
feature_trace_catalog.py.
"""
from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class CatalogTable:
    table: str
    id_column: str
    name_column: str
    object_type: str

@dataclass(frozen=True)
class CatalogProvider:
    provider_id: str
    domain: str
    tables: tuple[CatalogTable, ...]

_COMMON_SERVER_TABLES=(
    CatalogTable("item_basic","itemid","name","ITEM"),
    CatalogTable("item_equipment","itemid","name","ITEM_EQUIPMENT"),
    CatalogTable("item_weapon","itemid","name","ITEM_WEAPON"),
    CatalogTable("item_usable","itemid","name","ITEM_USABLE"),
    CatalogTable("npc_list","npcid","name","NPC"),
    CatalogTable("mob_spawn_points","mobid","mobname","MOB"),
    CatalogTable("mob_groups","groupid","name","MOB_GROUP"),
    CatalogTable("mob_pools","poolid","name","MOB_POOL"),
    CatalogTable("instance_list","instanceid","instance_name","INSTANCE"),
    CatalogTable("spell_list","spellid","name","SPELL"),
    CatalogTable("abilities","abilityid","name","ABILITY"),
    CatalogTable("weapon_skills","weaponskillid","name","WEAPON_SKILL"),
    CatalogTable("traits","traitid","name","TRAIT"),
)

def _prefixed(prefix: str) -> tuple[CatalogTable,...]:
    return tuple(CatalogTable(f"{prefix}_{t.table}",t.id_column,t.name_column,t.object_type) for t in _COMMON_SERVER_TABLES)

PROVIDERS=(
    CatalogProvider("server-sql","server",_prefixed("sql")),
    CatalogProvider("landsandboat","server",_prefixed("lsb")),
    CatalogProvider("topaz","server",_prefixed("topaz")),
    CatalogProvider("dsp","server",_prefixed("dsp")),
)

def provider_tables():
    return {table.table:(provider,table) for provider in PROVIDERS for table in provider.tables}
