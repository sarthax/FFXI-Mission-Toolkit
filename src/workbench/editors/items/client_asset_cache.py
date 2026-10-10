"""Persistent cache for client item DAT records and embedded icons.

The Item Editor can parse FFXI item DATs on demand, but inventory-style pages may request
hundreds of icons at once. This cache keeps parsed item metadata in SQLite and extracted PNGs
as normal files so lazy first-use extraction stays correct while prebuilding the whole item
surface is optional.

Cache validity is tied to the source DAT file size and mtime. A changed DAT invalidates only
items sourced from that DAT; unrelated cached categories remain usable.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
import time
from typing import Any

from workbench.runtime.paths import DATA_ROOT
from . import dat_tools

CACHE_ROOT = DATA_ROOT / "client_asset_cache" / "items"
INDEX_NAME = "index.sqlite3"


@dataclass(frozen=True)
class SourceRecord:
    category: str
    base_id: int
    item_type: int
    rom_path: str
    path: Path
    record_index: int
    record_count: int
    size: int
    mtime_ns: int


@dataclass(frozen=True)
class CachedItem:
    item_id: int
    available: bool
    metadata: dict[str, Any] | None
    icon_path: Path | None
    icon_sha256: str | None
    source: SourceRecord
    cache_hit: bool


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _client_root() -> Path:
    return Path(dat_tools.ffxi_dir()).resolve()


def _client_key(root: Path | None = None) -> str:
    value = str((root or _client_root()).resolve()).lower().encode("utf-8", errors="replace")
    return hashlib.sha256(value).hexdigest()[:16]


def _namespace(root: Path | None = None) -> Path:
    base = CACHE_ROOT / _client_key(root)
    (base / "icons").mkdir(parents=True, exist_ok=True)
    return base


def _index_path(root: Path | None = None) -> Path:
    return _namespace(root) / INDEX_NAME


def _connect(root: Path | None = None) -> sqlite3.Connection:
    con = sqlite3.connect(_index_path(root), timeout=30.0)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA synchronous=NORMAL")
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS item_cache (
            item_id INTEGER PRIMARY KEY,
            available INTEGER NOT NULL,
            source_category TEXT NOT NULL,
            source_rom_path TEXT NOT NULL,
            source_path TEXT NOT NULL,
            source_size INTEGER NOT NULL,
            source_mtime_ns INTEGER NOT NULL,
            record_index INTEGER NOT NULL,
            metadata_json TEXT,
            icon_file TEXT,
            icon_sha256 TEXT,
            cached_at TEXT NOT NULL
        )
        """
    )
    con.execute("CREATE INDEX IF NOT EXISTS ix_item_cache_source ON item_cache(source_rom_path)")
    return con


def _source_rows(root: Path | None = None) -> list[SourceRecord]:
    client_root = (root or _client_root()).resolve()
    rows: list[SourceRecord] = []
    for category, base_id, item_type, en_rom, _jp_rom in dat_tools.ITEM_DATS:
        path = client_root / en_rom
        if not path.is_file():
            continue
        try:
            count = int(dat_tools.record_count(path))
        except (OSError, ValueError):
            continue
        stat = path.stat()
        rows.append(SourceRecord(
            category=str(category), base_id=int(base_id), item_type=int(item_type),
            rom_path=str(en_rom), path=path, record_index=-1, record_count=count,
            size=int(stat.st_size), mtime_ns=int(stat.st_mtime_ns),
        ))
    return rows


def _source_health(root: Path, namespace: Path) -> tuple[list[dict[str, Any]], int]:
    """Audit stored rows against current source signatures without extracting DATs."""
    sources = _source_rows(root)
    con = _connect(root)
    try:
        rows = con.execute(
            "SELECT item_id, source_rom_path, source_size, source_mtime_ns, "
            "record_index, icon_file FROM item_cache"
        ).fetchall()
    finally:
        con.close()

    by_path: dict[str, list[sqlite3.Row]] = {}
    for row in rows:
        by_path.setdefault(str(row["source_rom_path"]), []).append(row)
    result: list[dict[str, Any]] = []
    known_ids: set[int] = set()
    for source in sources:
        fresh = stale = 0
        for row in by_path.get(source.rom_path, []):
            item_id = int(row["item_id"])
            if not source.base_id <= item_id < source.base_id + source.record_count:
                stale += 1
                continue
            expected = _source_with_index(source, item_id - source.base_id)
            if _row_is_fresh(row, expected, namespace):
                fresh += 1
                known_ids.add(item_id)
            else:
                stale += 1
        result.append({
            "category": source.category,
            "base_id": source.base_id,
            "item_type": source.item_type,
            "rom_path": source.rom_path,
            "path": str(source.path),
            "record_count": source.record_count,
            "cached_count": len(by_path.get(source.rom_path, [])),
            "fresh_count": fresh,
            "stale_count": stale,
            "missing_count": max(0, source.record_count - fresh),
            "size": source.size,
            "mtime_ns": source.mtime_ns,
        })
    orphaned = sum(
        1 for row in rows
        if str(row["source_rom_path"]) not in {src.rom_path for src in sources}
    )
    return result, orphaned


