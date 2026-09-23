"""Per-family monster/NPC "flat" model id -> real file_id table.

Replaces the disproven assumption (formerly `ENTITY_MODEL_OFFSET = 98239` applied universally to
every MODEL_STANDARD/UNK_5/AUTOMATON modelid in mob_look_decode.py / model_schedule_dump.py) --
that constant is, in xi-model-viewer's own source (ui/js/dattypes.js:138), only a fileId
CLASSIFICATION threshold ("is this fid in the composited-PC-Model range"), never a monster-model
additive offset. Proven wrong 2026-09-22 for both a MODEL_AUTOMATON (Troll_Ironworker -> resolved
to an unrelated NPC, Ulmia) and a MODEL_STANDARD (Abyssal_Demon -> resolved to an unrelated DAT).

Real mechanism (per family, NOT universal): each mob family's `modelid` values map onto a real
DAT file via a per-family CONSTANT ADDITIVE OFFSET (`file_id = modelid + file_id_base`). The
modelid values themselves are not always one contiguous block -- a family can have several
disjoint modelid ranges (e.g. different Assault/expansion-era reskins), but the same offset has
held across every range confirmed so far. Never assume a family's offset without independently
verifying at least one point in each disjoint range -- a formula that works for one block is not
proof it holds for another block of the same family (see Goblin below, which needed 2 separate
confirmations for its 2 known blocks before being trusted).

CONFIRMED families (2026-09-22):

  familyid 169, Demon -- modelid 740..755 (16 values, every Demon-family mob_pools row) <->
    ROM\\7\\64.DAT..79.DAT (16 files, user-verified in Noesis/XI Model Viewer weapon-by-weapon:
    64=sword, 65=rapier, 66=sword, 67=scythe, 68=stave, 69=scythe, 70=sword, 71=axe, 72=club,
    73=rapier, 74=club, 75=scythe, 76=scythe, 77=stave, 78=stave, 79=stave) -- a clean, gapless
    bijection. file_id_base = 1277 (file_id = modelid + 1277 = 1953 + (modelid-676), and
    ROM\\7\\N.DAT = file_id 1953+N per a dat-extractor --resolve batch scan of file_ids
    1000-6999). Also confirmed: `cmbSkill` (server combat mechanics) does NOT reliably correlate
    with the visual weapon -- the same modelid/DAT shows up across mobs with different cmbSkill
    values (visual flavor and combat mechanics are independently chosen). `mJob` correlates
    better for at least one case (all 4 stave/pole-visual modelids -- 744, 753, 754, 755 -- have
    mJob=15/SMN), but that's a secondary sanity signal, not the derivation itself.

  familyid 133, Goblin -- file_id_base = 1300 (file_id = modelid + 1300), confirmed independently
    across BOTH of its known disjoint modelid blocks:
      block 484-511 (~28 mob_pools rows, ROM\\6\\*.DAT range): 3-for-3 EXACT name-matched
        confirmation against xi-model-viewer's npcs.json (which independently lists each of
        these by the same in-game name):
          Goblin_Bounty_Hunter modelid=497 -> file_id 1797 -> ROM\\6\\2.DAT (npcs.json: same path)
          Goblin_Franctireur   modelid=501 -> file_id 1801 -> ROM\\6\\6.DAT (npcs.json: same path)
          Goblin_Bouncer       modelid=503 -> file_id 1803 -> ROM\\6\\8.DAT (npcs.json: same path)
      block 672-719 (ROM3\\7\\*.DAT range, no npcs.json name anchor available): 2-point
        weapon-plausibility spot check via Noesis --
          Goblin_Marksman (modelid 680) -> file_id 1980 -> ROM3\\7\\64.DAT -- holding a gun
            (RNG/THF-flavored weapon, consistent with "Marksman")
          modelid 672            -> file_id 1972 -> ROM3\\7\\57.DAT -- holding an axe
            (generic beastman-flavored weapon, plausible)
    Not yet individually verified: the family's smaller stray modelids (1086, 1090, 1383) --
    treat those as UNVERIFIED even though they belong to familyid 133, until spot-checked the
    same way. (resolve_family_file_id() currently has no range gate for Goblin, since the offset
    has held for both ranges checked so far and a stray modelid is far more likely to be a
    third block of the same +1300 pattern than a break in it -- but this is a judgment call, not
    a proof; revisit if a stray modelid ever comes back visually wrong.)

  familyid 447, Dullahan -- single-modelid family (ALL 4 mob_pools rows -- Dullahan, Balamor's
    Sycop, Regicidal Dullahan, Crom Dubh -- share modelid 2605, so there is no range to sweep,
    this one confirmed point covers the whole family). file_id_base = 50295 (file_id = modelid +
    50295), confirmed via direct FTABLE9.DAT reverse lookup (not dat-extractor --resolve
    brute-force -- see resolve_dat_path_to_file_id() pattern in session notes): user identified
    ROM9\\1\\5.DAT as Dullahan's real model in Noesis, reverse-searching FTABLE9.DAT's raw
    dir*128+file value found it at table offset 52900 -- i.e. file_id 52900 = modelid 2605 +
    50295. Note ToAU-era mob families (Trolls, Dullahans, etc.) do NOT get individually-named
    body entries in xi-model-viewer's npcs.json the way older-era families (Demon, Goblin) do --
    confirmed by the user; only generic shared "Weapons"/accessory sets are listed for them, which
    are sub-resource files with no FTABLE entry of their own and do NOT correlate with body
    modelid the way per-body-model files do. A named anchor for a ToAU-era family has to come from
    a real Noesis identification of the actual body DAT, not from npcs.json.

THIS TABLE IS PER-FAMILY AND MUST NOT BE ASSUMED TO GENERALIZE. Only add an entry once a family's
modelid range has been independently verified the same way (real Noesis/XI-Model-Viewer look at
the resolved DAT(s), not just a formula guess) -- see docs/project-memory/06-failed-approaches.md
for why a single universal offset was wrong twice already for this exact class of bug.

Usage:
    from mob_model_tables import resolve_family_file_id
    file_id = resolve_family_file_id(familyid, modelid)   # None if family/modelid unverified
"""

