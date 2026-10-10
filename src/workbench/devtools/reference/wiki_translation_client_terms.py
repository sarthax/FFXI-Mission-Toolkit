"""Client-DAT terminology (JA->EN) for the Wiki translator.

Terms come from exact, same-install EN/JA DAT pairs held in the bilingual text DB
(``workbench.client.dat.text_db``). They are verified-by-record-index, but are
still only prompt hints: reviewed Wiki terms and the curated starter glossary
take precedence, and the DB is optional (absent DB -> no client terms).
"""
from __future__ import annotations

import hashlib
import os
import sqlite3
from pathlib import Path

MIN_TERM_CHARS = 3        # shorter names are too ambiguous in running prose
MAX_TERMS_PER_BLOCK = 40
_SNAPSHOT_KINDS = ("items", "auto_translate")


def default_db_path() -> Path:
    env = os.environ.get("WIKI_CLIENT_TEXT_DB", "").strip()
    if env:
        return Path(env)
    from workbench.client.dat.text_db import DB_PATH
    return Path(DB_PATH)


class ClientTerms:
    """Read-only, lazily loaded JA->EN term index with a client snapshot id."""

    def __init__(self, db_path: str | Path | None = None):
        self.path = Path(db_path) if db_path else default_db_path()
        self._terms: dict[str, str] | None = None
        self._snapshot: str | None = None

    @property
    def available(self) -> bool:
        return self.path.exists()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(f"file:{self.path.as_posix()}?mode=ro", uri=True)

    @property
    def snapshot_id(self) -> str:
        """Fingerprint of the DAT files that supplied the terms ('none' if no DB)."""
        if self._snapshot is None:
            if not self.available:
                self._snapshot = "none"
            else:
                con = self._connect()
                try:
                    rows = con.execute(
                        "SELECT kind, ident, en_sha1, ja_sha1 FROM dat_pairs "
                        "WHERE kind IN (?,?) ORDER BY kind, ident", _SNAPSHOT_KINDS).fetchall()
                finally:
                    con.close()
                self._snapshot = hashlib.sha256(repr(rows).encode()).hexdigest()[:16]
        return self._snapshot

    def _load(self) -> dict[str, str]:
        if self._terms is not None:
            return self._terms
        self._terms = {}
        if not self.available:
            return self._terms
        candidates: dict[str, set[str]] = {}
        con = self._connect()
        try:
            for ja, en in con.execute("SELECT name_ja, name_en FROM items"):
                self._add(candidates, ja, en)
            for ja, en in con.execute("SELECT ja, en FROM auto_translate"):
                self._add(candidates, ja, en)
        finally:
            con.close()
        # Ambiguous Japanese names (several different English names) are dropped.
        self._terms = {ja: next(iter(en)) for ja, en in candidates.items() if len(en) == 1}
        return self._terms

    @staticmethod
    def _add(out: dict, ja, en) -> None:
        ja, en = (ja or "").strip(), (en or "").strip()
        if len(ja) >= MIN_TERM_CHARS and en and "${" not in ja and "${" not in en:
            out.setdefault(ja, set()).add(en)

    def terms_in(self, text: str, limit: int = MAX_TERMS_PER_BLOCK) -> dict[str, str]:
        """Client terms occurring in *text*; longest match wins over contained terms."""
        found = [t for t in self._load() if t in text]
        found.sort(key=len, reverse=True)
        kept: list[str] = []
        for term in found:
            if not any(term in longer for longer in kept):
                kept.append(term)
            if len(kept) >= limit:
                break
        terms = self._load()
        return {t: terms[t] for t in kept}


_default: ClientTerms | None = None


def default_terms() -> ClientTerms:
    global _default
    if _default is None or _default.path != default_db_path():
        _default = ClientTerms()
    return _default
