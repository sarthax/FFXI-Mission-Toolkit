"""Offline Wiki-to-Feature-Trace acceptance smoke over attributed real excerpts.

These are minimal fixture extracts, not whole-page or GUI acceptance.
Run: PYTHONPATH=src:. python test_fixtures/test_wiki_trace_real_corpus_acceptance.py
"""
from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from workbench.devtools.features.trace_dossier import build_dossier
from workbench.devtools.reference.wiki_document import mediawiki_blocks

MANIFEST=Path(__file__).parent/"wiki_corpus"/"real_manifest.json"
CASES={"bg-nm-medusa":"Medusa","bg-nm-absolute-virtue":"Absolute Virtue"}


def main():
    samples={s["sample_id"]:s for s in json.loads(MANIFEST.read_text(encoding="utf-8"))["samples"]}
    for sample_id, expected_title in CASES.items():
        sample=samples[sample_id]
        assert sample["evidence_type"]=="real_excerpt" and sample["source_wiki"]=="BGWiki"
        assert sample["page_title"]==expected_title and sample["page_id"] and sample["revision_id"]
        blocks=mediawiki_blocks(sample["page_id"],sample["excerpt_wikitext"])
        field=next((b for b in blocks if b["block_type"]=="template_field"
                    and b.get("source_locator")),None)
        assert field is not None,(sample_id,blocks)
        root=(f"catalog:reference_wiki_blocks:source_id={sample['source_wiki']}"
              f"&page_id={sample['page_id']}&block_id={field['block_id']}")
        result={"root":root,"nodes":[{"node_id":root,"known":True,"representations":[{
            "node_type":"REFERENCE_BLOCK","display_name":field["text"],
            "metadata":{"provider":"reference-wiki",
                        "identity":{"source_id":sample["source_wiki"],"page_id":sample["page_id"],
                                    "block_id":field["block_id"]},
                        "details":{"section_path":field["section_path"],
                                   "source_locator":field["source_locator"]}}}]}],
            "edges":[],"provider_relationships":[]}
        dossier=build_dossier(result)
        evidence=dossier["wiki_section_evidence"]
        assert evidence["review_only"] and evidence["locator"]==field["source_locator"]
        parsed=urlsplit(evidence["browse_href"])
        qs=parse_qs(parsed.query)
        assert parsed.path=="/wiki" and qs["source"]==["BGWiki"]
        assert qs["page_id"]==[str(sample["page_id"])] and qs["tab"]==["browse"]
        assert dossier["semantic_relationship_count"]==0
        print(f"{expected_title}: attributed excerpt -> trace locator -> exact Wiki route: PASS")
    print("Offline Wiki Trace real-corpus smoke: PASS; live GUI acceptance NOT performed")


if __name__=="__main__":
    main()
