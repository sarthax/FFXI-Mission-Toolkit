"""Validation for a DSP revision change set (R6 #1210, design: R6_REGRESSION_IMPACT_DESIGN_1199_1210.md).

A change set names two full commit SHAs and the repository-relative paths that differ
between them. It is produced by ``tools/dsp_change_set.py`` on an operator's machine; this
module only validates and normalizes it. It never runs git, reads a checkout, touches a
database or opens the network.

Hunks are BASE-side (``base_sha``) 1-based inclusive line ranges. A pure insertion has no base
lines, so it is recorded as the single base line it follows (line 1 for an insertion at the
start of a file). That can over-select a neighbouring citation but never under-selects one.
"""
from __future__ import annotations

import re

SCHEMA_VERSION = 1
STATUSES = ("A", "M", "D", "R")
MAX_CHANGES = 5000
MAX_PATH_LENGTH = 500
MAX_HUNKS_PER_CHANGE = 2000
MAX_REPOSITORY_LENGTH = 200

_SHA = re.compile(r"[0-9a-fA-F]{40}")
_DRIVE = re.compile(r"^[A-Za-z]:")
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")
_TOP_KEYS = {"schema_version", "repository", "base_sha", "head_sha", "changes"}
_CHANGE_REQUIRED = {"status", "path"}
_CHANGE_ALLOWED = _CHANGE_REQUIRED | {"old_path", "hunks"}


def _sha(value: object, name: str) -> str:
    if not isinstance(value, str) or not _SHA.fullmatch(value):
        raise ValueError(f"{name} must be a full 40-character git SHA")
    return value.lower()


def _path(value: object, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} must be a non-empty string")
    if len(value) > MAX_PATH_LENGTH:
        raise ValueError(f"{name} exceeds {MAX_PATH_LENGTH} characters")
    if _CONTROL.search(value):
        raise ValueError(f"{name} contains control characters")
    if "\\" in value or _DRIVE.match(value) or value.startswith("/"):
        raise ValueError(f"{name} must be a repository-relative POSIX path: {value!r}")
    parts = value.split("/")
    if any(part in ("", ".", "..") for part in parts):
        raise ValueError(f"{name} must not contain empty, '.' or '..' segments: {value!r}")
    return value


def _hunks(value: object, name: str) -> list[list[int]]:
    if not isinstance(value, list):
        raise ValueError(f"{name} must be a list of [start, end] line ranges or null")
    if len(value) > MAX_HUNKS_PER_CHANGE:
        raise ValueError(f"{name} exceeds {MAX_HUNKS_PER_CHANGE} ranges")
    out: list[list[int]] = []
    previous_end = 0
    for index, item in enumerate(value):
        if (not isinstance(item, (list, tuple)) or len(item) != 2
                or any(type(x) is not int for x in item)):
            raise ValueError(f"{name}[{index}] must be two integers [start, end]")
        start, end = item
        if start < 1 or end < start:
            raise ValueError(f"{name}[{index}] must satisfy 1 <= start <= end")
        if start <= previous_end:
            raise ValueError(f"{name}[{index}] must be ordered and not overlap the previous range")
        previous_end = end
        out.append([start, end])
    return out


def validate_change_set(change_set: object) -> dict:
    """Return a normalized deep copy of a valid change set, or raise ``ValueError``.

    Normalization lowercases SHAs, fills ``old_path`` / ``hunks`` with ``None`` when absent and
    orders ``changes`` by ``path`` so identical content always serializes identically.
    """
    if not isinstance(change_set, dict):
        raise ValueError("change set must be an object")
    if set(change_set) != _TOP_KEYS:
        extra = sorted(set(change_set) - _TOP_KEYS)
        missing = sorted(_TOP_KEYS - set(change_set))
        raise ValueError(f"unexpected or missing change-set fields (extra={extra}, missing={missing})")
    if change_set["schema_version"] != SCHEMA_VERSION or type(change_set["schema_version"]) is not int:
        raise ValueError("unsupported change-set schema version")
    repository = change_set["repository"]
    if (not isinstance(repository, str) or not repository.strip()
            or len(repository) > MAX_REPOSITORY_LENGTH or _CONTROL.search(repository)):
        raise ValueError("repository must be a non-empty string without control characters")
    base_sha = _sha(change_set["base_sha"], "base_sha")
    head_sha = _sha(change_set["head_sha"], "head_sha")
    if base_sha == head_sha:
        raise ValueError("base_sha and head_sha must differ")
    changes = change_set["changes"]
    if not isinstance(changes, list) or len(changes) > MAX_CHANGES:
        raise ValueError(f"changes must be a list of at most {MAX_CHANGES} entries")

    normalized: list[dict] = []
    new_paths: set[str] = set()
    old_paths: set[str] = set()
    for index, change in enumerate(changes):
        label = f"changes[{index}]"
        if not isinstance(change, dict):
            raise ValueError(f"{label} must be an object")
        keys = set(change)
        if not _CHANGE_REQUIRED <= keys or not keys <= _CHANGE_ALLOWED:
            raise ValueError(f"{label} has unexpected or missing fields")
        status = change["status"]
        if status not in STATUSES:
            raise ValueError(f"{label}.status must be one of {', '.join(STATUSES)}")
        path = _path(change["path"], f"{label}.path")
        old_path = change.get("old_path")
        hunks = change.get("hunks")
        if status == "R":
            old_path = _path(old_path, f"{label}.old_path")
            if old_path == path:
                raise ValueError(f"{label}.old_path must differ from path for a rename")
        elif old_path is not None:
            raise ValueError(f"{label}.old_path is only allowed for status R")
        if hunks is not None:
            if status in ("A", "D"):
                raise ValueError(f"{label}.hunks must be null for status {status}")
            hunks = _hunks(hunks, f"{label}.hunks")
        if path in new_paths:
            raise ValueError(f"duplicate path in change set: {path!r}")
        new_paths.add(path)
        if old_path is not None:
            if old_path in old_paths:
                raise ValueError(f"duplicate old_path in change set: {old_path!r}")
            old_paths.add(old_path)
        normalized.append({"status": status, "path": path, "old_path": old_path, "hunks": hunks})

    normalized.sort(key=lambda row: (row["path"], row["status"]))
    return {"schema_version": SCHEMA_VERSION, "repository": repository,
            "base_sha": base_sha, "head_sha": head_sha, "changes": normalized}