# {familyid: {"name": str, "modelid_ranges": [(lo, hi), ...],   # disjoint blocks OK
#             "file_id_base": int,   # file_id = modelid + file_id_base, same offset for every block
#             "dat_base": int|None,  # only set when every block lives under ONE rom_dir (see Demon)
#             "rom_dir": str|None,   # informational -- which ROM subdir, only when single-dir
#             "verified": str}}      # how/when this entry was confirmed -- never leave this blank
FAMILY_MODEL_TABLES = {
    169: {
        "name": "Demon",
        "modelid_ranges": [(740, 755)],
        "dat_base": 676,        # ROM\7\N.DAT where N = modelid - 676
        "file_id_base": 1277,   # file_id = modelid + 1277  (== 1953 + (modelid - 676))
        "rom_dir": r"ROM\7",
        "verified": (
            "2026-09-22: user-confirmed in Noesis/XI Model Viewer, all 16 modelid values "
            "(740-755) against all 16 DAT files (ROM\\7\\64.DAT-79.DAT), weapon-by-weapon. "
            "Gapless bijection, no assumptions left unverified in this range."
        ),
    },
    133: {
        "name": "Goblin",
        "modelid_ranges": [(484, 511), (672, 719)],  # stray 1086/1090/1383 NOT included -- unverified
        "dat_base": None,       # spans ROM\6 (block 1) and ROM3\7 (block 2) -- no single rom_dir
        "file_id_base": 1300,   # file_id = modelid + 1300
        "rom_dir": None,
        "verified": (
            "2026-09-22: file_id_base=1300 confirmed independently in both known blocks -- "
            "block 484-511 via 3 exact npcs.json name matches (Goblin_Bounty_Hunter, "
            "Goblin_Franctireur, Goblin_Bouncer, all landing on npcs.json's own path for that "
            "exact name); block 672-719 via 2-point Noesis weapon-plausibility spot check "
            "(Goblin_Marksman/modelid 680 -> gun, modelid 672 -> axe). Stray modelids 1086/1090/"
            "1383 belong to familyid 133 but are NOT covered by modelid_ranges above -- "
            "deliberately excluded until independently spot-checked."
        ),
    },
    447: {
        "name": "Dullahan",
        "modelid_ranges": [(2605, 2605)],  # single-modelid family -- all 4 mob_pools rows share it
        "dat_base": None,       # ROM9\1\5.DAT -- single point, no need for a dat_base/rom_dir formula
        "file_id_base": 50295,  # file_id = modelid + 50295 (2605 + 50295 = 52900)
        "rom_dir": None,
        "verified": (
            "2026-09-22: user-identified ROM9\\1\\5.DAT as Dullahan's real model in Noesis. "
            "Reverse-resolved via FTABLE9.DAT (dir=1,file=5 -> raw value 133 -> table offset "
            "52900) rather than dat-extractor --resolve brute force. All 4 familyid-447 rows "
            "(Dullahan, Balamor's_Sycop, Regicidal_Dullahan, Crom_Dubh) share modelid 2605, so "
            "this single point fully covers the family -- no sweep needed."
        ),
    },
    26: {
        "name": "Antlion",
        "modelid_ranges": [(1347, 1348)],  # every familyid-26 row uses one of these two values
        "dat_base": 1332,        # ROM\156\N.DAT where N = modelid - 1332 (15/16)
        "file_id_base": 1300,    # file_id = modelid + 1300
        "rom_dir": r"ROM\156",
        "verified": (
            "2026-09-22: npcs.json's Vermin/Antlion entry lists fileIds [2647, 2648, ...]; "
            "2647 = 1347+1300 -> ROM\\156\\15.DAT, 2648 = 1348+1300 -> ROM\\156\\16.DAT, both "
            "resolved to real on-disk DATs via dat-extractor. The entry's other 3 fileIds "
            "(53165, 52509, 53166) did NOT match either modelid under the same formula -- "
            "likely a different familyid's NM variant bundled into the same npcs.json name; not "
            "yet chased down, left unmapped here."
        ),
    },
    357: {
        "name": "Antlion (burrow/cave variant)",
        "modelid_ranges": [(1348, 1348)],  # single-modelid family, all familyid-357 rows share it
        "dat_base": 1332,
        "file_id_base": 1300,    # file_id = modelid + 1300 -- same offset as familyid 26
        "rom_dir": r"ROM\156",
        "verified": (
            "2026-09-22: shares modelid 1348 with familyid 26's Anthracite/Executioner Antlion, "
            "and npcs.json's Antlion fileIds already confirm 1348+1300 -> ROM\\156\\16.DAT is a "
            "real DAT (see familyid 26 entry) -- same body model reused across both family ids."
        ),
    },
    170: {
        "name": "Ladybug",
        "modelid_ranges": [(2018, 2018)],  # single-modelid family, all 3 familyid-170 rows share it
        "dat_base": None,
        "file_id_base": 50295,   # file_id = modelid + 50295
        "rom_dir": None,
        "verified": (
            "2026-09-22: npcs.json's Vermin/Ladybug entry lists fileId 52313 = 2018+50295 -> "
            "ROM\\207\\7.DAT, resolved to a real on-disk DAT via dat-extractor."
        ),
    },
    338: {
        "name": "Twitherym",
        "modelid_ranges": [(2535, 2536)],  # every familyid-338 row uses one of these two values
        "dat_base": None,        # ROM9\0\N.DAT -- N doesn't reduce to a clean modelid-based dat_base
        "file_id_base": 50295,   # file_id = modelid + 50295
        "rom_dir": None,
        "verified": (
            "2026-09-22: npcs.json's Vermin/Twitherym entry lists fileIds [52830, 52831, ...]; "
            "52830 = 2535+50295 -> ROM9\\0\\63.DAT, 52831 = 2536+50295 -> ROM9\\0\\64.DAT, both "
            "resolved to real on-disk DATs via dat-extractor -- 52830/ROM9\\0\\63.DAT is also the "
            "exact file the user had open in XI Model Viewer (screenshot), independent confirmation."
        ),
    },
}


