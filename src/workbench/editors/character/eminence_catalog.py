"""Checkout-local Records of Eminence catalog for Character Editor."""
from __future__ import annotations

from pathlib import Path
import re
from typing import Any


def _clean_label(value: str) -> str:
    text = str(value or "").strip()
    # Historical files commonly suffix repeatable entries with a visual '+' marker.
    if text.endswith(" +"):
        text = text[:-2].rstrip()
    return text


def eminence_catalog(server_root: Path | str | None) -> dict[str, Any]:
    root = Path(server_root).resolve() if server_root else None
    path = root / "scripts" / "globals" / "roe_records.lua" if root else None
    source = {
        "kind": "roe_records.lua",
        "path": str(path) if path else None,
        "available": bool(path and path.is_file()),
    }
    if path is None or not path.is_file():
        return {"source": source, "items": {}}

    same_line = re.compile(r"^\s*\[\s*(\d+)\s*\]\s*=\s*\{\s*--\s*(.*?)\s*$")
    id_only = re.compile(r"^\s*\[\s*(\d+)\s*\]\s*=\s*$")
    label_line = re.compile(r"^\s*\{\s*--\s*(.*?)\s*$")

    rows: dict[int, dict[str, Any]] = {}
    pending_id: int | None = None
    in_block_comment = False
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.rstrip()
        if in_block_comment:
            if "]]" in line:
                in_block_comment = False
            continue
        if "--[[" in line:
            in_block_comment = True
            pending_id = None
            continue

        match = same_line.match(line)
        if match:
            record_id = int(match.group(1))
            label = _clean_label(match.group(2))
            if 0 <= record_id < 4096:
                rows[record_id] = {"id": record_id, "label": label or f"Record {record_id}"}
            pending_id = None
            continue

        match = id_only.match(line)
        if match:
            record_id = int(match.group(1))
            pending_id = record_id if 0 <= record_id < 4096 else None
            continue

        if pending_id is not None:
            match = label_line.match(line)
            if match:
                label = _clean_label(match.group(1))
                rows[pending_id] = {"id": pending_id, "label": label or f"Record {pending_id}"}
                pending_id = None
            elif line.strip() and not line.lstrip().startswith("--"):
                pending_id = None

    return {
        "source": source,
        "items": {str(record_id): row for record_id, row in sorted(rows.items())},
    }
