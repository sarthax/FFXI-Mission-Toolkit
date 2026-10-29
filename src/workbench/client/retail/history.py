"""Immutable, provenance-aware observations of PlayOnline manifest history.

An observed revision is not proof its patch payload is still available.
Snapshots are deliberately separate from downloaded artifact sidecars.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

STAMP = re.compile(r"^\d{8}_\d+$")
PATH = re.compile(r"^[A-Za-z0-9_.-]+(/[A-Za-z0-9_.-]+)*$")
MAX_SNAPSHOT_BYTES = 64 * 1024 * 1024


def _validate(data: dict) -> dict:
    if data.get("schema") != 1 or data.get("source") != "playonline-patch-manifest:ffxi":
        raise ValueError("unsupported manifest history schema/source")
    files = data.get("files")
    if not isinstance(files, list):
        raise ValueError("missing files list")
    checked = []
    seen = set()
    for item in files:
        if not isinstance(item, dict):
            raise ValueError("invalid file record")
        name = item.get("file")
        if not isinstance(name, str) or not PATH.fullmatch(name) or ".." in name.split("/"):
            raise ValueError("invalid manifest file path")
        if name.casefold() in seen:
            raise ValueError("duplicate manifest file")
        seen.add(name.casefold())
        versions = item.get("versions")
        if not isinstance(versions, list):
            raise ValueError("missing versions")
        vseen = set()
        out = []
        for v in versions:
            if not isinstance(v, dict) or not isinstance(v.get("stamp"), str) or not STAMP.fullmatch(v["stamp"]):
                raise ValueError("invalid stamp")
            if v["stamp"] in vseen:
                raise ValueError("duplicate stamp")
            vseen.add(v["stamp"])
            direct = v.get("server_path")
            if not isinstance(direct, str) or not PATH.fullmatch(direct) or ".." in direct.split("/"):
                raise ValueError("invalid transfer path")
            sizes = [v.get("decoded_bytes"), v.get("transfer_bytes")]
            if any(type(n) is not int or n < 0 for n in sizes):
                raise ValueError("invalid file size")
            out.append({"stamp": v["stamp"], "decoded_bytes": sizes[0],
                        "transfer_bytes": sizes[1], "server_path": direct})
        checked.append({"file": name, "versions": out})
    return {"schema": 1, "source": data["source"], "files": checked}


def store_snapshot(raw: bytes, root: Path, *, observed_utc: str | None = None) -> dict:
    """Content-address raw validated export; never overwrite an existing observation."""
    if len(raw) > MAX_SNAPSHOT_BYTES:
        raise ValueError("snapshot exceeds size limit")
    data = _validate(json.loads(raw))
    canonical = (json.dumps(data, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    digest = hashlib.sha256(canonical).hexdigest()
    when = observed_utc or datetime.now(timezone.utc).isoformat()
    # Canonical payload is immutable. Re-observing same content never mutates it.
    snapshots = root / "snapshots"
    snapshots.mkdir(parents=True, exist_ok=True)
    dest = snapshots / (digest + ".json")
    try:
        with dest.open("xb") as f:
            f.write(canonical)
    except FileExistsError:
        if dest.read_bytes() != canonical:
            raise ValueError("existing snapshot has wrong hash")
    # Append-only capture log preserves repeated observations without touching snapshots.
    log = root / "observations.jsonl"
    record = {"schema": 1, "sha256": digest, "observed_utc": when,
              "file_count": len(data["files"]), "source": data["source"]}
    with log.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, sort_keys=True) + "\n")
    return record


def search(root: Path, *, file_contains: str = "", stamp: str = "") -> list[dict]:
    """Union all verified snapshots, never mistake missing history for nonexistence."""
    combined: dict[tuple[str, str], dict] = {}
    for path in sorted((root / "snapshots").glob("*.json")):
        if not re.fullmatch(r"[0-9a-f]{64}\.json", path.name):
            continue
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != path.stem:
            raise ValueError(f"snapshot corruption: {path.name}")
        data = _validate(json.loads(raw))
        for entry in data["files"]:
            if file_contains.casefold() not in entry["file"].casefold():
                continue
            for v in entry["versions"]:
                if stamp and stamp != v["stamp"]:
                    continue
                key = (entry["file"].casefold(), v["stamp"])
                row = {"file": entry["file"], **v, "snapshot_sha256": path.stem,
                       "availability": "UNKNOWN"}
                if key in combined:
                    current = combined[key]
                    if (current["decoded_bytes"], current["transfer_bytes"], current["server_path"]) != (
                        row["decoded_bytes"], row["transfer_bytes"], row["server_path"]):
                        current["availability"] = "CONFLICTING_MANIFESTS"
                        current.setdefault("conflicts", []).append(row)
                    else:
                        current.setdefault("also_observed_in", []).append(path.stem)
                else:
                    combined[key] = row
    return sorted(combined.values(), key=lambda x: (x["file"].casefold(), x["stamp"]))


def capture_current(root: Path, *, timeout: int = 180) -> dict:
    """Explicit network operation, requiring the existing built Rust downloader."""
    from workbench.client.retail.downloader import _run
    result = _run(["--export-history-json"], timeout)
    if not result["ok"]:
        raise RuntimeError(result.get("error") or "manifest export failed")
    return store_snapshot(result["stdout"].encode("utf-8"), root)
