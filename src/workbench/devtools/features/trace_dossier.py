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
    }
