# Wiki V2 Real-Source Fixture Corpus

Offline regression corpus for Wiki V2 typed extraction. Runner: `test_fixtures/test_wiki_corpus.py`
(wired into Workbench Regression). Data: `test_fixtures/wiki_corpus/`. No network, Ollama, live DB or
full Wiki dataset is needed in CI.

## Current parser status (2026-10-18)

The inventory and aggregate field counts below are a **historical local-DB snapshot**, not post-fix measurements.
The corpus contains 22 attributed BG/FFXIclopedia excerpts, 8 attributed real WikiWikiJP HTML excerpts, and 13 synthetic samples. Synthetic samples are not source evidence.

- **Merged #1098:** MediaWiki table-cell attributes separated from display labels; raw markup retained. Table/header gap pins retired.
- **Merged #1099:** Simple wrapper template values retain reviewable text; complex expansion remains unsupported. Nested-wrapper gap pin retired.
- **Merged #1101:** WikiWikiJP HTML rowspan/colspan tracked as physical columns; NPC area/coordinate mismatch corrected, both Voidwatch route areas retained.

All extracted field hints remain **review-only** and are not verified gameplay relationships. Next: multi-level merged headers, blank cells, and real two-column label/value examples. Merged #1110 adds focused merged-cell regressions on top of the reconciled v6 parser.
The audit below documents its original baseline; this status supersedes outdated parser limitations.

## 1. Local Wiki source inventory (`ffxi_zone_database.db`, read-only)

| Source | Pages | Raw MediaWiki source (`reference_wiki_documents`) | Structured blocks | Revision ids | Hashes | Limitations |
|---|---:|---|---|---|---|---|
| BGWiki | 47,608 | 47,607 docs (47,601 non-empty; 6 empty; 1 page without a doc) | 576,160 template_field, 215,094 table_cell, 545,214 link, ... (parser `wiki-doc-v3-table-fields`) | all pages | page_hash + raw_hash (verified = SHA-256 of raw) | Offline dump; per-page retrieval time not stored |
| FFXIclopedia | 540 | only 24 docs; 516 pages are flattened text with no raw source | 292 template_field (24 pages) | all pages | page_hash; raw_hash for 24 | API scrape 2026-10-16; 96% of pages cannot be re-parsed structurally |
| WikiWikiJP | 637 | **none** (`html-crawl` stored as flattened `page_text`) | none (would be `legacy_text`) | **none** | page_hash only | No labels, tables or templates survive; Japanese structure cannot be tested from stored data |

Other tables: claims 47 BG / 27 FFXIclopedia / 0 JP (all with revision + locator), 3 page alignments, 48 claim
alignments, 0 relations. Wiki import jobs exist (`wiki_bulk_jobs`, `wiki_bg_dump_jobs`, `wiki_jp_crawl_jobs`) and
can fetch more FFXIclopedia (API) and WikiWikiJP (crawl) pages; they were **not** run. BG uses a local dump.
No new scraper was built.

## 2. Corpus

`real_manifest.json` (24 attributed minimal excerpts: 17 BG, 7 FFXIclopedia) is produced by
`scripts/wiki_corpus_extract.py --db ffxi_zone_database.db`. Each carries source wiki, page title/id, URL,
revision id/timestamp, full-page raw SHA-256 (+ `raw_source_sha256_verified`), excerpt SHA-256, template/table
type, per-field label/raw value/locator/expected type, categories and license note. Retrieval timestamp is
`null` (not recorded per page). Excerpts keep only short parameters (<=220 chars) and at most 14 table lines;
omitted parameters are listed. Licensing is believed CC BY-NC-SA (BG) / CC BY-SA (FFXIclopedia); verify before
wider redistribution.

`real_jp_manifest.json` (8 real WikiWikiJP HTML excerpts: 4 ヴォイドウォッチ tables, 3 BFNM/NM tables, 1 NM list;
added after the pilot crawls recorded raw HTML and `retrieved_at`): a header plus two body rows (or four list items)
each, with an independent parser-free cell inventory. Pukiwiki exposes no revision id, so `revision_id` is
`none-exposed`. The runner checks that every non-empty cell survives in order (the parser emits no block for empty
cells, e.g. blank spacer headers; pinned). Voidwatch tables and the NM list yield **no** typed hints. Header
rows use column-header semantics: a policy label in an all-header row (`エリア`, `場所`) yields review-only, typed
(`LOCATION`) hints whose values are the cells beneath that column, never the next header (`orientation: column`). Pinned
per sample in `JP_EXPECTED_HITS`. The current v6 parser accounts for HTML rowspan/colspan: in `jp-vw-npc-table`, the second location is `バストゥーク商業区`, not coordinate `(D-11)`. The labelled JP samples remain synthetic. Licence terms for WikiWikiJP were not verified.

`synthetic_manifest.json` (13 samples) is generated from `synthetic_sources.json`, is marked
`evidence_type: synthetic`, has no URL/hash/revision, and states which real structure it models. The *labelled Japanese template-field samples* are synthetic; eight separate attributed real WikiWikiJP HTML excerpts are in `real_jp_manifest.json`. The historical local database lacked raw WikiWikiJP document storage.

Expected types are the frozen exact-label policy in the extractor, not read back from the parser. Deviations are
pinned in `known_gaps.json`; fixing one fails the test until its entry is deleted.

Covered: NMs (Medusa, Absolute Virtue), spawn/drop/reward/requirement/location labels, quests, missions, key
items, NPCs, BCNM, Trial of the Magians, campaign, infoboxes, two-column macros, insert-template macros, tables,
nested templates/links, Japanese labels and values, malformed source, empty/positional params, legacy flattened
text, ambiguous links (review-only).

## 3. Runner checks