def list_sources() -> list[dict[str, Any]]:
    root = _client_root()
    return _source_health(root, _namespace(root))[0]

def _source_for_item(item_id: int, root: Path | None = None) -> SourceRecord | None:
    value = int(item_id)
    for source in _source_rows(root):
        index = value - source.base_id
        if 0 <= index < source.record_count:
            return SourceRecord(**{**source.__dict__, "record_index": index})
    return None


def _source_with_index(source: SourceRecord, record_index: int) -> SourceRecord:
    return SourceRecord(**{**source.__dict__, "record_index": int(record_index)})


def _row_is_fresh(row: sqlite3.Row, source: SourceRecord, namespace: Path) -> bool:
    if int(row["source_size"]) != source.size or int(row["source_mtime_ns"]) != source.mtime_ns:
        return False
    if str(row["source_rom_path"]) != source.rom_path or int(row["record_index"]) != source.record_index:
        return False
    icon_file = row["icon_file"]
    return not icon_file or (namespace / str(icon_file)).is_file()


def _decode_metadata(raw: str | None) -> dict[str, Any] | None:
    if not raw:
        return None
    try:
        value = json.loads(raw)
    except (TypeError, ValueError):
        return None
    return value if isinstance(value, dict) else None


def _cached_from_row(row: sqlite3.Row, source: SourceRecord, namespace: Path, *, cache_hit: bool) -> CachedItem:
    icon_file = row["icon_file"]
    icon_path = namespace / str(icon_file) if icon_file else None
    return CachedItem(
        item_id=int(row["item_id"]), available=bool(row["available"]),
        metadata=_decode_metadata(row["metadata_json"]),
        icon_path=icon_path if icon_path and icon_path.is_file() else None,
        icon_sha256=str(row["icon_sha256"]) if row["icon_sha256"] else None,
        source=source, cache_hit=cache_hit,
    )


def _json_default(value: Any) -> Any:
    if isinstance(value, (bytes, bytearray, memoryview)):
        raw = bytes(value)
        return {"hex": raw.hex(), "bytes": len(raw)}
    if isinstance(value, Path):
        return str(value)
    return str(value)


def _write_icon(namespace: Path, item_id: int, png: bytes | None) -> tuple[str | None, str | None]:
    target = namespace / "icons" / f"{int(item_id)}.png"
    if not png:
        try:
            target.unlink()
        except FileNotFoundError:
            pass
        return None, None
    temp = target.with_suffix(".tmp")
    temp.write_bytes(png)
    temp.replace(target)
    return str(target.relative_to(namespace)).replace("\\", "/"), hashlib.sha256(png).hexdigest()


def _extract_item(item_id: int, namespace: Path) -> tuple[bool, dict[str, Any] | None, str | None, str | None]:
    record = dat_tools.read_client_item(int(item_id))
    if record is None:
        icon_file, icon_sha = _write_icon(namespace, item_id, None)
        return False, None, icon_file, icon_sha
    metadata = dat_tools.item_to_dict(record)
    icon_raw = getattr(record, "icon_data", None)
    png = dat_tools.bitmap_a_to_png(icon_raw) if icon_raw else None
    icon_file, icon_sha = _write_icon(namespace, item_id, png)
    return True, metadata, icon_file, icon_sha


