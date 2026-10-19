"""Read-only inventory of a Wiki database (baseline/after). py -3.11 scripts/wiki_inventory.py DB OUT.json"""
import json, sqlite3, sys, time
db, out = sys.argv[1:3]
c = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
q = lambda s, *a: c.execute(s, a).fetchall()
inv = {"db": db, "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "sources": {}}
for (sid,) in q("select distinct source_id from reference_wiki_pages order by 1"):
    d = {}
    d["pages"] = q("select count(*) from reference_wiki_pages where source_id=?", sid)[0][0]
    d["docs"] = q("select count(*) from reference_wiki_documents where source_id=?", sid)[0][0]
    d["docs_with_raw"] = q("select count(*) from reference_wiki_documents where source_id=? and raw_source is not null and trim(raw_source)!=''", sid)[0][0]
    d["docs_empty_raw"] = d["docs"] - d["docs_with_raw"]
    d["pages_without_doc"] = q("select count(*) from reference_wiki_pages p where source_id=? and not exists(select 1 from reference_wiki_documents d where d.source_id=p.source_id and d.page_id=p.page_id)", sid)[0][0]
    d["pages_with_blocks"] = q("select count(distinct page_id) from reference_wiki_blocks where source_id=?", sid)[0][0]
    d["parser_versions"] = dict(q("select parser_version,count(*) from reference_wiki_documents where source_id=? group by 1", sid))
    d["source_formats"] = dict(q("select source_format,count(*) from reference_wiki_documents where source_id=? group by 1", sid))
    d["blocks_by_type"] = dict(q("select block_type,count(*) from reference_wiki_blocks where source_id=? group by 1", sid))
    d["missing_retrieved_at"] = q("select count(*) from reference_wiki_documents where source_id=? and retrieved_at is null", sid)[0][0]
    d["missing_revision"] = q("select count(*) from reference_wiki_pages where source_id=? and (revision_id is null or revision_id='')", sid)[0][0] if "revision_id" in [r[1] for r in c.execute("pragma table_info(reference_wiki_pages)")] else None
    d["blocks_without_locator"] = q("select count(*) from reference_wiki_blocks where source_id=? and (source_locator is null or source_locator='')", sid)[0][0]
    inv["sources"][sid] = d
inv["preserved_tables"] = {t: q(f"select count(*) from {t}")[0][0] for t in (
    "reference_wiki_claims", "reference_wiki_mappings", "reference_wiki_mapping_reviews", "reference_wiki_page_alignments",
    "reference_wiki_claim_alignments", "reference_wiki_relations", "reference_wiki_relation_mappings", "reference_wiki_aliases",
    "reference_wiki_topics", "reference_wiki_topic_pages", "reference_wiki_translations", "reference_wiki_pages")}
inv["raw_hash_checksum"] = q("select count(*), sum(length(raw_source)), group_concat(substr(raw_hash,1,2)) is not null from reference_wiki_documents")[0][:2]
inv["jobs"] = {}
for t in ("wiki_bulk_jobs", "wiki_bg_dump_jobs", "wiki_jp_crawl_jobs"):
    try:
        inv["jobs"][t] = {"states": dict(q(f"select state,count(*) from {t} group by 1")), "errors": q(f"select count(*) from {t} where last_error is not null and last_error!=''")[0][0]}
    except Exception as e:
        inv["jobs"][t] = str(e)
json.dump(inv, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(json.dumps(inv, ensure_ascii=False)[:3000])