Excerpt hashes; real-sample provenance completeness; label/raw value/locator preservation; classification vs
policy; Japanese label/value preservation; near-miss and layout labels rejected; ambiguous links stay
review-only without resolution keys; no candidate or link carries relation, claim, mapping or resolution keys;
real layout tables invent no candidates; legacy text stays degraded and untyped; malformed input does not raise;
pinned gaps; per-source coverage report.

## 4. Field coverage (whole local DB, exact-label policy)

| Source | Template fields | Typed hint | Unrecognized | Typed but display text empty | JP values |
|---|---:|---:|---:|---:|---:|
| BGWiki | 576,160 | 19,854 (LOCATION 8,814; REWARDS 6,160; REQUIRES 4,383; QUEST 482; **DROPS 15**) | 556,306 | 1,550 | 261 |
| FFXIclopedia | 292 | 42 (QUEST 32; LOCATION 8; REQUIRES 1; REWARDS 1) | 250 | 37 | 0 |
| WikiWikiJP | 0 | 0 | n/a | n/a | n/a |

## 5. Gap analysis

**Unsupported but plausibly meaningful (BG label, count; each needs a design decision, not a silent alias)**
`DropsA/B/C/PrimaryDrops/DropsEvent` (~650), `Quest Reqs` 1,030, `Mission Name` 504, `Required.Augments` 2,459,
`Level Requirement` / `Previous Quest` / `Next Quest` / `Quest Name` ~100 each, `Unit Requirement` 53. Most volume
is item/equipment metadata (`Type`, `description`, `flags`, ...), intentionally out of scope. FFXIclopedia:
`drops-from`, `obtained`, `zones`, `bcnm` on the key-item infobox.

**Macro labels:** `Insert Quest List Template` (5,598), `Insert NPC List Template` (8,329), `Insert Quest Usage ...`
etc. are template-macro parameter names whose value is a transclusion marker. They are correctly unclassified but
dominate counts; they could be flagged `macro_field`.

**Historical parser gaps (now addressed in v6 except as noted)**
1. The historical parser dropped simple nested-wrapper display text (1,550 BG, 37 FFX potentially affected), e.g.
   `Zone={{Zone|X}}`. Label and raw value survive. Pinned: `syn-nested-template-value::Zone`.
2. The historical parser retained table cell attribute prefixes in cell text (`style="width:30%" | Location`), so exact-label matching
   misses them and header text is polluted. Pinned: `syn-table-header-attrs` (real BG headers show the same).
3. A template parameter that embeds `===heading===` (Medusa/Absolute Virtue `Notes`) also yields heading blocks
   from the template body (pinned by `syn-embedded-heading`). The real `Notes` value exceeded the excerpt limit
   and is listed as omitted.
4. Dotted/compound labels (`Main.Job`, `Required.Augments`) are kept verbatim and never match.

**Historical local-DB provenance gap:** WikiWikiJP pages in the sampled DB had no revision id or raw source; 516 of 540 FFXIclopedia pages had
no raw source; 6 BG docs have empty raw source; per-page retrieval time is not stored anywhere.

**Japanese/English alignment gaps:** only 1 WikiWikiJP alias exists; page alignments cover 3 titles; claim
alignments are 48 entity references. BG pages with `Japanese=` fields (e.g. `Magh Bihu`, label `Japanese`)
preserve the Japanese value, but nothing maps it to the JP wiki. The separately attributed JP HTML fixture samples validate table/list structure but do not establish full local-DB coverage or a reviewed cross-wiki topic mapping.

**Real layout tables:** the sampled BG/FFXIclopedia tables are layout or list tables. Two-column label/value tables
with allowlisted labels were not found in the sample, so those cases are synthetic.

## 6. Recommended next changes (ordered)

1. Re-crawl and preserve raw HTML/wikitext for historic WikiWikiJP and FFXIclopedia flattened pages; validate current storage and provenance before reporting recovered counts.
2. Gather real two-column label/value examples, missing/blank-cell and multi-level-header examples, and extend parser regressions without claiming authoritative relationships.
3. Design review of tiered/compound labels (`DropsA..C`, `PrimaryDrops`, `Quest Reqs`, `Required.Augments`): add through explicit, reviewed, per-source mappings, not generic aliases.
4. Flag `Insert * Template` parameters as `macro_field` without treating macro names as gameplay relationships.
5. Audit retrieval timestamps, revision availability, and source freshness on current imported pages.
6. Link reviewed Wiki fields to Feature Trace source-native drill-down (without implicit graph promotion).
7. Evaluate per-section translation UX and cross-wiki reviewed topic links separately from source-original evidence.

## 7. Reproduce / extend

```
py -3.11 scripts/wiki_corpus_extract.py --db ffxi_zone_database.db   # real excerpts (local DB)
py -3.11 scripts/wiki_corpus_extract.py --synthetic                  # synthetic manifest
PYTHONPATH=".;src" py -3.11 test_fixtures/test_wiki_corpus.py
```

## 8. Full-corpus validation

See [WIKI_FULL_CORPUS_VALIDATION.md](WIKI_FULL_CORPUS_VALIDATION.md) for the whole-database reparse with parser `wiki-doc-v6-html-table-spans` (the table-attribute, nested-template and JP rowspan gaps above are now fixed; gaps 1-2 in section 6 are closed).

## 9. Status interpretation

The page counts, classification counts, and provenance tables in sections 1 and 4 are an **offline historical snapshot**, not evidence that those totals still hold in the user's current database. The 24 BG/FFXIclopedia and 8 JP real excerpts are a regression sample, not an acceptance test of all scraped pages. Code/fixture changes merged on GitHub do not establish end-to-end crawl success or validate user-local data. Record a fresh, versioned audit of the local DB and wiki imports before declaring those operational backlog items complete.
