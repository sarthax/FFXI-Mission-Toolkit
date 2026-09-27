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
    detail_columns: tuple[str, ...] = ()
    inspect_path: str | None = None
    key_columns: tuple[str, ...] = ()

    def identity_columns(self) -> tuple[str, ...]:
        return self.key_columns or (self.id_column,)

@dataclass(frozen=True)
class CatalogProvider:
    provider_id: str
    domain: str
    tables: tuple[CatalogTable, ...]

@dataclass(frozen=True)
class CatalogLink:
    source_table: str
    source_column: str
    target_table: str
    target_column: str
    relationship: str

_COMMON_SERVER_TABLES=(
    CatalogTable("item_basic","itemid","name","ITEM"),
    CatalogTable("item_equipment","itemid","name","ITEM_EQUIPMENT"),
    CatalogTable("item_weapon","itemid","name","ITEM_WEAPON"),
    CatalogTable("item_usable","itemid","name","ITEM_USABLE"),
    CatalogTable("npc_list","npcid","name","NPC"),
    CatalogTable("mob_spawn_points","mobid","mobname","MOB"),
    CatalogTable("mob_groups","groupid","name","MOB_GROUP",key_columns=("zoneid","groupid")),
    CatalogTable("mob_pools","poolid","name","MOB_POOL"),
    CatalogTable("instance_list","instanceid","instance_name","INSTANCE"),
    CatalogTable("spell_list","spellid","name","SPELL"),
    CatalogTable("abilities","abilityid","name","ABILITY"),
    CatalogTable("weapon_skills","weaponskillid","name","WEAPON_SKILL"),
    CatalogTable("traits","traitid","name","TRAIT"),
)

def _prefixed(prefix: str) -> tuple[CatalogTable,...]:
    return tuple(CatalogTable(f"{prefix}_{t.table}",t.id_column,t.name_column,t.object_type,t.detail_columns,t.inspect_path,t.key_columns) for t in _COMMON_SERVER_TABLES)

PROVIDERS=(
    CatalogProvider("server-sql","server",_prefixed("sql")),
    CatalogProvider("landsandboat","server",_prefixed("lsb")),
    CatalogProvider("topaz","server",_prefixed("topaz")),
    CatalogProvider("dsp","server",_prefixed("dsp")),
    CatalogProvider("client-identity","client",(
        CatalogTable("identity_snapshots","snapshot_id","version","CLIENT_SNAPSHOT",
                     ("snapshot_type","family","recorded_at","source_location","fingerprint"),
                     "/clientoverview"),
        CatalogTable("identity_records","record_id","semantic_key","CLIENT_IDENTITY",
                     ("snapshot_id","namespace","numeric_id","zone_key","actor_key","confidence","evidence_id"),
                     "/clientoverview"),
    )),
    CatalogProvider("captures","runtime",(
        CatalogTable("captures","capture_id","capture_label","CAPTURE",
                     ("capturer","content_type","zones","mission_name","client_build","is_retail","start_time"),
                     "/captures/{id}"),
    )),
    CatalogProvider("research","research",(
        CatalogTable("research_sessions","research_session_id","question","RESEARCH_SESSION",
                     ("provider","model","permission_profile","feature_root","entity_root","verification_state","created_at","updated_at"),
                     "/research/{id}"),
        CatalogTable("research_proposals","proposal_id","subject_id","RESEARCH_PROPOSAL",
                     ("research_session_id","proposal_type","status","verification_requirement"),
                     None),
    )),
    CatalogProvider("validation","validation",(
        CatalogTable("validation_runs","run_id","name","VALIDATION_RUN",
                     ("status","feature_id","source_snapshot_id","target_snapshot_id","started_at","finished_at"),
                     "/validation/runs/{id}"),
        CatalogTable("validation_results","validation_id","validation_type","VALIDATION_RESULT",
                     ("run_id","subject_id","status","evidence_id","source","target"),
                     "/validation/runs"),
    )),
    CatalogProvider("packages","packages",(
        CatalogTable("migrations","migration_id","feature_id","MIGRATION",
                     ("source_snapshot_id","target_snapshot_id","status"),
                     "/packages"),
        CatalogTable("migration_actions","action_id","action","MIGRATION_ACTION",
                     ("migration_id","artifact_id","status","reason"),
                     "/packages"),
        CatalogTable("package_scope_reviews","migration_id","status","PACKAGE_SCOPE_REVIEW",
                     ("reviewed_at","scope_hash"),
                     "/packages/review"),
    )),
)

def provider_tables():
    return {table.table:(provider,table) for provider in PROVIDERS for table in provider.tables}


PROVIDER_LINKS=(
    CatalogLink("identity_records","snapshot_id","identity_snapshots","snapshot_id","IN_CLIENT_SNAPSHOT"),
    CatalogLink("research_proposals","research_session_id","research_sessions","research_session_id","FROM_RESEARCH_SESSION"),
    CatalogLink("validation_results","run_id","validation_runs","run_id","FROM_VALIDATION_RUN"),
    CatalogLink("migration_actions","migration_id","migrations","migration_id","IN_MIGRATION"),
    CatalogLink("package_scope_reviews","migration_id","migrations","migration_id","REVIEWS_MIGRATION"),
)
