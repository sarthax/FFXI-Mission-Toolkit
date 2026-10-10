"""Model/version-scoped cache for non-authoritative Japanese Wiki block translations."""
from __future__ import annotations

import hashlib
import json
import sqlite3

from . import wiki_ollama_translate as engine

VERSION = "wiki-jp-block-v2-quality"
DDL = """CREATE TABLE IF NOT EXISTS reference_wiki_block_translations (
 source_id TEXT NOT NULL, page_id TEXT NOT NULL, block_id TEXT NOT NULL,
 source_hash TEXT NOT NULL, model TEXT NOT NULL, policy_hash TEXT NOT NULL,
 target_lang TEXT NOT NULL DEFAULT 'en', translated TEXT NOT NULL,
 warnings_json TEXT NOT NULL DEFAULT '[]', created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 PRIMARY KEY(source_id,page_id,block_id,source_hash,model,policy_hash,target_lang))"""


def policy_hash() -> str:
    payload = json.dumps({"version": VERSION, "glossary": engine.GLOSSARY},
                         ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def render(blocks: list[dict]) -> str:
    lines = []
    for block in blocks:
        value = block["text"]
        kind = block["block_type"]
        if kind == "heading":
            value = "\n## " + value + "\n"
        elif kind == "list_item":
            value = "- " + value
        elif kind in {"table_header_cell", "table_cell"}:
            value = "| " + value + " |"
        lines.append(value)
    return "\n".join(lines)


def translate_cached_blocks(con: sqlite3.Connection, *, source_id: str,
                            page_id: str, blocks: list[dict], model: str,
                            max_blocks: int = 500) -> dict:
    if not model.strip():
        return {"status": "ERROR", "error": "Explicit model required"}
    if not blocks or len(blocks) > max_blocks:
        return {"status": "ERROR", "error": "Invalid or excessive block count"}
    con.execute(DDL)
    policy = policy_hash()
    output, warnings, misses = [], [], 0
    for block in blocks:
        kind = block.get("block_type", "")
        original = block.get("text") or ""
        if kind not in engine._TRANSLATABLE or not original.strip():
            continue
        if len(original) > 5000:
            return {"status": "ERROR", "error": "Block exceeds 5000 characters: " + str(block.get("block_id"))}
        block_id = str(block.get("block_id") or "")
        if not block_id:
            return {"status": "ERROR", "error": "Source block has no identifier"}
        digest = hashlib.sha256(original.encode("utf-8")).hexdigest()
        args = (source_id, str(page_id), block_id, digest, model, policy, "en")
        hit = con.execute("""SELECT translated,warnings_json FROM reference_wiki_block_translations
            WHERE source_id=? AND page_id=? AND block_id=? AND source_hash=?
              AND model=? AND policy_hash=? AND target_lang=?""", args).fetchone()
        if hit:
            translated, issue_list = hit[0], json.loads(hit[1])
        else:
            try:
                result = engine.translate(original, model=model)
            except Exception as exc:
                return {"status": "ERROR", "error": "Ollama failed on " + block_id + ": " + str(exc)}
            if result.get("status") != "OK":
                return {"status": "ERROR", "error": "Translation failed on " + block_id + ": " + str(result.get("error"))}
            translated, issue_list = result["text"], result.get("warnings", [])
            con.execute("""INSERT OR REPLACE INTO reference_wiki_block_translations
              (source_id,page_id,block_id,source_hash,model,policy_hash,target_lang,translated,warnings_json)
              VALUES (?,?,?,?,?,?,?,?,?)""", args + (translated, json.dumps(issue_list, ensure_ascii=False)))
            # Each successful block survives a later failure; pages only publish on full success.
            con.commit()
            misses += 1
        output.append({"block_id": block_id, "ordinal": block.get("ordinal"),
                       "block_type": kind, "original": original, "text": translated,
                       "section_path": block.get("section_path"),
                       "source_locator": block.get("source_locator")})
        warnings.extend(block_id + ": " + issue for issue in issue_list)
    if not output:
        return {"status": "ERROR", "error": "No translatable blocks"}
    return {"status": "OK", "text": render(output), "blocks": output,
            "engine": "ollama:" + model, "unverified": True, "warnings": warnings,
            "cache_hits": len(output) - misses, "cache_misses": misses}
