"""Focused Wiki section provenance must remain literal and review-only."""
from workbench.devtools.features.trace_dossier import build_dossier

def main():
    root="catalog:reference_wiki_blocks:source_id=WikiWikiJP&page_id=42&block_id=b1"
    result={"root":root,"edges":[],"provider_relationships":[],
        "nodes":[{"node_id":root,"known":True,"representations":[{
            "node_type":"REFERENCE_BLOCK","display_name":"原文の記述",
            "metadata":{"provider":"reference-wiki","identity":{"source_id":"WikiWikiJP","page_id":"42","block_id":"b1"},
                "details":{"section_path":"攻略 > 条件","source_locator":"section:攻略:block:1","block_type":"paragraph"}}}]}]}
    d=build_dossier(result)
    ev=d["wiki_section_evidence"]
    assert ev["source_id"]=="WikiWikiJP" and ev["page_id"]=="42",ev
    assert ev["section"]=="攻略 > 条件" and ev["locator"]=="section:攻略:block:1",ev
    assert ev["excerpt"]=="原文の記述" and ev["review_only"] is True,ev
    assert d["semantic_relationship_count"]==0 and d["provider_relationship_count"]==0
    result["nodes"][0]["representations"][0]["metadata"]["provider"]="server-sql"
    assert build_dossier(result)["wiki_section_evidence"] is None
    print("Wiki section Evidence Dossier contract: PASS")

if __name__=="__main__":
    main()
