# Wiki V2 Real-Source Fixture Corpus

Offline regression corpus for Wiki V2 typed extraction. Runner: `test_fixtures/test_wiki_corpus.py`
(wired into Workbench Regression). Data: `test_fixtures/wiki_corpus/`. No network, Ollama, live DB or
full Wiki dataset is needed in CI.

Branched from `main` (d4fd28db). It does **not** touch PR #1092 (`wiki_document.py`, its audit doc, its
contract test). The only shared file is `workbench-regression.yml`: this PR adds its line after
`test_wiki_document_v2.py`, #1092 adds one after `test_wiki_named_template_candidates.py`, so they should
merge cleanly. Table assertions treat `field_type` as optional so the corpus passes before and after #1092.

## Current parser status (2026-10-18)

The inventory and aggregate field counts below are a **historical local-DB snapshot**, not post-fix measurements.
The corpus contains 22 attributed BG/FFXIclopedia excerpts, 8 attributed real WikiWikiJP HTML excerpts, and 13 synthetic samples. Synthetic samples are not source evidence.

- **Merged #1098:** MediaWiki table-cell attributes separated from display labels; raw markup retained. Table/header gap pins retired.
- **Merged #1099:** Simple wrapper template values retain reviewable text; complex expansion remains unsupported. Nested-wrapper gap pin retired.
- **Merged #1101:** WikiWikiJP HTML rowspan/colspan tracked as physical columns; NPC area/coordinate mismatch corrected, both Voidwatch route areas retained.

All extracted field hints remain **review-only** and are not verified gameplay relationships. Next: multi-level merged headers, blank cells, and real two-column label/value examples.
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

`real_manifest.json` (22 attributed minimal excerpts: 15 BG, 7 FFXIclopedia) is produced by
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
per sample in `JP_EXPECTED_HITS`. Known limitation: rowspan/colspan tables are indexed positionally, so
`jp-vw-npc-table`'s second hit (`(D-11)`) is a shifted column. The labelled JP samples remain synthetic. Licence terms for WikiWikiJP were not verified.

`synthetic_manifest.json` (13 samples) is generated from `synthetic_sources.json`, is marked
`evidence_type: synthetic`, has no URL/hash/revision, and states which real structure it models. **All
WikiWikiJP samples are synthetic** because no WikiWikiJP structure is stored locally.

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

**Misclassified / lossy**
1. A typed label whose value is a nested template yields empty display text, so no hint (1,550 BG, 37 FFX), e.g.
   `Zone={{Zone|X}}`. Label and raw value survive. Pinned: `syn-nested-template-value::Zone`.
2. Table cell attribute prefixes remain in cell text (`style="width:30%" | Location`), so exact-label matching
   misses them and header text is polluted. Pinned: `syn-table-header-attrs` (real BG headers show the same).
3. A template parameter that embeds `===heading===` (Medusa/Absolute Virtue `Notes`) also yields heading blocks
   from the template body (pinned by `syn-embedded-heading`). The real `Notes` value exceeded the excerpt limit
   and is listed as omitted.
4. Dotted/compound labels (`Main.Job`, `Required.Augments`) are kept verbatim and never match.

**Missing provenance:** WikiWikiJP pages have no revision id and no raw source; 516 of 540 FFXIclopedia pages have
no raw source; 6 BG docs have empty raw source; per-page retrieval time is not stored anywhere.

**Japanese/English alignment gaps:** only 1 WikiWikiJP alias exists; page alignments cover 3 titles; claim
alignments are 48 entity references. BG pages with `Japanese=` fields (e.g. `Magh Bihu`, label `Japanese`)
preserve the Japanese value, but nothing maps it to the JP wiki. No JP structured labels can be validated from
stored data.

**Real layout tables:** the sampled BG/FFXIclopedia tables are layout or list tables. Two-column label/value tables
with allowlisted labels were not found in the sample, so those cases are synthetic.

## 6. Recommended next changes (ordered)

1. Keep raw HTML/wikitext for WikiWikiJP and the remaining 516 FFXIclopedia pages so structure can be tested; re-crawl through the existing jobs.
2. Fix nested-template display text (template-aware rendering or raw-value fallback) and delete the pinned gap.
3. Separate table cell attributes into metadata; delete the table gap pins.
4. Design review of tiered/compound labels (`DropsA..C`, `PrimaryDrops`, `Quest Reqs`, `Required.Augments`): add through explicit, reviewed, per-source mappings, not generic aliases.
5. Flag `Insert * Template` parameters as `macro_field`.
6. Record per-page retrieval timestamps on import.
7. Add real two-column label/value table excerpts once found (query `reference_wiki_blocks` for `table_row` with an allowlisted first cell).

## 7. Reproduce / extend

```
py -3.11 scripts/wiki_corpus_extract.py --db ffxi_zone_database.db   # real excerpts (local DB)
py -3.11 scripts/wiki_corpus_extract.py --synthetic                  # synthetic manifest
PYTHONPATH=".;src" py -3.11 test_fixtures/test_wiki_corpus.py
```
