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

## Implementation increment

Template and two-column table candidates now share the exact-label `REVIEW_FIELD_TYPES` mapping in `wiki_document.py`. Table candidates include `field_type` in addition to the existing raw field/value and locators. The field map includes the existing conservative English and Japanese drops, rewards, location, requirement, spawn, quest, and NM-identity labels. Unknown labels still do not become typed candidates. No schema migration, graph promotion, or translation-based authority change is involved.

## Column-header semantics (table candidates)

A table row made only of header cells now types the cells beneath each policy-labelled header
(review-only, `orientation: "column"`, with `column_index` and `header_row_index`). Previously the first two cells of a
header row were paired (`エリア` -> `NPC`), which used a header as a value. Row-style pairs (first cell label, second
cell value) are unchanged and now carry `orientation: "row"`. Historical v3 limitation: rowspan/colspan tables were indexed positionally. The merged v6 HTML parser now aligns physical columns; #1110 adds focused span regressions.

## Merged HTML cell alignment reconciliation (2026-10-19)

The current `main` parser already uses `wiki-doc-v6-html-table-spans`, retaining original cell/source locators and assigning physical columns across `rowspan` and `colspan`. The older draft PR #1106 used a separate `wiki-doc-v6-table-spans` implementation; it must not replace the newer code. Regression coverage pins a Japanese-style two-row rowspan and a colspan column-header case, ensuring only review-only candidates are emitted and coordinate cells are not mislabeled as areas. Remaining limitations around blank cells and compound header interpretation are unchanged.

## Reconciliation checkpoint (2026-10-19)

Merged #1098 (table attributes), #1099 (simple wrapper text), #1101 (JP physical-column rowspan/colspan), and #1110 (reconciled span tests) address previously documented parser-level deficiencies. The remaining open work is actual source and database acceptance: full JP/FFXIclopedia structured retention, missing/blank cells and multi-level headers, reviewed per-source label mappings, Feature Trace source-native drill-down, freshness inspection and translation UX. Preserve original-language values and the review-only boundary. See `WIKI_REAL_SOURCE_CORPUS.md` for the distinction between the historical local DB and current offline fixtures.
