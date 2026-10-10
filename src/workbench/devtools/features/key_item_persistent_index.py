"""Persistent, read-only DSP Lua reference cache with incremental source validation.

Cache is kept outside the server checkout. A checkout's resolved path is
recorded in SQLite so entries cannot be mixed across DSP environments.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from .key_item_references import _indexed_lua_lines, _ALLOWED_NAMESPACES, _OPERATION


def query_index(root: str | Path, db_path: str | Path, symbol: str, *,
                lineage: str = "dsp", max_files: int = 25000,
                max_matches: int = 200) -> dict:
    if lineage not in _ALLOWED_NAMESPACES:
        raise ValueError("unsupported source lineage")
    import re
    if not re.fullmatch(r"[A-Z][A-Z0-9_]*", symbol):
        raise ValueError("invalid key-item symbol")
    root = Path(root).resolve()
    scripts = root / "scripts"
    if not scripts.is_dir():
        return {"references": [], "scanned_files": 0, "matched_scripts": 0,
                "operation_counts": {"require": 0, "grant": 0, "remove": 0},
                "truncated": False, "cache": "missing_source"}
    db_path = Path(db_path).resolve()
    # A SQLite file inside the scripts directory risks polluting the checkout.
    if db_path.is_relative_to(root):
        raise ValueError("cache must be outside the server checkout")
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(db_path), timeout=10)
    try:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS sources (
            root TEXT NOT NULL, path TEXT NOT NULL, mtime_ns INTEGER NOT NULL,
            size INTEGER NOT NULL, PRIMARY KEY(root, path)
        );
        CREATE TABLE IF NOT EXISTS refs (
            root TEXT NOT NULL, path TEXT NOT NULL, symbol TEXT NOT NULL,
            line INTEGER NOT NULL, namespace TEXT NOT NULL,
            api TEXT NOT NULL, source_text TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS ix_ki_refs ON refs(root, symbol, path, line);
        """)
        root_key = str(root)
        files = sorted(scripts.rglob("*.lua"))
        truncated = len(files) > max_files
        selected = files[:max_files]
        seen = set()
        updated = 0
        for file in selected:
            if not file.resolve().is_relative_to(root):
                continue
            rel = file.relative_to(root).as_posix()
            seen.add(rel)
            try:
                st = file.stat()
                existing = con.execute(
                    "SELECT mtime_ns, size FROM sources WHERE root=? AND path=?",
                    (root_key, rel)).fetchone()
                if existing == (st.st_mtime_ns, st.st_size):
                    continue
                indexed = _indexed_lua_lines(str(file), st.st_mtime_ns, st.st_size)
                con.execute("DELETE FROM refs WHERE root=? AND path=?", (root_key, rel))
                for key, values in indexed.items():
                    con.executemany(
                        "INSERT INTO refs VALUES (?,?,?,?,?,?,?)",
                        [(root_key, rel, key, line, namespace, api, source)
                         for line, source, namespace, api in values])
                con.execute(
                    "INSERT OR REPLACE INTO sources VALUES (?,?,?,?)",
                    (root_key, rel, st.st_mtime_ns, st.st_size))
                updated += 1
            except OSError:
                truncated = True
        # Only prune absent files after a complete traversal.
        if not truncated:
            stored = con.execute("SELECT path FROM sources WHERE root=?", (root_key,)).fetchall()
            for (rel,) in stored:
                if rel not in seen:
                    con.execute("DELETE FROM refs WHERE root=? AND path=?", (root_key, rel))
                    con.execute("DELETE FROM sources WHERE root=? AND path=?", (root_key, rel))
        con.commit()
        namespaces = tuple(_ALLOWED_NAMESPACES[lineage])
        holders = ",".join("?" for _ in namespaces)
        records = con.execute(
            "SELECT path,line,namespace,api,source_text FROM refs "
            f"WHERE root=? AND symbol=? AND namespace IN ({holders}) "
            "ORDER BY path,line LIMIT ?",
            (root_key, symbol, *namespaces, max_matches + 1)).fetchall()
        if len(records) > max_matches:
            truncated = True
        refs = []
        counts = {"require": 0, "grant": 0, "remove": 0}
        for rel, line, namespace, api, source in records[:max_matches]:
            operation = _OPERATION[api]
            counts[operation] += 1
            refs.append({"source_path": rel, "source_line": line,
                         "namespace": namespace, "api": api,
                         "operation": operation, "source_text": source,
                         "symbol": symbol})
        return {"references": refs, "scanned_files": len(selected),
                "matched_scripts": len({r["source_path"] for r in refs}),
                "operation_counts": counts, "truncated": truncated,
                "cache": "sqlite", "reindexed_files": updated,
                "symbol": symbol, "lineage": lineage, "source_root": root_key,
                "limitations": ["Static occurrences do not prove execution.",
                                "Dynamic, multiline and helper-generated calls may be missed."]}
    finally:
        con.close()
