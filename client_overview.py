"""Service layer for Client > Overview / Build: fingerprint of the installed client (read-only).

Gathers each root-level DLL/EXE (sha256, size, PE link timestamp), the FTABLE/VTABLE DAT index files,
ROM folder counts, and any capability observations already saved for this exact build
(snapshot:client-<FFXiMain sha256[:12]>, see binary_probes.persist_probes). Nothing is written.
"""
from __future__ import annotations

import hashlib
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from workbench.client.binary_index import BinaryFormatError, index_binary

BUILD_ANCHOR = "FFXiMain.dll"
_CACHE: dict[tuple[str, float, int], dict] = {}


def _sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _binary_row(p: Path) -> dict:
    st = p.stat()
    key = (str(p), st.st_mtime, st.st_size)
    if key not in _CACHE:
        row = {"name": p.name, "size": st.st_size, "sha256": _sha256(p), "pe": None, "link_time": None}
        try:
            b = index_binary(p, max_strings=0)["binary"]
            row["pe"] = b["pe_kind"]
            if b.get("timestamp"):
                row["link_time"] = datetime.fromtimestamp(b["timestamp"], timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        except (BinaryFormatError, OSError, ValueError, KeyError):
            pass  # not a PE (or unreadable): still fingerprinted by hash
        _CACHE[key] = row
    return _CACHE[key]


def overview(install_dir: str, graph_db: Path | None = None) -> dict:
    root = Path(install_dir)
    if not root.is_dir():
        raise FileNotFoundError(f"FFXI install folder not found: {install_dir}")
    binaries = [_binary_row(p) for p in sorted(root.iterdir(), key=lambda x: x.name.lower())
                if p.is_file() and p.suffix.lower() in (".dll", ".exe")]
    tables = [{"name": n, "size": (root / n).stat().st_size} for n in ("FTABLE.DAT", "VTABLE.DAT") if (root / n).is_file()]
    roms = sorted(d.name for d in root.iterdir() if d.is_dir() and d.name.upper().startswith("ROM"))
    anchor = next((b for b in binaries if b["name"].lower() == BUILD_ANCHOR.lower()), None)
    snapshot_id = f"snapshot:client-{anchor['sha256'][:12]}" if anchor else None
    return {"install": str(root), "binaries": binaries, "tables": tables, "rom_dirs": roms,
            "build_id": anchor["sha256"][:12] if anchor else None, "snapshot_id": snapshot_id,
            "observations": saved_observations(graph_db, snapshot_id)}


def saved_observations(graph_db: Path | None, snapshot_id: str | None) -> dict:
    """Capability observations already saved for this build. graph_built=False if there is no graph yet."""
    out = {"graph_built": False, "counts": {}, "rows": []}
    if not graph_db or not snapshot_id or not Path(graph_db).is_file():
        return out
    con = sqlite3.connect(f"file:{Path(graph_db).as_posix()}?mode=ro", uri=True)
    try:
        tables = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if "capability_observations" not in tables:
            return out
        out["graph_built"] = True
        rows = con.execute(
            "SELECT capability_id, status FROM capability_observations WHERE source_snapshot_id=? ORDER BY capability_id",
            (snapshot_id,)).fetchall()
        for cap, status in rows:
            out["counts"][status] = out["counts"].get(status, 0) + 1
            out["rows"].append({"capability": cap.replace("capability:client-binary-probe:", ""), "status": status})
    finally:
        con.close()
    return out