def _ensure_with_connection(
    con: sqlite3.Connection,
    *,
    item_id: int,
    source: SourceRecord,
    namespace: Path,
    commit: bool,
) -> CachedItem:
    row = con.execute("SELECT * FROM item_cache WHERE item_id = ?", (int(item_id),)).fetchone()
    if row is not None and _row_is_fresh(row, source, namespace):
        return _cached_from_row(row, source, namespace, cache_hit=True)

    available, metadata, icon_file, icon_sha = _extract_item(int(item_id), namespace)
    metadata_json = json.dumps(metadata, ensure_ascii=False, separators=(",", ":"), default=_json_default) if metadata is not None else None
    con.execute(
        """
        INSERT INTO item_cache(
            item_id, available, source_category, source_rom_path, source_path,
            source_size, source_mtime_ns, record_index, metadata_json,
            icon_file, icon_sha256, cached_at
        ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(item_id) DO UPDATE SET
            available=excluded.available,
            source_category=excluded.source_category,
            source_rom_path=excluded.source_rom_path,
            source_path=excluded.source_path,
            source_size=excluded.source_size,
            source_mtime_ns=excluded.source_mtime_ns,
            record_index=excluded.record_index,
            metadata_json=excluded.metadata_json,
            icon_file=excluded.icon_file,
            icon_sha256=excluded.icon_sha256,
            cached_at=excluded.cached_at
        """,
        (
            int(item_id), 1 if available else 0, source.category, source.rom_path, str(source.path),
            source.size, source.mtime_ns, source.record_index, metadata_json,
            icon_file, icon_sha, _utc_now(),
        ),
    )
    if commit:
        con.commit()
    row = con.execute("SELECT * FROM item_cache WHERE item_id = ?", (int(item_id),)).fetchone()
    if row is None:
        raise RuntimeError(f"Unable to persist client cache row for item {item_id}")
    return _cached_from_row(row, source, namespace, cache_hit=False)


def ensure_item(item_id: int, *, source: SourceRecord | None = None) -> CachedItem | None:
    root = _client_root()
    namespace = _namespace(root)
    source = source or _source_for_item(int(item_id), root)
    if source is None:
        return None
    con = _connect(root)
    try:
        return _ensure_with_connection(con, item_id=int(item_id), source=source, namespace=namespace, commit=True)
    finally:
        con.close()


def build_source(category: str) -> dict[str, Any]:
    root = _client_root()
    namespace = _namespace(root)
    source = next((row for row in _source_rows(root) if row.category == str(category)), None)
    if source is None:
        raise KeyError(f"Unknown or unavailable item DAT category: {category}")

    started = time.perf_counter()
    hits = extracted = available = empty = failed = 0
    con = _connect(root)
    try:
        for index in range(source.record_count):
            item_id = source.base_id + index
            try:
                entry = _ensure_with_connection(
                    con,
                    item_id=item_id,
                    source=_source_with_index(source, index),
                    namespace=namespace,
                    commit=False,
                )
            except Exception:
                failed += 1
                continue
            hits += 1 if entry.cache_hit else 0
            extracted += 0 if entry.cache_hit else 1
            available += 1 if entry.available else 0
            empty += 0 if entry.available else 1
            if index and index % 250 == 0:
                con.commit()
        con.commit()
    finally:
        con.close()
    return {
        "category": source.category,
        "record_count": source.record_count,
        "cache_hits": hits,
        "extracted": extracted,
        "available": available,
        "empty": empty,
        "failed": failed,
        "elapsed_seconds": round(time.perf_counter() - started, 3),
    }


def cache_status() -> dict[str, Any]:
    root = _client_root()
    namespace = _namespace(root)
    con = _connect(root)
    try:
        row = con.execute(
            "SELECT COUNT(*) AS rows, SUM(CASE WHEN available=1 THEN 1 ELSE 0 END) AS available FROM item_cache"
        ).fetchone()
    finally:
        con.close()
    icon_bytes = sum(path.stat().st_size for path in (namespace / "icons").glob("*.png") if path.is_file())
    index_bytes = _index_path(root).stat().st_size if _index_path(root).is_file() else 0
    sources, orphaned = _source_health(root, namespace)
    total_records = sum(int(source["record_count"]) for source in sources)
    cached = int(row["rows"] or 0) if row else 0
    fresh = sum(int(source["fresh_count"]) for source in sources)
    stale = sum(int(source["stale_count"]) for source in sources)
    return {
        "client_root": str(root),
        "client_key": _client_key(root),
        "cache_root": str(namespace),
        "cached_rows": cached,
        "fresh_rows": fresh,
        "stale_rows": stale,
        "orphaned_rows": orphaned,
        "missing_rows": max(0, total_records - fresh),
        "available_rows": int(row["available"] or 0) if row else 0,
        "total_records": total_records,
        "complete": bool(total_records and fresh == total_records and not stale and not orphaned),
        "icon_bytes": icon_bytes,
        "index_bytes": index_bytes,
        "total_bytes": icon_bytes + index_bytes,
        "sources": sources,
    }


def clear_cache() -> dict[str, Any]:
    root = _client_root()
    namespace = _namespace(root)
    before = 0
    if namespace.exists():
        for path in namespace.rglob("*"):
            if path.is_file():
                try:
                    before += path.stat().st_size
                except OSError:
                    pass
        shutil.rmtree(namespace, ignore_errors=True)
    return {"status": "cleared", "client_key": _client_key(root), "bytes_removed": before}
