# Wiki V2 Full-Corpus Reparse Validation

Validates parser `wiki-doc-v6-html-table-spans` against the whole local Wiki database after
PR #1098 (MediaWiki table-cell attributes), #1099 (simple nested-template display values) and
#1101 (JP HTML rowspan/colspan alignment). Branch `validation/wiki-full-corpus-20261018`.
Raw metrics: [`wiki_full_corpus_validation_metrics.json`](wiki_full_corpus_validation_metrics.json).

## 1. Method and safety

- The production DB (`ffxi_zone_database.db`) was **not modified**. A backup was copied, then a second
  working copy was reparsed (`--apply` refuses the production file name).
- No network, no recrawl. Reuses `wiki_document.build_blocks` / `store_document` (no new importer).
  `retrieved_at` and `source_revision` are passed through unchanged; raw source is untouched.
- Tools: `scripts/wiki_inventory.py` (read-only inventory), `scripts/wiki_full_corpus_validate.py`
  (measure and reparse a working copy). Backups, DB copies and logs live outside the repo and are not committed.

```
py -3.11 scripts/wiki_inventory.py --db WORKING.db --out inventory.json
py -3.11 scripts/wiki_full_corpus_validate.py --db WORKING.db --out report.json            # measure only
py -3.11 scripts/wiki_full_corpus_validate.py --db WORKING.db --out report.json --apply    # reparse the copy
```

Results: 47,661 documents reparsed in 321 s, **0 failures**. A second pass produced an identical
block hash (idempotent). Preserved tables (claims, alignments, relations, jobs) are identical before and
after, and raw checksums are equal. All 47,661 documents were on `wiki-doc-v3-table-fields` before and
are on `wiki-doc-v6-html-table-spans` after.

## 2. Source inventory (before)

| Source | Pages | Docs | Docs with raw | Pages without doc | Missing `retrieved_at` | Revision ids |
|---|---:|---:|---:|---:|---:|---|
| BGWiki | 47,608 | 47,607 | 47,601 (6 empty) | 1 | 47,607 | all |
| FFXIclopedia | 540 | 24 | 24 | **516** | 24 | all |
| WikiWikiJP | 637 | 36 | 36 | **601** | 36 | none exposed |

Only the docs with raw source can be reparsed. 516 FFXIclopedia pages and 601 JP pages are flattened
text with no raw source; structure for those requires an approved crawl (not done).

## 3. Before / after

| Metric | BG before | BG after | FFX before | FFX after | JP before | JP after |
|---|---:|---:|---:|---:|---:|---:|
| Documents | 47,601 | | 24 | | 36 | |
| Pages with changed counts | | 1,398 | | 2 | | 7 |
| Template fields | 576,160 | 576,160 | 292 | 292 | 0 | 0 |
| Typed fields | 19,854 | 19,854 | 42 | 42 | 0 | 0 |
| Typed but empty | 1,550 | **1,543** | 37 | 37 | 0 | 0 |
| Table cell blocks | 235,181 | 226,337 | 725 | 724 | 14,182 | 14,182 |
| Cells with attribute metadata | 0 | **62,222** | 0 | 4 | 0 | 0 |
| Table candidates | 3,041 | **4,465** | 0 | 1 | 332 | 357 |
| Total blocks | 1,883,769 | 1,874,925 | 1,899 | 1,898 | 28,166 | 28,166 |

Table candidates by type, BG before to after: LOCATION 749 to 1,702; REWARDS 1,767 to 1,658; DROPS 108 to 257;
NM_IDENTITY 161 to 476; QUEST 110 to 219; REQUIRES 104 to 111; SPAWN_CONDITIONS 42 to 42.
JP: LOCATION 317 to 342, REWARDS 15 to 15. Template-field counts are unchanged because #1098 to #1101 affect
table cells and display values only. Block totals fall because stripped attribute-only cells no longer
produce blocks. "Before" candidate counts come from the old blocks re-grouped with the current
`presentation_groups`, so the candidate growth includes #1092 column-header semantics as well as the table fixes.

## 4. Per-fix results

