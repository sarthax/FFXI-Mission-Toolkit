"""Catalog of retail client binaries fetched by tools/retail_fetch.

Source of truth is the ``<file>.provenance.json`` sidecar the downloader writes only after
size and manifest-signature validation. The catalog never trusts a sidecar alone: it
re-hashes the file on disk and reports the result. Retail binaries live under their own
root, separate from DSP server artifacts and capture packages, and never enter Git.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

from workbench.runtime.paths import REPO_ROOT

SIDECAR_SUFFIX = ".provenance.json"


BUILTIN_ROOT = REPO_ROOT / ".workbench" / "client-binaries" / "retail"
CLIENT_SUBDIR = "RetailVersions"


def _saved_root() -> str:
    """Folder chosen manually on the Retail Version Explorer page ('' when none)."""
    try:
        import sqlite3
        from workbench.runtime import settings_store
        con = sqlite3.connect(str(settings_store.DB_PATH))
        try:
            return (settings_store.get(con, "retail_root") or "").strip()
        finally:
            con.close()
    except Exception:
        return ""


def _client_folder() -> str | None:
    """The FFXI client folder configured in Settings (or auto-detected from the registry)."""
    try:
        from workbench.runtime import settings_store
        return settings_store.get_ffxi_install()
    except Exception:
        return None


def retail_root_info() -> dict[str, Any]:
    """Resolve the retail catalog folder and say where the choice came from.

    Order: WORKBENCH_RETAIL_ROOT, a folder chosen on the page, <client folder>/RetailVersions,
    then the repo-local built-in folder. A subfolder of the client install is used (not the
    install itself) so catalog scans stay small and downloads stay out of the game files."""
    client = _client_folder()
    client_default = Path(client) / CLIENT_SUBDIR if client else None
    default = client_default or BUILTIN_ROOT
    env = os.environ.get("WORKBENCH_RETAIL_ROOT")
    saved = _saved_root()
    if env:
        path, source = Path(env), "env"
    elif saved:
        path, source = Path(saved), "setting"
    elif client_default:
        path, source = client_default, "client"
    else:
        path, source = BUILTIN_ROOT, "builtin"
    return {"path": path, "source": source, "default": default, "client": client, "saved": saved}


def retail_root() -> Path:
    return retail_root_info()["path"]


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _inside(root: Path, p: Path) -> bool:
    try:
        p.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _entry(root: Path, sidecar: Path) -> dict[str, Any]:
    binary = Path(str(sidecar)[: -len(SIDECAR_SUFFIX)])
    out: dict[str, Any] = {"sidecar": str(sidecar), "path": str(binary), "problems": []}
    try:
        meta = json.loads(sidecar.read_text(encoding="utf-8"))
    except (OSError, ValueError) as ex:
        out.update(file=binary.name, version="?", status="INVALID_SIDECAR")
        out["problems"].append(f"unreadable sidecar: {ex}")
        return out
    out.update(
        file=str(meta.get("file", binary.name)),
        version=str(meta.get("retail_version", "?")),
        sha256=str(meta.get("sha256", "")),
        expected_bytes=meta.get("expected_decoded_bytes"),
        retrieved_utc=meta.get("retrieved_utc"),
        signature_verified=bool(meta.get("manifest_signature_verified")),
        downloader=meta.get("downloader"),
    )
    if not _inside(root, binary):
        out["problems"].append("binary resolves outside the retail root")
    elif not binary.is_file():
        out["problems"].append("binary file is missing")
    else:
        size = binary.stat().st_size
        out["actual_bytes"] = size
        if out["expected_bytes"] is not None and size != out["expected_bytes"]:
            out["problems"].append(f"size {size} differs from recorded {out['expected_bytes']}")
        actual = _sha256(binary)
        out["actual_sha256"] = actual
        if actual != out["sha256"]:
            out["problems"].append("SHA-256 differs from sidecar")
    if not out["signature_verified"]:
        out["problems"].append("sidecar does not record a verified manifest signature")
    if not out["problems"]:
        out["status"] = "VALID"
    elif any("missing" in p for p in out["problems"]):
        out["status"] = "MISSING"
    else:
        out["status"] = "INVALID"
    return out


def scan(root: Path | None = None) -> list[dict[str, Any]]:
    """All catalog entries, ordered by file then version. Identical (file, sha256) pairs
    collapse to one entry listing every duplicate path; different versions coexist."""
    root = root or retail_root()
    if not root.is_dir():
        return []
    by_identity: dict[tuple[str, str], dict[str, Any]] = {}
    extra: list[dict[str, Any]] = []
    for sidecar in sorted(root.rglob("*" + SIDECAR_SUFFIX)):
        e = _entry(root, sidecar)
        if e["status"] != "VALID":
            extra.append(e)
            continue
        key = (e["file"].lower(), e["sha256"])
        if key in by_identity:
            by_identity[key].setdefault("duplicates", []).append(e["path"])
        else:
            by_identity[key] = e
    rows = list(by_identity.values()) + extra
    rows.sort(key=lambda r: (r["file"].lower(), r["version"]))
    return rows


def find(file: str, version: str, root: Path | None = None) -> dict[str, Any] | None:
    for r in scan(root):
        if r["file"].lower() == file.lower() and r["version"] == version and r["status"] == "VALID":
            return r
    return None
