"""Read-only DAT inspector: resolve a client DAT id, identify what it is, preview its contents.

Backs the Client > DAT Inspector page. Nothing here writes to the client. Type identification is
empirical -- each xi_tinkerer parser is tried in turn and only ones that parse the file cleanly are
reported -- so a result is a real parse, never a guess from the id alone. Known per-zone id
families (zone data/events/dialog/entities) are labelled from the same offsets build_database.py
uses, but are shown as a hint, not as proof of content.
"""
from __future__ import annotations

import hashlib
import struct
import subprocess
from pathlib import Path

try:
    import xi_tinkerer
except ModuleNotFoundError:
    xi_tinkerer = None

from workbench.client.dat.extractor_bin import ensure_dat_extractor

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

def parser_capabilities() -> dict:
    """Report this installation's actual callable decoders, not guessed DAT support.

    The registry is the Inspector's known API surface; an installed binding may expose
    fewer methods. Presence is not evidence that any particular DAT will parse.
    """
    installed = xi_tinkerer is not None
    rows = [{
        "parser": name,
        "label": PARSER_LABELS.get(name, name),
        "tool_kind": PARSER_TOOL_KIND.get(name, "generic"),
        "available": bool(installed and callable(getattr(xi_tinkerer, name, None))),
    } for name in PARSERS]
    return {
        "bindings_installed": installed,
        "registered_count": len(rows),
        "available_count": sum(1 for row in rows if row["available"]),
        "parsers": rows,
        "note": "Parser availability does not verify support for an individual DAT; inspect a file to establish evidence.",
    }


BLOCK_TYPE_LABELS = {
    32: "Texture",
    41: "Skeleton",
    42: "Skeleton mesh",
    43: "Skeleton animation",
}


def scan_sections(data: bytes) -> dict:
    """Inventory the generic block chain without interpreting section semantics beyond known types."""
    rows = []
    offset = 0
    seen = set()
    warnings = []
    while offset + 8 <= len(data):
        if offset in seen:
            warnings.append(f"block chain loop detected at 0x{offset:X}")
            break
        seen.add(offset)

        raw_name = data[offset:offset + 4]
        name = "".join(chr(b) if 32 <= b < 127 else "." for b in raw_name)
        packed = struct.unpack_from("<I", data, offset + 4)[0]
        type_id = packed & 0x7F
        next_units = (packed >> 7) & 0x7FFFF
        block_size = next_units * 16

        terminal = next_units == 0
        if not terminal and block_size < 8:
            warnings.append(
                f"section {len(rows)} at 0x{offset:X} has invalid block size {block_size}"
            )
            block_size = 0

        effective_size = (
            max(0, len(data) - offset) if terminal else min(block_size, max(0, len(data) - offset))
        )
        truncated = (not terminal and block_size > len(data) - offset)
        rows.append({
            "index": len(rows),
            "name": name.rstrip("\x00"),
            "name_hex": raw_name.hex(" "),
            "type_id": type_id,
            "type_label": BLOCK_TYPE_LABELS.get(type_id, f"Unknown type {type_id}"),
            "offset": offset,
            "offset_hex": f"0x{offset:X}",
            "size": effective_size,
            "declared_size": block_size,
            "terminal": terminal,
            "truncated": truncated,
        })

        if terminal:
            break
        if block_size <= 0:
            break
        offset += block_size
        if len(rows) >= 2000:
            warnings.append("section scan stopped after 2000 blocks")
            break

    counts = {}
    for row in rows:
        counts[row["type_label"]] = counts.get(row["type_label"], 0) + 1
    return {
        "sections": rows,
        "section_count": len(rows),
        "type_counts": counts,
        "warnings": warnings,
    }


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


FAMILY_EXPECTED_PARSERS = {
    "events": {"parse_events"},
    "dialog": {"parse_dialog", "parse_dmsg_table", "parse_xistring_table"},
    "entities": {"parse_entity_names"},
}
PARSER_TOOL_KIND = {
    "parse_events": "events",
    "parse_dialog": "dialog",
    "parse_dmsg_table": "dialog",
    "parse_xistring_table": "dialog",
    "parse_entity_names": "entities",
    "parse_item_info": "items",
    "parse_menu_table": "menu",
    "parse_status_info": "status",
    "parse_auto_translate": "auto_translate",
    "parse_furniture_data": "furniture",
}


