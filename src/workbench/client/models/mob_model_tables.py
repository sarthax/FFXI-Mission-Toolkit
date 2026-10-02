"""Per-family monster/NPC "flat" model id -> real file_id table.

These mappings are evidence-backed family-specific correlations. They deliberately do not
fall back to a universal model-id offset: callers must treat an unmapped family/range as
unresolved rather than guessing.
"""

FAMILY_MODEL_TABLES = {
    169: {
        "name": "Demon",
        "modelid_ranges": [(740, 755)],
        "dat_base": 676,
        "file_id_base": 1277,
        "rom_dir": r"ROM\7",
        "verified": (
            "2026-09-22: user-confirmed in Noesis/XI Model Viewer, all 16 modelid values "
            "(740-755) against all 16 DAT files (ROM\\7\\64.DAT-79.DAT), weapon-by-weapon."
        ),
    },
    133: {
        "name": "Goblin",
        "modelid_ranges": [(484, 511), (672, 719)],
        "dat_base": None,
        "file_id_base": 1300,
        "rom_dir": None,
        "verified": (
            "2026-09-22: file_id_base=1300 confirmed independently in both known blocks; "
            "stray modelids 1086/1090/1383 remain deliberately excluded until verified."
        ),
    },
    447: {
        "name": "Dullahan",
        "modelid_ranges": [(2605, 2605)],
        "dat_base": None,
        "file_id_base": 50295,
        "rom_dir": None,
        "verified": (
            "2026-09-22: ROM9\\1\\5.DAT identified as Dullahan and reverse-resolved through "
            "FTABLE9.DAT to file_id 52900."
        ),
    },
    26: {
        "name": "Antlion",
        "modelid_ranges": [(1347, 1348)],
        "dat_base": 1332,
        "file_id_base": 1300,
        "rom_dir": r"ROM\156",
        "verified": (
            "2026-09-22: npcs.json Antlion fileIds 2647/2648 match modelids 1347/1348 + 1300 "
            "and both resolve to real client DATs."
        ),
    },
    357: {
        "name": "Antlion (burrow/cave variant)",
        "modelid_ranges": [(1348, 1348)],
        "dat_base": 1332,
        "file_id_base": 1300,
        "rom_dir": r"ROM\156",
        "verified": (
            "2026-09-22: shares modelid 1348 with familyid 26, already confirmed at file_id 2648."
        ),
    },
    170: {
        "name": "Ladybug",
        "modelid_ranges": [(2018, 2018)],
        "dat_base": None,
        "file_id_base": 50295,
        "rom_dir": None,
        "verified": (
            "2026-09-22: npcs.json Ladybug fileId 52313 equals 2018+50295 and resolves on disk."
        ),
    },
    338: {
        "name": "Twitherym",
        "modelid_ranges": [(2535, 2536)],
        "dat_base": None,
        "file_id_base": 50295,
        "rom_dir": None,
        "verified": (
            "2026-09-22: npcs.json Twitherym fileIds 52830/52831 match modelids 2535/2536 + 50295; "
            "52830 was independently confirmed in XI Model Viewer."
        ),
    },
}


def resolve_family_file_id(familyid: int, modelid: int) -> int | None:
    """Return a verified file_id for this family/model pair, or None when unresolved."""
    entry = FAMILY_MODEL_TABLES.get(familyid)
    if not entry:
        return None
    if not any(lo <= modelid <= hi for lo, hi in entry["modelid_ranges"]):
        return None
    return modelid + entry["file_id_base"]


def resolve_family_dat_path(familyid: int, modelid: int) -> str | None:
    """Return a verified ROM-relative path where this family has a single-dir mapping."""
    entry = FAMILY_MODEL_TABLES.get(familyid)
    if not entry or entry.get("dat_base") is None or entry.get("rom_dir") is None:
        return None
    if not any(lo <= modelid <= hi for lo, hi in entry["modelid_ranges"]):
        return None
    n = modelid - entry["dat_base"]
    return f"{entry['rom_dir']}\\{n}.DAT"
