"""Inventory DSP GM Lua commands without executing Lua or sending game commands.

The command catalog is descriptive, not authorization. The server's actual GM
permission checks remain authoritative. Commands default to manual-only.
"""
from __future__ import annotations

import re
from pathlib import Path

_NAME = re.compile(r"[a-zA-Z][a-zA-Z0-9_]{0,63}\Z")
_META = re.compile(r"--\s*(?:func|desc)\s*:\s*(.*)", re.I)
_PERMISSION = re.compile(r"\bpermission\s*=\s*(\d+)")
_PARAMETERS = re.compile(r'\bparameters\s*=\s*["\']([^"\']*)["\']')
_READ_ONLY = frozenset({"getmobaction", "checklocalvar"})
_MAX_FILE = 64 * 1024


def catalog_commands(server_root: str | Path, *, limit: int = 512) -> list[dict]:
    """Read a configured local server checkout's scripts/commands directory."""
    if type(limit) is not int or not 1 <= limit <= 1024:
        raise ValueError("Invalid catalog size limit")
    root = Path(server_root).resolve(strict=True)
    directory = root / "scripts" / "commands"
    if not directory.is_dir() or directory.is_symlink():
        raise ValueError("Server checkout has no trusted command directory")
    records = []
    for path in sorted(directory.glob("*.lua")):
        if len(records) >= limit:
            break
        if path.is_symlink() or not _NAME.fullmatch(path.stem):
            continue
        try:
            if path.stat().st_size > _MAX_FILE:
                continue
            source = path.read_text(encoding="utf-8-sig")
        except (OSError, UnicodeError):
            continue
        labels = {}
        for line in source.splitlines()[:35]:
            m = _META.match(line.strip())
            if m:
                value = m.group(1).strip()[:240]
                key = "function" if "func:" in line.lower() else "description"
                labels[key] = value
        permission = _PERMISSION.search(source)
        params = _PARAMETERS.search(source)
        name = path.stem.lower()
        records.append({
            "name": name,
            "command": "!" + name,
            "description": labels.get("description", ""),
            "permission": int(permission.group(1)) if permission else None,
            "parameters": params.group(1) if params else None,
            "classification": "diagnostic_candidate" if name in _READ_ONLY else "unreviewed",
            "execution_enabled": False,
            "source_path": "scripts/commands/" + path.name,
        })
    return records


def command_preview(record: dict, arguments: list[str] | None = None) -> str:
    """Build a copy-only preview. No transport or execution exists here."""
    name = record.get("name")
    if not isinstance(name, str) or not _NAME.fullmatch(name):
        raise ValueError("Invalid command name")
    arguments = arguments or []
    if len(arguments) > 8 or any(not isinstance(a, str) or not a or
       len(a) > 128 or any(c in a for c in "\r\n\x00") for a in arguments):
        raise ValueError("Invalid command arguments")
    return "!" + name + (" " + " ".join(arguments) if arguments else "")
