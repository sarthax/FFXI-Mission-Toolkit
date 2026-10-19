"""Presentation-only Evidence Dossier for Feature Trace.

Summarizes evidence already present in a trace. It never infers missing relationships,
declares implementation completeness, or manufactures cross-source identity.
"""
from __future__ import annotations
from collections import Counter
from workbench.devtools.features.trace_catalog import relationship_section

FACET_ORDER=("Dependencies / Requirements","Acquisition / Progression","Implementation / Server","Client","Validation","Evidence / References","Other / Unclassified")

def build_dossier(result: dict) -> dict:
    root=result.get("root")
    root_node=next((n for n in result.get("nodes",()) if n.get("node_id")==root),None) or {"node_id":root,"known":False,"representations":[]}
    reps=root_node.get("representations") or []
    primary=reps[0] if reps else {}
    counts=Counter(relationship_section(edge) for edge in result.get("edges",()))
    facets=[{"name":name,"count":counts[name]} for name in FACET_ORDER if counts[name]]
    runtime=result.get("runtime_hierarchy") or {}
    provider_links=list(result.get("provider_relationships") or ())
    if runtime.get("observation_count",0):
        facets.append({"name":"Runtime / Captures & Packets","count":runtime["observation_count"],"capture_count":runtime.get("capture_count",0),"group_count":runtime.get("group_count",0)})
    wiki_links=[
        link for link in provider_links
        if link.get("adapter")=="reference-wiki" and
        link.get("relationship") in {
            "HAS_SOURCE_DOCUMENT","DOCUMENT_FOR_REFERENCE_PAGE",
            "IN_REFERENCE_PAGE","FROM_REFERENCE_PAGE","TOPIC_MEMBER_PAGE"
        }
    ]
    # Focused, literal source evidence for an inspected Wiki block/claim/relation.
    # Do not infer claims, validate accuracy, or synthesize missing locators.
    meta=primary.get("metadata") or {}
    details=meta.get("details") or {}
    wiki_evidence=None
    if meta.get("provider")=="reference-wiki" and primary.get("node_type") in {
        "REFERENCE_BLOCK","REFERENCE_CLAIM","REFERENCE_RELATION"
    }:
        wiki_evidence={
            "node_type":primary.get("node_type"),
            "section":details.get("section_path") or details.get("section_title"),
            "locator":details.get("source_locator"),
            "excerpt":details.get("excerpt") or (primary.get("display_name") if primary.get("node_type")=="REFERENCE_BLOCK" else None),
            "source_id":details.get("source_id"),
            "page_id":details.get("page_id"),
            "revision_id":details.get("revision_id"),
            "authority":details.get("authority"),
            "review_only":True,
        }
    if provider_links:
        facets.append({"name":"Source-native links","count":len(provider_links)})
    return {
        "identity":{"node_id":root,"known":bool(root_node.get("known")),"display_name":primary.get("display_name") or root,"node_type":primary.get("node_type") or "UNKNOWN","source_count":len(reps),"provider":(primary.get("metadata") or {}).get("provider"),"domain":(primary.get("metadata") or {}).get("domain"),"details":(primary.get("metadata") or {}).get("details") or {},"inspect_href":(primary.get("metadata") or {}).get("inspect_href"),"representations":reps},
        "facets":facets,
        "semantic_relationship_count":len(result.get("edges",())),
        "semantic_node_count":len(result.get("nodes",())),
        "runtime_observation_count":runtime.get("observation_count",0),
        "runtime_capture_count":runtime.get("capture_count",0),
        "runtime_group_count":runtime.get("group_count",0),
        "provider_relationship_count":len(provider_links),
        "provider_relationships":provider_links,
        "wiki_source_navigation":wiki_links,
        "wiki_section_evidence":wiki_evidence,
    }
