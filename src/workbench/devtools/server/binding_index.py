"""Read-only Lua binding source index providers for Development tooling.

This module intentionally owns only deterministic source inspection. Cached backport indexes,
diff classification, CLI behavior, and package migration policy remain in Validation/Packages.
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path

SOL_REGISTER_RE = re.compile(r'SOL_REGISTER\(\s*"([A-Za-z_][A-Za-z0-9_]*)"\s*,\s*(\w+)::')
LUNAR_DECLARE_RE = re.compile(r"LUNAR_DECLARE_METHOD\(\s*(\w+)\s*,\s*([A-Za-z_][A-Za-z0-9_]*)\s*\)")


def lua_binding_files(root: Path) -> list[Path]:
    root = Path(root)
    directory = root / "src/map/lua"
    return sorted(directory.glob("*.cpp")) if directory.is_dir() else []


def binding_source_fingerprint(root: Path) -> str:
    """Deterministic fingerprint of the Lua binding source surface."""
    root = Path(root)
    digest = hashlib.sha256()
    for path in lua_binding_files(root):
        rel = path.relative_to(root).as_posix().encode("utf-8")
        digest.update(rel + b"\0")
        digest.update(hashlib.sha256(path.read_bytes()).digest())
    return digest.hexdigest()


def build_topaz_index(root: Path) -> dict[str, list[dict]]:
    """Build name -> registration locations from SOL_REGISTER bindings."""
    root = Path(root)
    index: dict[str, list[dict]] = {}
    for path in lua_binding_files(root):
        text = path.read_text(encoding="utf-8", errors="replace")
        for match in SOL_REGISTER_RE.finditer(text):
            name, cls = match.group(1), match.group(2)
            line_no = text[: match.start()].count("\n") + 1
            index.setdefault(name, []).append(
                {"class": cls, "file": path.relative_to(root).as_posix(), "line": line_no}
            )
    return index


def build_dsp_index(root: Path) -> dict[str, list[dict]]:
    """Build name -> registration locations from legacy LUNAR_DECLARE_METHOD bindings."""
    root = Path(root)
    index: dict[str, list[dict]] = {}
    for path in lua_binding_files(root):
        text = path.read_text(encoding="utf-8", errors="replace")
        for match in LUNAR_DECLARE_RE.finditer(text):
            cls, name = match.group(1), match.group(2)
            line_no = text[: match.start()].count("\n") + 1
            index.setdefault(name, []).append(
                {"class": cls, "file": path.relative_to(root).as_posix(), "line": line_no}
            )
    return index
