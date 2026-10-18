# WikiWikiJP pilot crawl and retrieval provenance

## Storage (no new format)

`reference_wiki_documents` already holds `raw_source` + `raw_hash`. This change adds two nullable columns,
migrated in place by `wiki_document.init_db`:

- `retrieved_at`: UTC ISO-8601 fetch time. Set by the WikiWikiJP crawler and the FFXIclopedia importer. A re-fetch
  of identical source refreshes only this column (and `source_revision` if supplied); block ids and `parsed_at` stay put.
- `source_revision`: wiki revision id or equivalent stamp when the source exposes one. Left NULL otherwise.
  PukiWiki (WikiWikiJP) has no revision id; a Last-Modified header or page edit stamp is a candidate, but is not
  captured yet because `scrape_wikiwiki_jp.get()` returns only the body.

Existing rows keep NULL for both (unknown, not backfilled or guessed). BG dump import is not changed.

## Pilot (not yet run)

The crawler only accepts batch sizes of 50 or 250 and `refresh` mode needs pages already cached, so the smallest
real pilot is a `refresh` of one cached subtree at limit 50:

1. In the Wiki tab, pick a seed with cached WikiWikiJP pages (for example a mission or NM index subtree), mode `refresh`, batch 50.
   The existing 637 pages have no raw source, so refresh stores raw HTML and parsed blocks for them. Polite crawler, anti-bot
   challenges stop the job for manual resume.
2. Check: `SELECT COUNT(*) FROM reference_wiki_documents WHERE source_id='WikiWikiJP' AND raw_source<>'' AND retrieved_at IS NOT NULL`.
3. Query block types for those pages (`reference_wiki_blocks`): look for `table_*`, definition-like rows and labels from the
   Japanese policy (ドロップ, 報酬, 出現条件 and so on).
4. Add 3 to 5 minimal excerpts to `test_fixtures/wiki_corpus/` via `scripts/wiki_corpus_extract.py` (extend `SPECS`),
   replacing the synthetic WikiWikiJP samples where real ones exist.

Decision gate after the pilot: if tables and labels survive in the HTML blocks, re-crawl the rest; if not, the
fix is in `html_blocks`, not in storage.
