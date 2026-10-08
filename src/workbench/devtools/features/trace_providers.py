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
    name_column: str | None
    object_type: str
    detail_columns: tuple[str, ...] = ()
    inspect_path: str | None = None
    key_columns: tuple[str, ...] = ()
    search_columns: tuple[str, ...] = ()
    display_template: str | None = None

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
    CatalogTable("npc_list","npcid","name","NPC",
                 detail_columns=("zoneid","pos_x","pos_y","pos_z","pos_rot","look","status","flag")),
    CatalogTable("mob_spawn_points","mobid","mobname","MOB",
                 detail_columns=("groupid","pos_x","pos_y","pos_z","pos_rot")),
    CatalogTable("mob_groups","groupid","name","MOB_GROUP",
                 detail_columns=("poolid","dropid","respawntime","minLevel","maxLevel"),
                 key_columns=("zoneid","groupid"),
                 search_columns=("poolid","dropid")),
    CatalogTable("mob_pools","poolid","name","MOB_POOL",
                 detail_columns=("familyid","modelid"),
                 search_columns=("familyid","modelid")),
    # mob_droplist has no primary key in the upstream server schemas. Use the complete row as
    # its read-only catalog identity so Feature Trace can navigate deterministic group -> drop ->
    # item relationships without inventing a synthetic persistent ID.
    CatalogTable("mob_droplist","dropid",None,"MOB_DROP",
                 detail_columns=("dropType","groupId","groupRate","itemId","itemRate"),
                 key_columns=("dropid","dropType","groupId","groupRate","itemId","itemRate"),
                 search_columns=("itemId",),
                 display_template="Drop {dropid} item {itemId}"),
    CatalogTable("mob_skills","mob_skill_id","name","MOB_SKILL"),
    CatalogTable("pet_list","petid","name","PET"),
    CatalogTable("instance_list","instanceid","instance_name","INSTANCE"),
    CatalogTable("instance_entities","id",None,"INSTANCE_ENTITY",
                 key_columns=("instanceid","id"),
                 display_template="Instance {instanceid} entity {id}"),
    CatalogTable("spell_list","spellid","name","SPELL"),
    CatalogTable("blue_spell_list","spellid",None,"BLUE_SPELL_WIRING",
                 detail_columns=("mob_skill_id",),
                 search_columns=("mob_skill_id",),
                 display_template="Blue spell wiring {spellid}"),
    CatalogTable("abilities","abilityid","name","ABILITY"),
    CatalogTable("weapon_skills","weaponskillid","name","WEAPON_SKILL"),
    CatalogTable("traits","traitid","name","TRAIT"),
)

def _prefixed(prefix: str) -> tuple[CatalogTable,...]:
    return tuple(CatalogTable(f"{prefix}_{t.table}",t.id_column,t.name_column,t.object_type,t.detail_columns,t.inspect_path,t.key_columns,t.search_columns,t.display_template) for t in _COMMON_SERVER_TABLES)


def _common_server_links(prefix: str) -> tuple[CatalogLink, ...]:
    """Exact cross-table links shared by supported server SQL lineages."""
    return (
        CatalogLink(f"{prefix}_item_equipment","itemid",f"{prefix}_item_basic","itemid","EXTENDS_ITEM_BASIC"),
        CatalogLink(f"{prefix}_item_weapon","itemid",f"{prefix}_item_basic","itemid","EXTENDS_ITEM_BASIC"),
        CatalogLink(f"{prefix}_item_usable","itemid",f"{prefix}_item_basic","itemid","EXTENDS_ITEM_BASIC"),
        CatalogLink(f"{prefix}_mob_groups","poolid",f"{prefix}_mob_pools","poolid","USES_MOB_POOL"),
        CatalogLink(f"{prefix}_blue_spell_list","mob_skill_id",f"{prefix}_mob_skills","mob_skill_id","USES_MOB_SKILL"),
    )

