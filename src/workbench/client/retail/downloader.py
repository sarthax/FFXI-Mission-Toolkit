"""Thin subprocess wrapper around the Rust ``ffxi-retail-selective`` tool.

The tool always runs as a separate process, never in-process, and only with arguments
validated here. Downloads go to ``<retail root>/<stamp>/`` and are never written to an
installed client directory.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any

from workbench.client.retail.catalog import retail_root
from workbench.runtime.paths import REPO_ROOT

_FILE_RE = re.compile(r"^[A-Za-z0-9_.-]+(/[A-Za-z0-9_.-]+)*$")
_STAMP_RE = re.compile(r"^\d{8}_\d+$")
_EXE = "ffxi-retail-selective.exe" if os.name == "nt" else "ffxi-retail-selective"
DEFAULT_TIMEOUT = 180
MAX_TIMEOUT = 600
CACHE_NAME = "_manifest_cache.json"


def find_exe() -> Path | None:
    env = os.environ.get("RETAIL_FETCH_EXE")
    candidates = [Path(env)] if env else []
    candidates.append(REPO_ROOT / "tools" / "retail_fetch" / "target" / "release" / _EXE)
    return next((c for c in candidates if c.is_file()), None)


def valid_file(name: str) -> str:
    if not _FILE_RE.match(name) or ".." in name.split("/"):
        raise ValueError("invalid manifest file name")
    return name


def valid_stamp(stamp: str) -> str:
    if not _STAMP_RE.match(stamp):
        raise ValueError("invalid version stamp (expected like 30261006_0)")
    return stamp


def _run(args: list[str], timeout: int) -> dict[str, Any]:
    exe = find_exe()
    if exe is None:
        return {"ok": False, "error": "downloader not built (cargo build --release in tools/retail_fetch)"}
    timeout = max(5, min(int(timeout), MAX_TIMEOUT))
    try:
        p = subprocess.run([str(exe), *args], capture_output=True, text=True, timeout=timeout, check=False)
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": f"timed out after {timeout}s"}
    return {"ok": p.returncode == 0, "stdout": p.stdout, "stderr": p.stderr.strip(),
            "error": p.stderr.strip() if p.returncode else None}


def parse_list(text: str) -> list[dict[str, str]]:
    rows = []
    for line in text.splitlines():
        m = re.match(r"^(\S+)\s+latest=(\S+)$", line.strip())
        if m:
            rows.append({"file": m.group(1), "latest": m.group(2)})
    return rows


def parse_history(text: str) -> list[dict[str, Any]]:
    rows = []
    for line in text.splitlines():
        m = re.match(r"^(\S+)\s+(\S+)\s+(\d+) bytes\s+direct=(\d+) bytes$", line.strip())
        if m:
            rows.append({"file": m.group(1), "version": m.group(2),
                         "decoded_bytes": int(m.group(3)), "transfer_bytes": int(m.group(4))})
    return rows


def _filter(rows: list[dict[str, str]], text: str) -> list[dict[str, str]]:
    t = text.lower()
    return [r for r in rows if t in r["file"].lower()][:500]


def manifest_list(filter_text: str = "", timeout: int = DEFAULT_TIMEOUT, refresh: bool = False) -> dict[str, Any]:
    """File list from a local cache; one network read only on refresh or first use."""
    cache = retail_root() / CACHE_NAME
    if not refresh and cache.is_file():
        try:
            rows = json.loads(cache.read_text(encoding="utf-8"))["files"]
            return {"ok": True, "cached": True, "files": _filter(rows, filter_text)}
        except (OSError, ValueError, KeyError):
            pass
    r = _run(["--list"], timeout)
    if not r["ok"]:
        return r
    rows = parse_list(r["stdout"])
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps({"files": rows}), encoding="utf-8")
    return {"ok": True, "cached": False, "files": _filter(rows, filter_text)}


def history(file: str, timeout: int = DEFAULT_TIMEOUT) -> dict[str, Any]:
    r = _run(["--history", "--file", valid_file(file)], timeout)
    if r["ok"]:
        r["versions"] = parse_history(r["stdout"])
    return r


def plan(file: str, stamp: str, timeout: int = DEFAULT_TIMEOUT) -> dict[str, Any]:
    return _run(["--plan", "--file", valid_file(file), "--version", valid_stamp(stamp)], timeout)


def download(file: str, stamp: str, timeout: int = DEFAULT_TIMEOUT) -> dict[str, Any]:
    out = retail_root() / valid_stamp(stamp)
    return _run(["--file", valid_file(file), "--version", stamp, "--output", str(out)], timeout)