def resolve_family_file_id(familyid: int, modelid: int) -> int | None:
    """Real file_id for a flat (MODEL_STANDARD/UNK_5/AUTOMATON) modelid, using this family's
    verified table entry. Returns None if the family has no entry yet, or modelid falls outside
    every one of its verified modelid_ranges -- callers MUST treat None as "unresolved", never
    fall back to guessing (e.g. the old 98239+modelid formula), per project rule (never invent/
    estimate an id)."""
    entry = FAMILY_MODEL_TABLES.get(familyid)
    if not entry:
        return None
    if not any(lo <= modelid <= hi for lo, hi in entry["modelid_ranges"]):
        return None
    return modelid + entry["file_id_base"]


def resolve_family_dat_path(familyid: int, modelid: int) -> str | None:
    """Same as resolve_family_file_id but returns the ROM-relative path string directly (e.g.
    "ROM\\7\\78.DAT"), for families where dat_base/rom_dir are known (i.e. every verified block
    lives under one ROM subdir) -- informational/debug use; resolve_rom_path() via dat-extractor
    is still the authoritative resolver, and is required for a multi-rom_dir family like Goblin."""
    entry = FAMILY_MODEL_TABLES.get(familyid)
    if not entry or entry.get("dat_base") is None or entry.get("rom_dir") is None:
        return None
    if not any(lo <= modelid <= hi for lo, hi in entry["modelid_ranges"]):
        return None
    n = modelid - entry["dat_base"]
    return f"{entry['rom_dir']}\\{n}.DAT"
