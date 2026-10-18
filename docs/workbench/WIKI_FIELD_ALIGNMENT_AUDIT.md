# Wiki backlog: typed field alignment checkpoint (2026-10-18)

The current roadmap's Wiki V2 priorities are **not** a missing scraper from scratch. The existing `wiki_document` parser preserves MediaWiki blocks, template field raw values, and source locators. Named English and Japanese template fields and explicit two-column table labels can yield **review-only** candidates. Unrecognized prose must not become a trusted drop, reward, spawn, quest, or requirement edge.

## Initial offline contract

`test_fixtures/test_wiki_field_alignment_contract.py` exercises a mixed-language MediaWiki sample:

- English `Drops` and Japanese `必要条件` template fields map to conservative typed review candidates.
- Raw Japanese markup and source locators survive extraction.
- `Notes` and `備考` prose is excluded from candidate promotion.
- Explicit two-column `Drops` and `報酬` table rows are review candidates, while a `Notes` row is not.
- All candidates remain `review_only`; the fixture does not assert graph edges, source truth, or actual scrape success.

This is **synthetic contract coverage**, not a real-source audit. The next step is to collect small, licensed/attributable real BG Wiki, FFXIclopedia, and WikiWikiJP examples, record source page/revision and field locators, and build a field-by-field matrix of recognized, ambiguous, and unsupported layouts. Avoid committing wholesale scraped pages or treating machine translation as source evidence.

## Remaining prioritized backlog

1. Real-source template/infobox/two-column-table sample matrix; add only explicitly evidenced allowlisted fields and regression fixtures.
2. JP original-label to English canonical-field review mapping, keeping Japanese source values authoritative.
3. Reviewed typed fields and topic/section links into Feature Trace source-native drill-down; no automatic trusted graph edges.
4. Page-history/freshness/schema audit against real DB versions; distinguish existing code from operational acceptance.
5. Selective recovery of flattened WikiWikiJP records and translation per-section UX.
6. Relationship graph view with separate wiki-only and independently confirmed edges.

Do not mark any of these items complete merely because this fixture passes.
