"""Domain framework service (read-only).

Loads definitions.json and, for each domain entity, reports what the configured server checkouts
actually contain (glob matches per root) plus how many offline BG Wiki pages back the domain.
"Present" only means the expected files exist; it says nothing about completeness or correctness.
"""
from __future__ import annotations

import glob
import gzip
import json
import re
from pathlib import Path

DEF_PATH = Path(__file__).with_name("definitions.json")
WIKI_DUMP = Path(__file__).resolve().parents[2] / "vendor/ffxi-wiki-dumps-dist/bg-wiki.jsonl.gz"
_WIKI_CACHE: dict = {}


def load() -> dict:
    return json.loads(DEF_PATH.read_text(encoding="utf-8"))["domains"]


def slug(label: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-")


def wiki_counts(categories: list[str]) -> dict[str, int]:
    """Pages per category from the offline dump; the dump is scanned once per process."""
    if not WIKI_DUMP.is_file():
        return {}
    key = WIKI_DUMP.stat().st_mtime
    if _WIKI_CACHE.get("key") != key:
        counts: dict[str, int] = {}
        with gzip.open(WIKI_DUMP, "rt", encoding="utf-8") as f:
            for line in f:
                for c in json.loads(line).get("categories", []):
                    counts[c] = counts.get(c, 0) + 1
        _WIKI_CACHE.update(key=key, counts=counts)
    return {c: _WIKI_CACHE["counts"].get(c, 0) for c in categories}


def _count(root: Path | None, pattern: str) -> int | None:
    if root is None or not Path(root).is_dir():
        return None  # root not configured
    return len(glob.glob(str(Path(root) / pattern)))


def resolve(domain: dict, roots: dict[str, Path | None]) -> list[dict]:
    """Per entity: matches per server root for each glob, and a total per root."""
    out = []
    for ent in domain["entities"]:
        per_root = {}
        for name, root in roots.items():
            hits = [(g, _count(root, g)) for g in ent["server_globs"]]
            per_root[name] = {
                "configured": root is not None and Path(root).is_dir(),
                "globs": [{"glob": g, "matches": n} for g, n in hits],
                "present": sum(n or 0 for _, n in hits) > 0,
            }
        out.append({**ent, "per_root": per_root})
    return out


def domain_status(domain: dict, resolved: list[dict]) -> dict:
    """Roll up: for each root, how many entity kinds have any matching file."""
    roll = {}
    for ent in resolved:
        for name, info in ent["per_root"].items():
            r = roll.setdefault(name, {"present": 0, "total": len(resolved), "configured": info["configured"]})
            r["present"] += 1 if info["present"] else 0
    return roll
