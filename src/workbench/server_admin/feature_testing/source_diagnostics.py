"""Bounded read-only source search for local test supervisor.

Only explicitly selected source roots are searched. Never executes files or follows
symlinks; returns short excerpts with source locations, not arbitrary file contents.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

from workbench.runtime.paths import repo_path

_ROOT_VARIABLES = {
    "toolkit": "MISSION_TOOLKIT_SUPERVISOR_TOOLKIT_SOURCE_ROOT",
    "dsp": "MISSION_TOOLKIT_SUPERVISOR_DSP_SOURCE_ROOT",
    "headless": "MISSION_TOOLKIT_SUPERVISOR_HEADLESS_SOURCE_ROOT",
}
_EXTENSIONS = frozenset({".py", ".cs", ".cpp", ".cc", ".c", ".h", ".hpp", ".lua"})
_MAX_FILES = 1500
_MAX_BYTES = 131072
_MAX_MATCHES = 20
_EXCLUDED = frozenset({".git", ".venv", "venv", "node_modules", "dist", "build", "bin", "obj", "data", "logs", "artifacts", "__pycache__", "secrets", "credentials"})
_SENSITIVE = re.compile(r"(?i)(password|secret|token|private[_-]?key|api[_-]?key|authorization)\s*[:=]")


def search_source(repository: str, term: str) -> dict:
    if repository not in _ROOT_VARIABLES:
        raise ValueError("unknown source repository")
    if not isinstance(term, str) or not 3 <= len(term.strip()) <= 80:
        raise ValueError("source search term must be 3..80 characters")
    term = term.strip()
    if any(ord(c) < 32 for c in term):
        raise ValueError("control characters not allowed")
    root_text = os.environ.get(_ROOT_VARIABLES[repository], "")
    if repository == "toolkit" and not root_text:
        root_text = str(repo_path("src"))
    if not root_text:
        return {"configured": False, "repository": repository, "matches": []}
    root = Path(root_text)
    if not root.is_absolute() or root.is_symlink() or not root.is_dir():
        raise ValueError("invalid configured source root")
    root = root.resolve(strict=True)
    results = []
    inspected = 0
    truncated = False
    # Path.glob does not traverse symlink directories with this pattern, and
    # individual files are checked again to avoid following symlinked files.
    for path in sorted(root.rglob("*")):
        if path.is_symlink() or not path.is_file() or path.suffix.lower() not in _EXTENSIONS:
            continue
        relative = path.relative_to(root)
        if any(part.lower() in _EXCLUDED or part.startswith(".") for part in relative.parts):
            continue
        if path.stat().st_size > _MAX_BYTES:
            continue
        inspected += 1
        if inspected > _MAX_FILES:
            truncated = True
            break
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        for line_no, line in enumerate(lines, 1):
            if term.casefold() not in line.casefold() or _SENSITIVE.search(line):
                continue
            excerpt = line.strip()[:240]
            results.append({"path": relative.as_posix(), "line": line_no, "excerpt": excerpt})
            if len(results) >= _MAX_MATCHES:
                truncated = True
                break
        if truncated:
            break
    return {"configured": True, "repository": repository, "term": term,
            "matches": results, "truncated": truncated,
            "files_scanned": min(inspected, _MAX_FILES),
            "source_revision": "local_checkout_unverified"}
