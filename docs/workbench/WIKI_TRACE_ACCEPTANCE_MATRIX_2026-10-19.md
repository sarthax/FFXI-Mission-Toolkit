# Wiki → Feature Trace acceptance matrix (2026-10-19)

The initial source-aware navigation implementation is merged through PR #1137. This checkpoint distinguishes offline fixture contracts from operator acceptance on the user's local DB.

| Case | Offline coverage | Live acceptance |
| --- | --- | --- |
| BGWiki Medusa (page 37229) | Attributed minimal wikitext, source ID, revision, parser locator, dossier route query | Not run |
| BGWiki Absolute Virtue (page 535) | Attributed minimal wikitext, source ID, revision, parser locator, dossier route query | Not run |
| WikiWikiJP original-language section | Synthetic dossier contract with Unicode section in URL | Not run |
| Wrong-source/same-ID page navigation | Exact composite-key provider regression | Not run |
| Real game implementation/behavior relevance | Not implied by Wiki evidence | Not run |

Run offline: `PYTHONPATH=src:. python test_fixtures/test_wiki_trace_real_corpus_acceptance.py`.

## Operator acceptance on local installation

1. Confirm Medusa and Absolute Virtue are present in `reference_wiki_pages` and have corresponding `reference_wiki_blocks` and `reference_wiki_documents` rows. Note source revision, retrieved timestamp and parser version; do not fabricate missing values.
2. In Feature Trace search, resolve the **BGWiki** source-qualified page and inspect a populated Wiki block. Confirm the Evidence Dossier shows the original source locator and a review-only warning, without mislabelling the block as verified server behavior.
3. Follow **Open exact Wiki source page / section**. Confirm URL retains BGWiki and the exact page ID, the Wiki browser displays that same page, and section focus highlights the expected original heading where available.
4. Repeat with Absolute Virtue and test a missing or wrong source-qualified page ID; a mismatch must show an error rather than a different title match.
5. Record identity correctness, locator correctness, whether the intended section was focused, unrelated content encountered and click count. Compare to the operator's intended behavior question. Mark each case PASS/FAIL/BLOCKED with screenshots/logs and commit/database provenance.

**Limitation:** Real corpus fixtures are short extracts. Passing offline checks does not prove a deployed Wiki UI resolves every original page, that source locators are exact document positions, or that Feature Trace ranking is useful. Preserve this gap in the roadmap until user-local acceptance succeeds.
