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
