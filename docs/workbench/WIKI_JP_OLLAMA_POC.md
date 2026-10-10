# Japanese Wiki → English local Ollama PoC

This is an **opt-in, draft-only** translator attached to the existing Wiki page "Translate to English (machine)" action. The original Japanese `reference_wiki_pages.page_text` and structured blocks are never replaced. Wiki translations are not authoritative gameplay findings.

## Local setup (Windows PowerShell)

1. Install and run Ollama locally; download a model that supports Japanese → English translation.
2. Test the model using `ollama run <your-model-name>`.
3. Set `$env:WIKI_TRANSLATE_OLLAMA_MODEL="<your-model-name>"` in the same PowerShell environment that launches the toolkit, then start the toolkit.
4. Open a previously cached WikiWikiJP article in Wiki > Browse and select **Translate to English (machine)**.

The model uses Ollama's local `http://127.0.0.1:11434/api/generate` endpoint. No cloud provider or remote endpoint is permitted by the PoC. The existing `WIKI_TRANSLATE_CMD` path remains available if no Ollama model is configured. If neither is configured, the UI reports `NO_ENGINE`.

## Current limitations

- The initial model call handles excerpts up to **5,000 characters**. Longer pages report an explicit error; they need structural block/chunk translation in the next slice.
- A small reviewed terminology starter glossary is applied in the prompt. Future work should load canonical aliases and client DAT identity data.
- Numeric omissions are flagged as warnings; translations are still **unverified**. Translation of page content does not promote wiki reference claims into server truth.
- Structured pages now use `reference_wiki_block_translations`, keyed by source/page/block, source text hash, model, and glossary/prompt policy fingerprint. Different models coexist, and successful blocks survive interruptions. The existing page-level table remains for legacy command translations; unstructured Ollama fallback currently has no reusable block cache.
- The UI does not yet display per-paragraph bilingual alignment, numeric warnings, or background queue progress. These belong to the follow-up Wiki translation workflow.
- Scraping, cache ingestion, and structure extraction are deliberately unchanged.

## Offline smoke tests

Run `python tests/legacy/test_wiki_ollama_translate.py`. It mocks Ollama responses, checks cache reuse, original-content preservation, numeric warnings and local-endpoint restrictions. A live model integration test requires a local Ollama installation and cached Japanese article.

## Second slice: cache regression tests

Run `python tests/legacy/test_wiki_translation_cache.py`. This tests same-model reuse, model changes, edited-block invalidation, hidden links, and interrupted-page recovery without Ollama. Live model/GUI validation and CI remain necessary.

## Third slice: explicit cached-page batch service

`wiki_translation_batch.py` adds SQLite-persisted run status, completed/failed counts, remaining-page checkpoints, cached-block reuse, and in-process cancellation. It selects only cached `WikiWikiJP` pages (10 or 50 per run) and never issues wiki scraping requests. Failed pages are recorded for retry; a stopped job can be retried using `retry_job` with the same selected Ollama model. Interrupted process state is detected when status is queried and does not automatically resume.

For a short local smoke run with the toolkit Python environment and running Ollama, set `WIKI_TRANSLATE_OLLAMA_MODEL` and run:

```powershell
python -m workbench.devtools.reference.wiki_translation_batch_cli PATH_TO_WIKI_DB start --limit 10
```

The CLI runs in the foreground; closing it interrupts the worker. Cancellation through `cancel(job_id)` requires invoking the service in the same running application process. HTTP routes and GUI batch controls are **not yet connected** and must not be presented as available. The next slice should wire guarded POST start/cancel/retry endpoints and GET status, then add progress polling to the Wiki translation tab. Before enabling large runs, verify concurrency and rate limiting with local Ollama. Offline contract test: `python tests/legacy/test_wiki_translation_batch.py`.

## Fourth slice: Wiki Translation tab

The Wiki page now includes a **Translation** tab, with 10/50 cached-page batch starts, 4-second status polling, persisted job progress, cancellation requests, and retry-failures actions. Routes: `GET /wiki/translation/jobs` and `POST /wiki/translation/start`, `/retry`, `/cancel`. Source imports and wiki evidence are untouched. The batch worker runs inside the toolkit process; cancellation is cooperative and takes effect between pages, and work interrupted by a toolkit restart stays interrupted until explicitly retried. A page may take substantial time on a local CPU-only model. Live validation and CI are pending.

Offline UI contract test: `python test_fixtures/test_wiki_translation_batch_ui.py`.

## Fifth slice: conservative translation quality checks

The local translation adapter now reports warnings for missing numeric tokens, hex/uppercase identifier strings, missing starter-glossary equivalents, and suspiciously short translated outputs. These are review hints, not reliable judgments of Japanese translation accuracy; reviewed glossary/alias ingestion remains future work. Cache policy version `wiki-jp-block-v2-quality` invalidates prior block drafts so new warnings are populated on retranslation. Offline checks: `python tests/legacy/test_wiki_translation_quality.py`. CI/live tests have not been executed in this session.

## Sixth slice: reviewed wiki terminology

The translation block service now combines its starter terminology with unambiguous, explicitly MANUAL/REVIEWED Japanese page links to canonical English Wiki topics. Unreviewed machine-derived and automatic links are excluded. Only terms appearing in the source block enter the model prompt. The versioned cache fingerprint covers the current glossary; changing reviewed mappings causes regenerated drafts. This is a conservative Wiki-reviewed glossary foundation, **not yet** a client-DAT-wide official name dictionary. Verify it with `python tests/legacy/test_wiki_translation_glossary.py`. Run the complete CI suite and local Ollama smoke tests before merging.

## Seventh slice: client-DAT terminology

`wiki_translation_client_terms.py` adds JA→EN terms from exact same-install client DAT pairs (item names, auto-translate phrases) held in the local bilingual text DB `data/ja_en_text.db` (`workbench.client.dat.text_db`; rebuild with `python -m workbench.client.dat.text_db build --ffxi "<client dir>"`; override location with `WIKI_CLIENT_TEXT_DB`). Names shorter than 3 characters and Japanese names that map to more than one English name are excluded; at most 40 terms (longest match first) enter each block prompt. Precedence is client DAT < reviewed Wiki topics < curated starter glossary. The cache policy is now `wiki-jp-block-v4-client-dat-terms` and includes a client snapshot id (hash of the DAT file SHA-1s that supplied the terms), so a different client build regenerates drafts. If the DB is absent the translator behaves as before (snapshot `none`). Terms are prompt hints and flow into the existing quality warnings; they are not translation verification. Not yet done: zone/NPC/key-item/spell names, per-term confidence/source display in the UI, and incremental/lazy indexing. Test: `python tests/legacy/test_wiki_translation_client_terms.py`. Note: `test_wiki_translation_batch.py` fails on Windows temp-file cleanup (PermissionError) identically on the unmodified PR branch.
