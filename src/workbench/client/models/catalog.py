"""Searchable model catalog for Client > Model Viewer and Zone Editor.

The catalog is intentionally correlation-oriented rather than pretending every model DAT contains
a human-readable canonical name. It joins evidence we can actually prove:

- flat creature model ids referenced by the selected server's mob_pools / npc_list
- FFXiMain's four-band model-id -> resource file-id mapping
- the configured client's FTABLE/VTABLE resolution for those file ids
- older hand-verified visible-mesh anchors in mob_model_tables.py, kept as render hints
- server aliases, family ids, pool ids, and reference counts

This lets a DAT/file id/model id be correlated back to useful names without treating a server
name as client-authored metadata.
"""

from __future__ import annotations

from collections import defaultdict
import re

from workbench.client.models import look_decode as look
from workbench.client.models import mob_model_tables
from workbench.client.models import resolver as client_model_resolver
from workbench.client.models import schedule_dump as msd
from workbench.devtools.spatial import zone_plot
from workbench.runtime.legacy_settings import get_ffxi_install


_CACHE: dict[tuple[str, str], list[dict]] = {}


def clear_cache():
    _CACHE.clear()


def _bytes(value) -> bytes | None:
    if value is None:
        return None
    if isinstance(value, bytes):
        return value
    if isinstance(value, bytearray):
        return bytes(value)
    if isinstance(value, memoryview):
        return value.tobytes()
    if isinstance(value, str):
        raw = value.strip()
        if raw.lower().startswith("0x"):
            raw = raw[2:]
        if re.fullmatch(r"[0-9A-Fa-f]{40}", raw):
            try:
                return bytes.fromhex(raw)
            except ValueError:
                return None
    return None


def _display_name(*values) -> str:
    for value in values:
        if value is None:
            continue
        s = str(value).strip()
        if s:
            return s.replace("_", " ")
    return ""


def _empty(model_id: int) -> dict:
    file_id, rule = client_model_resolver.model_id_to_file_id(model_id)
    return {
        "model_id": int(model_id),
        "resource_file_id": int(file_id),
        "mapping_rule": rule,
        "resource_rom_path": None,
        "registered": False,
        "names": set(),
        "mob_names": set(),
        "npc_names": set(),
        "family_ids": set(),
        "pool_ids": set(),
        "source_kinds": set(),
        "mob_references": 0,
        "npc_references": 0,
        "visual_hints": {},
    }


def _pool_reference_counts(cu) -> dict[int, int]:
    try:
        cu.execute(
            "select gr.poolid,count(*) from mob_groups gr "
            "join mob_spawn_points s on s.groupid=gr.groupid "
            "and (((s.mobid-16777216)>>12)&511)=gr.zoneid group by gr.poolid"
        )
        return {int(poolid): int(count) for poolid, count in cu.fetchall()}
    except Exception:
        try:
            cu.execute("select poolid,count(*) from mob_groups group by poolid")
            return {int(poolid): int(count) for poolid, count in cu.fetchall()}
        except Exception:
            return {}


def _collect_server_models(server: str) -> dict[int, dict]:
    rows: dict[int, dict] = {}
    db = zone_plot._db(server)
    cu = db.cursor()
    try:
        pool_refs = _pool_reference_counts(cu)

        try:
            pool_cols = zone_plot._columns(cu, "mob_pools")
        except Exception:
            pool_cols = set()
        if {"poolid", "modelid"}.issubset(pool_cols):
            name_col = "name" if "name" in pool_cols else (
                "poolname" if "poolname" in pool_cols else "NULL"
            )
            family_col = "familyid" if "familyid" in pool_cols else "NULL"
            cu.execute(f"select poolid,{name_col},{family_col},modelid from mob_pools")
            for poolid, pool_name, familyid, model_raw in cu.fetchall():
                blob = _bytes(model_raw)
                if not blob or len(blob) != 20:
                    continue
                decoded = look.decode_look_data(blob, familyid=int(familyid) if familyid is not None else None)
                if decoded.get("kind") != "flat":
                    continue
                mid = int(decoded["modelid"])
                rec = rows.setdefault(mid, _empty(mid))
                label = _display_name(pool_name)
                if label:
                    rec["names"].add(label)
                    rec["mob_names"].add(label)
                rec["pool_ids"].add(int(poolid))
                if familyid is not None:
                    fid = int(familyid)
                    rec["family_ids"].add(fid)
                    visual_file_id = mob_model_tables.resolve_family_file_id(fid, mid)
                    if visual_file_id is not None:
                        family_meta = mob_model_tables.FAMILY_MODEL_TABLES.get(fid, {})
                        rec["visual_hints"][(fid, int(visual_file_id))] = {
                            "family_id": fid,
                            "family_name": family_meta.get("name"),
                            "file_id": int(visual_file_id),
                            "rom_path": None,
                            "verified": family_meta.get("verified"),
                        }
                rec["source_kinds"].add("mob_pool")
                rec["mob_references"] += int(pool_refs.get(int(poolid), 1))

        try:
            npc_cols = zone_plot._columns(cu, "npc_list")
        except Exception:
            npc_cols = set()
        if "look" in npc_cols:
            name_expr = "name" if "name" in npc_cols else "NULL"
            pol_expr = "polutils_name" if "polutils_name" in npc_cols else "NULL"
            cu.execute(f"select look,{name_expr},{pol_expr} from npc_list")
            for look_raw, name, pol_name in cu.fetchall():
                blob = _bytes(look_raw)
                if not blob or len(blob) != 20:
                    continue
                decoded = look.decode_look_data(blob)
                if decoded.get("kind") != "flat":
                    continue
                mid = int(decoded["modelid"])
                rec = rows.setdefault(mid, _empty(mid))
                label = _display_name(pol_name, name)
                if label:
                    rec["names"].add(label)
                    rec["npc_names"].add(label)
                rec["source_kinds"].add("npc_list")
                rec["npc_references"] += 1
    finally:
        db.close()
    return rows


