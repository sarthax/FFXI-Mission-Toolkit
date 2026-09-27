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
FAMILY_LABELS = {
    "zone_data": "Zone data",
    "events": "Events / cutscenes",
    "dialog": "Dialog / message text",
    "entities": "Entity names",
}
PARSER_LABELS = {
    "parse_dialog": "Dialog text",
    "parse_dmsg_table": "DMSG string table",
    "parse_xistring_table": "XI string table",
    "parse_entity_names": "Entity names",
    "parse_events": "Events / cutscenes",
    "parse_menu_table": "Menu table",
    "parse_item_info": "Item information",
    "parse_status_info": "Status information",
    "parse_auto_translate": "Auto-translate table",
    "parse_furniture_data": "Furniture data",
}
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



def dat_id_for_zone_family(zone_id: int, family: str) -> int:
    family = str(family or "").strip().lower()
    bases = dict(FAMILIES)
    if family not in bases:
        raise ValueError(f"Unknown DAT family: {family}")
    zone_id = int(zone_id)
    if zone_id < 0 or zone_id > 255:
        raise ValueError("Zone-based DAT families currently support zone IDs 0-255.")
    return bases[family] + zone_id


def _path_under_client(ffxi_path: str, dat_path: str) -> Path:
    root = Path(ffxi_path).resolve()
    candidate = Path(dat_path)
    if not candidate.is_absolute():
        candidate = root / candidate
    candidate = candidate.resolve()
    try:
        candidate.relative_to(root)
    except ValueError as ex:
        raise ValueError("DAT path must be inside the configured FFXI client root.") from ex
    if not candidate.is_file():
        raise FileNotFoundError(f"DAT file not found: {candidate}")
    if candidate.suffix.lower() != ".dat":
        raise ValueError(f"Selected file is not a .DAT file: {candidate}")
    return candidate


def _summary(result) -> dict:
    """Return compact human-readable facts without losing the raw parser preview."""
    if isinstance(result, dict):
        keys = list(result.keys())
        collection_counts = {
            str(k): len(v)
            for k, v in result.items()
            if isinstance(v, (list, tuple, dict))
        }
        return {
            "kind": "mapping",
            "top_level_fields": len(result),
            "field_names": [str(x) for x in keys[:12]],
            "collection_counts": collection_counts,
        }
    if isinstance(result, (list, tuple)):
        return {"kind": "list", "count": len(result)}
    return {"kind": type(result).__name__, "value": str(result)[:160]}


def _inspect_path(
    path: Path,
    *,
    client_root: Path | None = None,
    dat_id: int | None = None,
    extractor_note: str = "",
    family_hint: str | None = None,
) -> dict:
    data = path.read_bytes()
    matches, rejected = [], []
    for name in PARSERS:
        try:
            parsed = getattr(xi_tinkerer, name)(str(path))
            matches.append({
                "parser": name,
                "label": PARSER_LABELS.get(name, name),
                "summary": _summary(parsed),
                "preview": _preview(parsed),
            })
        except Exception as ex:
            rejected.append({
                "parser": name,
                "label": PARSER_LABELS.get(name, name),
                "reason": str(ex)[:220],
            })
    if client_root is not None:
        try:
            relative = path.resolve().relative_to(Path(client_root).resolve()).as_posix()
        except (OSError, ValueError):
            relative = path.name
    else:
        relative = path.name
    return {
        "dat_id": dat_id,
        "path": str(path),
        "rom_relative": relative,
        "filename": path.name,
        "size": len(data),
        "size_kib": round(len(data) / 1024.0, 1),
        "sha256": hashlib.sha256(data).hexdigest(),
        "header_hex": data[:64].hex(" "),
        "header_ascii": "".join(chr(b) if 32 <= b < 127 else "." for b in data[:64]),
        "extractor_note": extractor_note,
        "family_hint": family_hint,
        "matches": matches,
        "rejected": rejected,
        "parser_match_count": len(matches),
        "parser_reject_count": len(rejected),
    }


def inspect_path(ffxi_path: str, dat_path: str) -> dict:
    """Inspect a user-selected DAT path inside the configured client root."""
    path = _path_under_client(ffxi_path, dat_path)
    return _inspect_path(path, client_root=Path(ffxi_path))

def inspect(ffxi_path: str, dat_id: int) -> dict:
    found = resolve(ffxi_path, dat_id)
    return _inspect_path(
        Path(found["path"]),
        client_root=Path(ffxi_path),
        dat_id=dat_id,
        extractor_note=found["extractor_note"],
        family_hint=id_hint(dat_id),
    )
