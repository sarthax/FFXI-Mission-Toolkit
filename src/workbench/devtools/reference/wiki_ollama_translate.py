"""Opt-in local Ollama Japanese Wiki translator. Original wiki evidence is never modified."""
from __future__ import annotations

import json
import os
import re
import urllib.request

_DEFAULT_URL = "http://127.0.0.1:11434/api/generate"
_NUMBERS = re.compile(r"(?<![\w])\d+(?:[.,]\d+)*(?![\w])")
# Curated starter terms; extend from reviewed aliases/client identifiers, not model guesses.
GLOSSARY = {"だいじなもの": "key item", "ミッション": "mission",
            "クエスト": "quest", "ノートリアスモンスター": "Notorious Monster",
            "魔法": "magic", "エリア": "area", "獣人": "beastman"}


def translate(text: str, *, model: str, url: str = _DEFAULT_URL,
              timeout: int = 120, max_chars: int = 5000) -> dict:
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
    terms = "\n".join(f"{jp} = {en}" for jp, en in GLOSSARY.items())
    prompt = (
        "Translate this Final Fantasy XI Japanese wiki excerpt into natural English. "
        "Preserve numbers, item IDs, names, list formatting, and uncertainty. "
        "Do not add facts, explanations, or commentary. Use these glossary terms:\n"
        + terms + "\n\nJapanese source:\n" + text + "\n\nEnglish translation:"
    )
    payload = json.dumps({"model": model, "prompt": prompt, "stream": False,
                          "options": {"temperature": 0}}).encode("utf-8")
    req = urllib.request.Request(url, payload, headers={"Content-Type": "application/json"},
                                 method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as response:
        translated = json.load(response).get("response", "").strip()
    if not translated:
        return {"status": "ERROR", "error": "Model returned no translation"}
    missing = sorted(set(_NUMBERS.findall(text)) - set(_NUMBERS.findall(translated)))
    return {"status": "OK", "text": translated, "engine": "ollama:" + model,
            "unverified": True, "warnings": ["Numeric tokens missing: " + ", ".join(missing)] if missing else []}


def configured_model() -> str:
    return os.environ.get("WIKI_TRANSLATE_OLLAMA_MODEL", "").strip()
