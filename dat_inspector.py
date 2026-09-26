"""Read-only DAT inspector: resolve a client DAT id, identify what it is, preview its contents.

Backs the Client > DAT Inspector page. Nothing here writes to the client. Type identification is
empirical -- each xi_tinkerer parser is tried in turn and only ones that parse the file cleanly are
reported -- so a result is a real parse, never a guess from the id alone. Known per-zone id
families (zone data/events/dialog/entities) are labelled from the same offsets build_database.py
uses, but are shown as a hint, not as proof of content.
"""
from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

import xi_tinkerer
from dat_extractor_bin import ensure_dat_extractor

PARSERS = (
    "parse_dialog", "parse_dmsg_table", "parse_xistring_table", "parse_entity_names",
    "parse_events", "parse_menu_table", "parse_item_info", "parse_status_info",
    "parse_auto_translate", "parse_furniture_data",
)
FAMILIES = (("zone_data", 100), ("events", 5820), ("dialog", 6420), ("entities", 6720))
PREVIEW_ITEMS = 25


def id_hint(dat_id: int) -> str | None:
    for name, base in FAMILIES:
        if base <= dat_id <= base + 255:
            return f"per-zone {name} for zoneid {dat_id - base}"
    return None


def resolve(ffxi_path: str, dat_id: int) -> dict:
    exe = ensure_dat_extractor()
    r = subprocess.run([str(exe), "--resolve", ffxi_path, str(dat_id)],
                       capture_output=True, text=True, timeout=60)
    for line in r.stdout.splitlines():
        parts = line.split("\t")
        if len(parts) >= 2 and Path(parts[1]).exists():
            return {"path": parts[1], "extractor_note": " / ".join(parts[2:])}
    raise FileNotFoundError(f"DAT id {dat_id} did not resolve to a file under {ffxi_path}")


def _preview(result) -> object:
    """Trims a parser result to something small enough to render."""
    if isinstance(result, dict):
        out = {}
        for k, v in list(result.items())[:8]:
            if isinstance(v, (list, tuple)):
                out[k] = {"count": len(v), "first": list(v[:PREVIEW_ITEMS])}
            elif isinstance(v, dict):
                out[k] = {"count": len(v), "first": dict(list(v.items())[:PREVIEW_ITEMS])}
            else:
                out[k] = v
        return out
    if isinstance(result, (list, tuple)):
        return {"count": len(result), "first": list(result[:PREVIEW_ITEMS])}
    return result


def inspect(ffxi_path: str, dat_id: int) -> dict:
    found = resolve(ffxi_path, dat_id)
    path = Path(found["path"])
    data = path.read_bytes()
    matches, rejected = [], []
    for name in PARSERS:
        try:
            matches.append({"parser": name, "preview": _preview(getattr(xi_tinkerer, name)(str(path)))})
        except Exception as ex:
            rejected.append({"parser": name, "reason": str(ex)[:140]})
    return {
        "dat_id": dat_id,
        "path": str(path),
        "rom_relative": str(path).split("FINAL FANTASY XI")[-1].lstrip("\/"),
        "size": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
        "header_hex": data[:48].hex(" "),
        "header_ascii": "".join(chr(b) if 32 <= b < 127 else "." for b in data[:48]),
        "extractor_note": found["extractor_note"],
        "family_hint": id_hint(dat_id),
        "matches": matches,
        "rejected": rejected,
    }