PROVIDERS=(
    CatalogProvider("server-sql","server",_prefixed("sql")),
    CatalogProvider("landsandboat","server",_prefixed("lsb")+(
        CatalogTable("lsb_effects","effectid","name","STATUS_EFFECT",search_columns=("display_name","norm_name")),
        CatalogTable("keyitems_ours","id","const_name","KEY_ITEM",search_columns=("norm_name",)),
    )),
    CatalogProvider("topaz","server",_prefixed("topaz")+(
        CatalogTable("topaz_effects","effectid","name","STATUS_EFFECT",search_columns=("norm_name",)),
        CatalogTable("topaz_keyitems","id","const_name","KEY_ITEM",search_columns=("norm_name",)),
    )),
    CatalogProvider("dsp","server",_prefixed("dsp")+(
        CatalogTable("dsp_effects","effectid","name","STATUS_EFFECT",search_columns=("norm_name",)),
    )),
    CatalogProvider("retail-reference","reference",(
        CatalogTable("keyitems_external","id","name","KEY_ITEM_REFERENCE",search_columns=("norm_name",)),
    )),
    CatalogProvider("reference-wiki","reference",(
        CatalogTable("reference_wiki_pages","page_id","title","REFERENCE_PAGE",
                     ("source_id","norm_title","revision_id","revision_timestamp","page_hash"),
                     "/wiki",key_columns=("source_id","page_id"),
                     search_columns=("title","norm_title","source_id"),
                     display_template="{source_id}: {page_id}"),
        CatalogTable("reference_wiki_blocks","block_id","text","REFERENCE_BLOCK",
                     ("source_id","page_id","ordinal","block_type","heading_level","section_path","target","source_locator"),
                     "/wiki",key_columns=("source_id","page_id","block_id"),
                     search_columns=("text","target","section_path","block_type")),
        CatalogTable("reference_wiki_topics","topic_id","canonical_title","REFERENCE_TOPIC",
                     ("norm_title",),"/wiki",search_columns=("canonical_title","norm_title")),
        CatalogTable("reference_wiki_topic_pages","topic_id",None,"REFERENCE_TOPIC_PAGE",
                     ("source_id","page_id","link_method"),"/wiki",
                     key_columns=("topic_id","source_id","page_id"),
                     search_columns=("topic_id","source_id","page_id","link_method"),
                     display_template="{topic_id} / {source_id}:{page_id}"),
        CatalogTable("reference_wiki_claims","claim_id","subject_text","REFERENCE_CLAIM",
                     ("source_id","page_id","page_title","revision_id","revision_timestamp","section_title",
                      "claim_type","excerpt","source_locator","authority"),
                     "/wiki",search_columns=("page_title","excerpt","section_title","source_id")),
        CatalogTable("reference_wiki_mappings","mapping_id","target_label","REFERENCE_MAPPING",
                     ("claim_id","target_domain","target_table","target_key","mapping_method",
                      "mapping_status","confidence"),
                     "/wiki",search_columns=("claim_id","target_table","target_key","mapping_status")),
        CatalogTable("reference_wiki_mapping_reviews","mapping_id","review_status","REFERENCE_MAPPING_REVIEW",
                     ("notes","reviewed_at"),"/wiki",search_columns=("review_status","notes")),
        CatalogTable("reference_wiki_page_alignments","alignment_id","norm_title","REFERENCE_PAGE_ALIGNMENT",
                     ("bg_page_id","ffxiclopedia_page_id","status","updated_at"),"/wiki",
                     search_columns=("status","bg_page_id","ffxiclopedia_page_id")),
        CatalogTable("reference_wiki_claim_alignments","pair_id","status","REFERENCE_CLAIM_ALIGNMENT",
                     ("alignment_id","bg_claim_id","ffxiclopedia_claim_id","alignment_type","similarity","conflict_kind"),
                     "/wiki",search_columns=("alignment_id","alignment_type","conflict_kind","status")),
    )),
    CatalogProvider("server-event-refs","server",(
        CatalogTable("npc_event_refs","csid",None,"SERVER_EVENT_REF",
                     key_columns=("source","zone_name","npc_script","csid"),
                     display_template="{source} {zone_name}/{npc_script} event {csid}"),
    )),
    CatalogProvider("client-identity","client",(
        CatalogTable("identity_snapshots","snapshot_id","version","CLIENT_SNAPSHOT",
                     ("snapshot_type","family","recorded_at","source_location","fingerprint"),
                     "/clientoverview",search_columns=("family","source_location","fingerprint")),
        CatalogTable("identity_records","record_id","semantic_key","CLIENT_IDENTITY",
                     ("snapshot_id","namespace","numeric_id","zone_key","actor_key","confidence","evidence_id"),
                     "/clientoverview",search_columns=("numeric_id","zone_key","actor_key","owner_key","evidence_id")),
    )),
    CatalogProvider("captures","runtime",(
        CatalogTable("captures","capture_id","capture_label","CAPTURE",
                     ("capturer","content_type","zones","mission_name","client_build","is_retail","start_time"),
                     "/captures/{id}",search_columns=("capturer","content_type","zones","mission_name","client_build")),
    )),
    CatalogProvider("research","research",(
        CatalogTable("research_sessions","research_session_id","question","RESEARCH_SESSION",
                     ("provider","model","permission_profile","feature_root","entity_root","verification_state","created_at","updated_at"),
                     "/research/{id}",search_columns=("provider","model","feature_root","entity_root","verification_state")),
        CatalogTable("research_proposals","proposal_id","subject_id","RESEARCH_PROPOSAL",
                     ("research_session_id","proposal_type","status","verification_requirement"),
                     None,search_columns=("research_session_id","proposal_type","status")),
    )),
    CatalogProvider("validation","validation",(
        CatalogTable("validation_runs","run_id","name","VALIDATION_RUN",
                     ("status","feature_id","source_snapshot_id","target_snapshot_id","started_at","finished_at"),
                     "/validation/runs/{id}",search_columns=("status","feature_id","source_snapshot_id","target_snapshot_id")),
        CatalogTable("validation_results","validation_id","validation_type","VALIDATION_RESULT",
                     ("run_id","subject_id","status","evidence_id","source","target"),
                     "/validation/runs",search_columns=("run_id","subject_id","status","evidence_id","source","target")),
    )),
    CatalogProvider("packages","packages",(
        CatalogTable("migrations","migration_id","feature_id","MIGRATION",
                     ("source_snapshot_id","target_snapshot_id","status"),
                     "/packages",search_columns=("source_snapshot_id","target_snapshot_id","status")),
        CatalogTable("migration_actions","action_id","action","MIGRATION_ACTION",
                     ("migration_id","artifact_id","status","reason"),
                     "/packages",search_columns=("migration_id","artifact_id","status","reason")),
        CatalogTable("package_scope_reviews","migration_id","status","PACKAGE_SCOPE_REVIEW",
                     ("reviewed_at","scope_hash"),
                     "/packages/review"),
    )),
)