def build_catalog(server: str | None = None, refresh: bool = False) -> list[dict]:
    server = server or zone_plot.get_server()
    ffxi_path = get_ffxi_install() or ""
    key = (server, ffxi_path)
    if not refresh and key in _CACHE:
        return _CACHE[key]

    rows = _collect_server_models(server)
    all_file_ids = {rec["resource_file_id"] for rec in rows.values()}
    for rec in rows.values():
        all_file_ids.update(h["file_id"] for h in rec["visual_hints"].values())

    resolved = msd.resolve_rom_paths(ffxi_path, all_file_ids) if ffxi_path else {}

    out = []
    for mid in sorted(rows):
        rec = rows[mid]
        rec["resource_rom_path"] = resolved.get(rec["resource_file_id"])
        rec["registered"] = rec["resource_rom_path"] is not None

        hints = []
        for (_family_id, _file_id), hint in sorted(rec["visual_hints"].items()):
            h = dict(hint)
            h["rom_path"] = resolved.get(h["file_id"])
            hints.append(h)
        rec["visual_hints"] = hints

        registered_hints = [h for h in hints if h.get("rom_path")]
        hint_file_ids = {h["file_id"] for h in registered_hints}
        render_hint = registered_hints[0] if len(hint_file_ids) == 1 else None
        rec["render_file_id"] = render_hint["file_id"] if render_hint else rec["resource_file_id"]
        rec["render_rom_path"] = render_hint["rom_path"] if render_hint else rec["resource_rom_path"]
        if render_hint:
            rec["render_source"] = "legacy hand-verified family visual DAT"
        elif len(hint_file_ids) > 1:
            rec["render_source"] = "FFXiMain monster resource; family visual hints are ambiguous"
        else:
            rec["render_source"] = "FFXiMain monster resource (may be skeleton-only)"
        rec["visual_hint_ambiguous"] = len(hint_file_ids) > 1

        rec["names"] = sorted(rec["names"], key=str.casefold)
        rec["mob_names"] = sorted(rec["mob_names"], key=str.casefold)
        rec["npc_names"] = sorted(rec["npc_names"], key=str.casefold)
        rec["family_ids"] = sorted(rec["family_ids"])
        rec["pool_ids"] = sorted(rec["pool_ids"])
        rec["source_kinds"] = sorted(rec["source_kinds"])
        rec["reference_count"] = rec["mob_references"] + rec["npc_references"]
        rec["primary_name"] = rec["names"][0] if rec["names"] else f"Model {mid}"
        rec["source_server"] = server
        out.append(rec)

    _CACHE[key] = out
    return out


def _haystack(row: dict) -> str:
    vals = [
        row.get("model_id"),
        row.get("resource_file_id"),
        row.get("render_file_id"),
        row.get("resource_rom_path"),
        row.get("render_rom_path"),
        row.get("mapping_rule"),
        *(row.get("names") or []),
        *(row.get("mob_names") or []),
        *(row.get("npc_names") or []),
        *(row.get("family_ids") or []),
        *(row.get("pool_ids") or []),
    ]
    for hint in row.get("visual_hints") or []:
        vals.extend([hint.get("family_name"), hint.get("file_id"), hint.get("rom_path")])
    return " ".join(str(v) for v in vals if v is not None).replace("\\", "/").casefold()


def search_catalog(
    q: str = "",
    *,
    server: str | None = None,
    limit: int = 100,
    refresh: bool = False,
) -> dict:
    rows = build_catalog(server, refresh=refresh)
    query = (q or "").strip().replace("\\", "/").casefold()
    matched = rows if not query else [row for row in rows if query in _haystack(row)]
    limit = max(1, min(int(limit), 500))
    return {
        "server": server or zone_plot.get_server(),
        "query": q or "",
        "total": len(rows),
        "matched": len(matched),
        "rows": matched[:limit],
        "truncated": len(matched) > limit,
        "client_configured": bool(get_ffxi_install()),
    }


def correlate(
    *,
    model_id: int | None = None,
    file_id: int | None = None,
    rom_path: str | None = None,
    server: str | None = None,
) -> list[dict]:
    rows = build_catalog(server)
    norm_path = (rom_path or "").replace("\\", "/").casefold()
    out = []
    for row in rows:
        if model_id is not None and row["model_id"] != int(model_id):
            continue
        if file_id is not None:
            ids = {row["resource_file_id"], row.get("render_file_id")}
            ids.update(h.get("file_id") for h in row.get("visual_hints") or [])
            if int(file_id) not in ids:
                continue
        if norm_path:
            paths = {row.get("resource_rom_path"), row.get("render_rom_path")}
            paths.update(h.get("rom_path") for h in row.get("visual_hints") or [])
            norm_paths = {
                str(p).replace("\\", "/").casefold()
                for p in paths if p
            }
            if norm_path not in norm_paths:
                continue
        out.append(row)
    return out
