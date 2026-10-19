"""Evidence Dossier must prioritize exact Wiki source navigation, never graph authority."""
from workbench.devtools.features.trace_dossier import build_dossier

def main():
    wiki={"relationship":"HAS_SOURCE_DOCUMENT","adapter":"reference-wiki",
          "provider_native":True,"target_node":"catalog:reference_wiki_documents:source_id=BGWiki&page_id=42",
          "target_name":"BGWiki: 42 source document","target_type":"REFERENCE_DOCUMENT"}
    generic={"relationship":"GROUP_USES_POOL","adapter":"server",
             "target_node":"catalog:lsb_mob_pools:12"}
    trace={"root":"catalog:reference_wiki_pages:source_id=BGWiki&page_id=42",
           "nodes":[{"node_id":"catalog:reference_wiki_pages:source_id=BGWiki&page_id=42",
                     "known":True,"representations":[{"display_name":"BG page","node_type":"REFERENCE_PAGE",
                            "metadata":{"provider":"reference-wiki","domain":"reference"}}]}],
           "edges":[],"provider_relationships":[generic,wiki]}
    result=build_dossier(trace)
    assert result["wiki_source_navigation"]==[wiki], result
    assert result["provider_relationship_count"]==2
    assert result["semantic_relationship_count"]==0
    trace["provider_relationships"]=[generic]
    assert build_dossier(trace)["wiki_source_navigation"]==[]
    print("Feature Trace Wiki dossier source-first contract: PASS")

if __name__=="__main__":
    main()
