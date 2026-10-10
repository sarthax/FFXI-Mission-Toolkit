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
- The existing translation table allows one English result per page revision/hash. Switching Ollama models forces a fresh result, rather than retaining parallel model variants. The next iteration should use a model/glossary/prompt-version keyed translation table.
- The UI does not yet display per-paragraph bilingual alignment, numeric warnings, or background queue progress. These belong to the follow-up Wiki translation workflow.
- Scraping, cache ingestion, and structure extraction are deliberately unchanged.

## Offline smoke tests

Run `python tests/legacy/test_wiki_ollama_translate.py`. It mocks Ollama responses, checks cache reuse, original-content preservation, numeric warnings and local-endpoint restrictions. A live model integration test requires a local Ollama installation and cached Japanese article.