def provider_tables():
    return {table.table:(provider,table) for provider in PROVIDERS for table in provider.tables}


PROVIDER_LINKS=(
    *(_common_server_links(prefix) for prefix in ()),
    *_common_server_links("sql"),
    *_common_server_links("lsb"),
    *_common_server_links("topaz"),
    *_common_server_links("dsp"),
    CatalogLink("identity_records","snapshot_id","identity_snapshots","snapshot_id","IN_CLIENT_SNAPSHOT"),
    CatalogLink("captures","client_build","identity_snapshots","version","CAPTURE_CLIENT_BUILD"),
    CatalogLink("research_proposals","research_session_id","research_sessions","research_session_id","FROM_RESEARCH_SESSION"),
    CatalogLink("validation_results","run_id","validation_runs","run_id","FROM_VALIDATION_RUN"),
    CatalogLink("migration_actions","migration_id","migrations","migration_id","IN_MIGRATION"),
    CatalogLink("package_scope_reviews","migration_id","migrations","migration_id","REVIEWS_MIGRATION"),
    CatalogLink("reference_wiki_blocks","page_id","reference_wiki_pages","page_id","IN_REFERENCE_PAGE"),
    CatalogLink("reference_wiki_claims","page_id","reference_wiki_pages","page_id","FROM_REFERENCE_PAGE"),
    CatalogLink("reference_wiki_topic_pages","topic_id","reference_wiki_topics","topic_id","IN_REFERENCE_TOPIC"),
    CatalogLink("reference_wiki_topic_pages","page_id","reference_wiki_pages","page_id","TOPIC_MEMBER_PAGE"),
    CatalogLink("reference_wiki_mappings","claim_id","reference_wiki_claims","claim_id","MAPS_REFERENCE_CLAIM"),
    CatalogLink("reference_wiki_mapping_reviews","mapping_id","reference_wiki_mappings","mapping_id","REVIEWS_REFERENCE_MAPPING"),
    CatalogLink("reference_wiki_claim_alignments","alignment_id","reference_wiki_page_alignments","alignment_id","IN_REFERENCE_PAGE_ALIGNMENT"),
    CatalogLink("reference_wiki_claim_alignments","bg_claim_id","reference_wiki_claims","claim_id","ALIGNS_BG_REFERENCE_CLAIM"),
    CatalogLink("reference_wiki_claim_alignments","ffxiclopedia_claim_id","reference_wiki_claims","claim_id","ALIGNS_FFXICLOPEDIA_REFERENCE_CLAIM"),
)
