"""Model Viewer backend: resolves an NPC/mob's real model DAT from the live DB and serves its raw
bytes to the browser, where gui/static/ffxi-dat/index.js (vendored, transpiled from
github.com/Soverance/Vanalytics, MIT license -- see gui/static/ffxi-dat/README.md) parses it and
renders it with three.js. Reuses mob_look_decode.py's already-verified look_t decode and
model_schedule_dump.py's dat-extractor-backed FTABLE/VTABLE resolution rather than re-deriving
either.

MODEL_STANDARD/UNK_5/AUTOMATON ("flat") entities expose the FFXiMain model resource and, where
the earlier Noesis work proved a separate visible family mesh DAT, use that mesh as the render hint. MODEL_EQUIPED/
CHOCOBO ("gear") entities are a client-side composite of a race skeleton DAT + up to 8 per-slot
gear DATs -- the slot-id-to-file-id mapping (gear_tables.py, confirmed 2026-09-21, see its
docstring and mob_look_decode.py's) is now resolved to real ROM paths for every equipped slot.
"""
from pathlib import Path

import mob_look_decode as look
import model_schedule_dump as msd
import client_model_resolver
import mob_model_tables
import settings
import zone_plot


def _db_row(kind: str, eid: int, server=None):
    """Fetch the raw look_t blob for a mob (mob_pools.modelid, via its spawn point's poolid) or an
    NPC (npc_list.look), from the live DB."""
    db = zone_plot._db(server)
    cu = db.cursor()
    try:
        if kind == "m":
            cu.execute("select p.modelid, s.mobname, p.familyid from mob_spawn_points s "
                       "join mob_groups gr on gr.groupid=s.groupid "
                       "join mob_pools p on p.poolid=gr.poolid where s.mobid=%s", (eid,))
            row = cu.fetchone()
            familyid = row[2] if row else None
        elif kind in ("n", "d"):
            cu.execute("select look, name from npc_list where npcid=%s", (eid,))
            row = cu.fetchone()
            familyid = None  # NPCs have no familyid -- always the unverified fallback path
        else:
            raise ValueError("kind must be m/n/d")
        if not row:
            raise ValueError(f"{kind} id {eid} not found in the live DB")
        return bytes(row[0]), row[1], familyid
    finally:
        db.close()


def resolve(kind: str, eid: int, server=None) -> dict:
    """Full resolve: DB row -> decoded look_t -> real ROM path(s) via dat-extractor, using
    whichever local FFXI client install Settings has configured. Flat entities get one
    "rom_path"; gear entities get a "skeleton_rom_path" plus a "rom_path" per equipped slot
    inside "gear_resolved"."""
    blob, name, familyid = _db_row(kind, eid, server)
    info = look.decode_look_data(blob, familyid=familyid)
    info["name"] = name

    if info.get("kind") == "prop":
        return info  # door/elevator/ship -- not a model at all

    ffxi_path = settings.get_ffxi_install()
    if not ffxi_path:
        info["error"] = "no FFXI client install path configured -- set one on the Settings page"
        return info
    info["ffxi_path"] = ffxi_path

    if info.get("kind") == "flat":
        mapped = client_model_resolver.resolve_model_id(info["modelid"], ffxi_path)
        info["file_id"] = mapped["file_id"]
        info["file_id_source"] = mapped["mapping_source"]
        info["mapping_rule"] = mapped["mapping_rule"]
        info["resource_file_id"] = mapped["file_id"]
        info["resource_rom_path"] = mapped.get("rom_path")
        info["registered"] = mapped.get("registered", False)

        # The FFXiMain model-id formula identifies the monster resource/skeleton entry. Some
        # families also have a separately hand-verified visible mesh DAT from the earlier Noesis
        # investigation. Keep that as a *render hint*, not as a competing model-id formula.
        visual_fid = (
            mob_model_tables.resolve_family_file_id(int(familyid), int(info["modelid"]))
            if familyid is not None else None
        )
        visual_path = msd.resolve_rom_path(ffxi_path, visual_fid) if visual_fid is not None else None
        if visual_path:
            info["render_file_id"] = visual_fid
            info["render_rom_path"] = visual_path
            info["render_source"] = "legacy hand-verified family visual DAT"
            info["rom_path"] = visual_path
        else:
            info["render_file_id"] = mapped["file_id"]
            info["render_rom_path"] = mapped.get("rom_path")
            info["render_source"] = "FFXiMain monster resource (may be skeleton-only)"
            info["rom_path"] = mapped.get("rom_path")

        if mapped.get("error") and not visual_path:
            info["error"] = mapped["error"]
        return info

    # kind == "gear": resolve the race skeleton DAT plus every equipped slot's gear DAT.
    if info.get("skeleton_path"):
        skel_fid = None
        # skeleton_path is already a ROM-relative path (e.g. "ROM\42\4.DAT"), not a file_id --
        # dat-extractor's resolve_rom_path takes a file_id, so just use the path as-is; confirm
        # it exists on disk under the configured install.
        skel_full = Path(ffxi_path) / info["skeleton_path"]
        info["skeleton_rom_path"] = info["skeleton_path"] if skel_full.exists() else None
        if not info["skeleton_rom_path"]:
            info.setdefault("errors", []).append(
                f"skeleton DAT not found on disk: {skel_full}")
    else:
        info.setdefault("errors", []).append(
            f"no skeleton DAT mapping for race {info.get('race_name')!r}")

    for slot, resolved in info.get("gear_resolved", {}).items():
        fid = resolved.get("file_id")
        if fid is None:
            resolved["rom_path"] = None
            continue
        rom_path = msd.resolve_rom_path(ffxi_path, fid)
        resolved["rom_path"] = rom_path
        if not rom_path:
            info.setdefault("errors", []).append(
                f"dat-extractor found no ROM file for {slot} file_id {fid}")

    return info


def read_dat_bytes(ffxi_path: str, rom_path: str) -> bytes:
    """Read the actual DAT bytes off the local client install disk. rom_path is dat-extractor's
    own output (e.g. "ROM2/34/12.DAT"), always relative to the install root."""
    p = Path(ffxi_path) / rom_path
    if not p.exists():
        raise FileNotFoundError(f"{p} does not exist under the configured FFXI install")
    return p.read_bytes()



def resolve_model_id(model_id: int, ffxi_path: str | None = None) -> dict:
    """Direct Client-tool entry point: raw server look_t model id -> file id -> real DAT."""
    return client_model_resolver.resolve_model_id(model_id, ffxi_path)