**#1098 table-cell attributes (correct improvement).** 62,222 BG cells now carry `cell_attributes` metadata
and their text no longer contains `style="..." |` prefixes. Exact-label matching therefore works on headers
that used to be polluted, which is the main source of the LOCATION, DROPS and NM_IDENTITY increases. Recovered
content (e.g. `Impure alizarin yggzi`, which was previously swallowed after an attribute pipe) is real.

**#1099 simple nested-template values (correct, small).** Only 7 BG pages recovered a display value
(typed-empty 1,550 to 1,543). Of the remaining 1,543, 969 are genuinely empty parameters, 373 are HTML
comments, and 200 are complex templates that are deliberately not expanded. FFX is unchanged at 37.

**#1101 JP rowspan/colspan (correct improvement).** Across all 36 JP pages, LOCATION candidates whose value
was a coordinate (a shifted column) went from 20 to **0**, while total candidates rose from 332 to 357
because correctly aligned columns now appear. 7 pages changed; no JP page lost a block.

## 5. Regressions and limitations

- **No regression confirmed.** No document failed, no preserved claim or alignment changed, raw is untouched.
- **Locator instability (limitation).** Table-cell locators are ordinal (`block:<pid>:table-cell:N`). Because
  attribute-only cells are no longer emitted, 709 BG pages and 1 FFX page have cell locators that shift. The
  production claims table has 47 BG and 27 FFX claims with locators; before applying this to production, check
  each claim's locator against the new blocks (none were rewritten here since the claims table is preserved).
  Stable content-addressed locators are a recommended follow-up.
- **Potential false positives to review (not auto-corrected).** New column candidates for review include
  REWARDS cells whose value is only image markup, LOCATION cells with values such as `Level: Any`, and
  REQUIRES cells with a bare number. All are `review_only`; none feeds a claim or mapping.
- **Still typed-empty 1,543 BG / 37 FFX:** see section 4.
- **Unchanged limitations:** unrecognized labels still dominate (macro labels such as `Insert NPC List Template`
  and tiered labels such as `DropsA`), and nothing about them changed.

## 6. Source-backed examples

| Class | Source | Example | Fixture |
|---|---|---|---|
| Correct improvement | BG `Forri-Porri` (id 100195) | attribute-prefixed cell now yields clean text and `cell_attributes` | `bg-table-attrs-rowspan` |
| Correct improvement | BG `Easy Button` | NM_IDENTITY column header yields `Maju`, `Neak`, `Yakshi` (column orientation, review-only) | `bg-table-nm-column-header` |
| Correct improvement | JP `エリア` tables | coordinates no longer reported as locations after rowspan alignment | `jp-vw-npc-table` and BFNM samples |
| Unchanged limitation | BG nested complex templates | `Zone={{Zone|X}}` style values stay empty by design | gap pin |
| Potential false positive | BG REWARDS image-only cells | review-only, needs reviewer | not pinned |
| Requires manual review | locators on 709 BG pages | claim locators must be re-checked before production apply | none |

`bg-table-attrs-rowspan` and `bg-table-nm-column-header` are real excerpts added to the corpus by this PR
(24 real BG/FFX samples, 8 real JP samples). `test_wiki_corpus.py` now asserts the column-header sample yields
only review-only column NM_IDENTITY hits.

## 7. Tests

All `test_fixtures/test_wiki_*.py` pass except three `*_package_migration` tests. They fail identically on a
clean checkout of `main`, so they are pre-existing and unrelated to this work; the cause was not diagnosed here.

## 8. Remaining gaps and recommended priorities

1. Approved crawl to store raw source for 516 FFX and 601 JP pages (no structure is testable without it).
2. Record `retrieved_at` for all 47,667 docs (all are missing it) and a revision id for JP.
3. Content-stable table locators, then a claim-locator audit before reparsing production.
4. Reviewer pass on the false-positive patterns in section 5.
5. Reviewed per-source mappings for tiered labels (`DropsA..C`, `Quest Reqs`), and a `macro_field` flag.
6. Diagnose the three package_migration test failures separately.

To apply to production: back up the DB, run the reparse with `--apply` against the copy, compare, then swap
under explicit approval. This PR does not touch the production database.
