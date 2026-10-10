"""Opt-in local Ollama Japanese Wiki translator. Original wiki evidence is never modified."""
from __future__ import annotations

import json
import os
import re
import urllib.request

_DEFAULT_URL = "http://127.0.0.1:11434/api/generate"
_NUMBERS = re.compile(r"(?<![0-9])\d+(?:[.,]\d+)*(?![0-9])")
# Curated starter terms; extend from reviewed aliases/client identifiers, not model guesses.
GLOSSARY = {"だいじなもの": "key item", "ミッション": "mission",
            "クエスト": "quest", "ノートリアスモンスター": "Notorious Monster",
            "魔法": "magic", "エリア": "area", "獣人": "beastman"}


# Deterministic translation checks: warnings never certify a translation as correct.
_IDENTIFIERS = re.compile(r"(?<![A-Za-z0-9_])(?:0x[0-9a-fA-F]+|[A-Z][A-Z0-9_]{2,})(?![A-Za-z0-9_])")


def quality_warnings(source: str, translated: str, glossary: dict | None = None) -> list[str]:
    warnings = []
    missing_numbers = sorted(set(_NUMBERS.findall(source)) - set(_NUMBERS.findall(translated)))
    if missing_numbers:
        warnings.append("Numeric tokens missing: " + ", ".join(missing_numbers))
    missing_ids = sorted(set(_IDENTIFIERS.findall(source)) - set(_IDENTIFIERS.findall(translated)))
    if missing_ids:
        warnings.append("Identifiers missing: " + ", ".join(missing_ids))
    if len(source) > 100 and len(translated.strip()) < max(12, len(source) // 20):
        warnings.append("Translation unusually short; review for omissions")
    for jp, en in (glossary or GLOSSARY).items():
        if jp in source and en.casefold() not in translated.casefold():
            warnings.append("Glossary term not found: " + en)
    return warnings


def translate(text: str, *, model: str, url: str = _DEFAULT_URL,
              timeout: int = 120, max_chars: int = 5000,
              glossary: dict | None = None, num_ctx: int = 8192) -> dict:
    """Translate bounded source text via loopback Ollama; return unverified draft."""
    if not model.strip():
        raise ValueError("An explicit installed Ollama model is required")
    # Do not permit arbitrary remote endpoints via configuration on this PoC.
    if url not in {_DEFAULT_URL, "http://localhost:11434/api/generate"}:
        raise ValueError("Only loopback Ollama is allowed")
    if not text.strip():
        return {"status": "ERROR", "error": "Empty source"}
    if len(text) > max_chars:
        return {"status": "ERROR", "error": "Source exceeds translation limit; chunk first"}
    terms = "\n".join(f"{jp} = {en}" for jp, en in (glossary or GLOSSARY).items())
    prompt = (
        "Translate this Final Fantasy XI Japanese wiki excerpt into natural English. "
        "Preserve numbers, item IDs, names, list formatting, and uncertainty. "
        "Do not add facts, explanations, or commentary. Use these glossary terms:\n"
        + terms + "\n\nJapanese source:\n" + text + "\n\nEnglish translation:"
    )
    payload = json.dumps({"model": model, "prompt": prompt, "stream": False,
                          "options": {"temperature": 0, "num_ctx": num_ctx}}).encode("utf-8")
    req = urllib.request.Request(url, payload, headers={"Content-Type": "application/json"},
                                 method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as response:
        translated = json.load(response).get("response", "").strip()
    if not translated:
        return {"status": "ERROR", "error": "Model returned no translation"}
    return {"status": "OK", "text": translated, "engine": "ollama:" + model,
            "unverified": True, "warnings": quality_warnings(text, translated, glossary)}


def configured_model() -> str:
    return os.environ.get("WIKI_TRANSLATE_OLLAMA_MODEL", "").strip()


# Only visible textual blocks are translated; links/structural separators remain intact.
_TRANSLATABLE = frozenset({"heading", "paragraph", "list_item", "definition",
                          "definition_term", "table_header_cell", "table_cell",
                          "template_field", "legacy_text"})


def translate_blocks(blocks: list[dict], *, model: str,
                     max_chars: int = 5000, max_blocks: int = 500) -> dict:
    """Translate per source block while preserving structural order and identities.

    Never translates hidden source links or fabricated fields. A failed block
    aborts the page so partial results are not cached as complete translations.
    """
    if len(blocks) > max_blocks:
        return {"status": "ERROR", "error": "Too many blocks for a single synchronous translation"}
    if not blocks:
        return {"status": "ERROR", "error": "No structured blocks found"}
    translated, warnings = [], []
    for block in blocks:
        kind = block.get("block_type", "")
        original = block.get("text") or ""
        if kind not in _TRANSLATABLE or not original.strip():
            continue
        # Oversized cells/paragraphs are not silently truncated.
        if len(original) > max_chars:
            return {"status": "ERROR", "error": "Block exceeds limit: " + str(block.get("block_id"))}
        result = translate(original, model=model, max_chars=max_chars)
        if result["status"] != "OK":
            return {"status": "ERROR", "error": "Block translation failed: " + str(block.get("block_id")) + ": " + str(result.get("error"))}
        translated.append({"block_id": block.get("block_id"), "ordinal": block.get("ordinal"),
                           "block_type": kind, "original": original, "text": result["text"],
                           "section_path": block.get("section_path"),
                           "source_locator": block.get("source_locator")})
        warnings.extend(str(block.get("block_id")) + ": " + w for w in result.get("warnings", []))
    if not translated:
        return {"status": "ERROR", "error": "No translatable text blocks"}
    display = []
    for b in translated:
        text = b["text"]
        if b["block_type"] == "heading":
            text = "\n## " + text + "\n"
        elif b["block_type"] == "list_item":
            text = "- " + text
        elif b["block_type"] in {"table_header_cell", "table_cell"}:
            text = "| " + text + " |"
        display.append(text)
    return {"status": "OK", "text": "\n".join(display), "blocks": translated,
            "engine": "ollama:" + model, "unverified": True, "warnings": warnings}