def resource_context(dat_id: int | None) -> dict:
    if dat_id is None:
        return {"family": None, "zone_id": None}
    for name, base in FAMILIES:
        if base <= int(dat_id) <= base + 255:
            return {"family": name, "zone_id": int(dat_id) - base}
    return {"family": None, "zone_id": None}


def _sample_rows(value, limit: int = 12) -> list[dict]:
    rows = []
    if isinstance(value, dict):
        for key, item in list(value.items())[:limit]:
            if isinstance(item, dict):
                row = {"key": key}
                row.update({str(k): v for k, v in list(item.items())[:8] if not isinstance(v, (list, tuple, dict))})
            else:
                row = {"key": key, "value": item}
            rows.append(row)
        return rows
    if isinstance(value, (list, tuple)):
        for idx, item in enumerate(list(value)[:limit]):
            if isinstance(item, dict):
                row = {"#": idx}
                row.update({str(k): v for k, v in list(item.items())[:8] if not isinstance(v, (list, tuple, dict))})
            else:
                row = {"#": idx, "value": item}
            rows.append(row)
    return rows


def _presentation(result) -> dict:
    scalars = []
    collections = []
    if isinstance(result, dict):
        for key, value in result.items():
            if isinstance(value, (list, tuple, dict)):
                collections.append({
                    "name": str(key),
                    "count": len(value),
                    "rows": _sample_rows(value),
                })
            else:
                scalars.append({"name": str(key), "value": value})
    elif isinstance(result, (list, tuple)):
        collections.append({
            "name": "entries",
            "count": len(result),
            "rows": _sample_rows(result),
        })
    else:
        scalars.append({"name": "value", "value": result})
    return {"scalars": scalars[:24], "collections": collections[:12]}


def _classify(matches: list[dict], family: str | None) -> dict:
    names = [m["parser"] for m in matches]
    warnings = []
    if not matches:
        verdict = "No supported structured parser recognized this DAT"
        status = "unknown"
        confidence = "unclassified"
    elif len(matches) == 1:
        verdict = f"Decoded as {matches[0]['label']}"
        status = "recognized"
        confidence = "parser accepted"
    else:
        verdict = f"{len(matches)} compatible parser interpretations"
        status = "multiple"
        confidence = "ambiguous structure"
        warnings.append(
            "Multiple parsers accepted this DAT. Keep each interpretation separate until additional evidence identifies the resource type."
        )

    expected = FAMILY_EXPECTED_PARSERS.get(family or "")
    if family and expected and matches and not (set(names) & expected):
        warnings.append(
            f"The DAT ID falls in the {FAMILY_LABELS.get(family, family)} zone-family range, "
            "but none of the expected parsers accepted it. Treat the family as an ID hint only."
        )
    return {
        "status": status,
        "verdict": verdict,
        "confidence": confidence,
        "warnings": warnings,
        "parser_names": names,
    }


def _inspect_path(
    path: Path,
    *,
    client_root: Path | None = None,
    dat_id: int | None = None,
    extractor_note: str = "",
    family_hint: str | None = None,
) -> dict:
    if xi_tinkerer is None:
        raise RuntimeError(
            "xi-tinkerer Python bindings are not available. Install/build xi-tinkerer before decoding DAT contents."
        )
    data = path.read_bytes()
    matches, rejected = [], []
    for name in PARSERS:
        parser = getattr(xi_tinkerer, name, None)
        if not callable(parser):
            rejected.append({
                "parser": name,
                "label": PARSER_LABELS.get(name, name),
                "reason": "Decoder not available in the installed xi-tinkerer bindings",
                "unavailable": True,
            })
            continue
        try:
            parsed = parser(str(path))
            matches.append({
                "parser": name,
                "label": PARSER_LABELS.get(name, name),
                "summary": _summary(parsed),
                "presentation": _presentation(parsed),
                "preview": _preview(parsed),
                "tool_kind": PARSER_TOOL_KIND.get(name, "generic"),
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
    context = resource_context(dat_id)
    classification = _classify(matches, context["family"])
    section_scan = scan_sections(data)
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
        "family": context["family"],
        "zone_id": context["zone_id"],
        "classification": classification,
        "parser_capabilities": parser_capabilities(),
        "section_scan": section_scan,
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
