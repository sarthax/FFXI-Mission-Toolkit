"""
Driver applying backport_lua_convert across the 7 new Assault mission packages (Leujaoam Sanctum,
Mamool Ja Training Grounds, Lebros Cavern, Periqia, Ilrusi Atoll, Mercenary Rank Promotions, Assault
Lockbox Appraisal), writing DSP-ready output into each package's own lua-dsp/ sibling tree.

Pattern-matched off backport_convert_nyzul_package.py. The key difference from that package: all
zones touched here use the newly-confirmed shape_C id-file convention (per_zone_id_file_conventions
.shape_C_zones_table_global in data/dsp_namespace_map.json) -- `local ID = zones[xi.zone.X]`, no
require(), ID.text/mob/npc call sites unchanged. See reports/dsp_id_shape_findings_2026-09-13.md for
the full evidence trail.
"""
from pathlib import Path
import backport_lua_convert as blc

PKG_ROOT_BASE = Path(r"D:\Claude\Topaz-Assault-Backport\mission-packages")

PACKAGES = [
    "leujaoam_sanctum_missions_1-4",
    "mamool_ja_training_grounds_missions_1-4",
    "lebros_cavern_missions_1-4",
    "periqia_missions_1-4",
    "ilrusi_atoll_missions_1-4",
    "mercenary_rank_promotions",
    "assault_lockbox_appraisal",
]

# Zone folder name -> its real xi.zone.* enum (confirmed 2026-09-13 by reading each zone's real
# DSP IDs.lua header directly -- `zones[xi.zone.<THIS>]`).
ZONE_ENUM_BY_FOLDER = {
    "Leujaoam_Sanctum": "LEUJAOAM_SANCTUM",
    "Mamool_Ja_Training_Grounds": "MAMOOL_JA_TRAINING_GROUNDS",
    "Lebros_Cavern": "LEBROS_CAVERN",
    "Periqia": "PERIQIA",
    "Ilrusi_Atoll": "ILRUSI_ATOLL",
    "Aht_Urhgan_Whitegate": "AHT_URHGAN_WHITEGATE",
    "Bhaflau_Thickets": "BHAFLAU_THICKETS",
    "Caedarva_Mire": "CAEDARVA_MIRE",
    "Mount_Zhayolm": "MOUNT_ZHAYOLM",
    "Wajaom_Woodlands": "WAJAOM_WOODLANDS",
    "Al_Zahbi": "AL_ZAHBI",
    "Nashmau": "NASHMAU",
}

# Globals files DSP already ships a complete, independently-evolved version of (or has explicitly
# dropped from Assault scope) -- same precedent as the Nyzul package's SKIP_GENERIC_CONVERSION for
# globals/zone.lua, missions.lua, teleports.lua, besieged.lua, keyitems.lua, instance.lua. Only
# besieged/keyitems/missions actually recur in these 7 packages' own globals/ folders.
SKIP_GENERIC_CONVERSION_BASENAMES = {
    "scripts/globals/besieged.lua",
    "scripts/globals/keyitems.lua",
    "scripts/globals/missions.lua",
}


def zone_settings_for(rel_path: str) -> dict:
    for folder, enum in ZONE_ENUM_BY_FOLDER.items():
        if rel_path.startswith(f"scripts/zones/{folder}/"):
            return {"zone_table": enum, "id_shape": "zones_table", "id_file_hint": None}
    return {"zone_table": None, "id_shape": None, "id_file_hint": None}


def convert_package(pkg_name: str, ns_map: dict) -> dict:
    pkg_root = PKG_ROOT_BASE / pkg_name
    src_root = pkg_root / "lua"
    out_root = pkg_root / "lua-dsp"
    report = {"package": pkg_name, "converted": [], "skipped": [], "flagged": []}

    if not src_root.exists():
        report["error"] = f"no lua/ tree at {src_root}"
        return report

    for src in src_root.rglob("*.lua"):
        rel = src.relative_to(src_root).as_posix()
        dst = out_root / rel
        dst.parent.mkdir(parents=True, exist_ok=True)

        if rel in SKIP_GENERIC_CONVERSION_BASENAMES:
            report["skipped"].append(rel)
            continue

        text = src.read_text(encoding="utf-8", errors="replace")
        settings = zone_settings_for(rel)
        result = blc.convert(text, ns_map=ns_map, **settings)
        dst.write_text(result.converted, encoding="utf-8")
        report["converted"].append(rel)
        if result.flagged:
            report["flagged"].append((rel, len(result.flagged)))

    return report


DSP_ROOT = Path(r"D:\Claude\old-dsp-reference")


def main():
    blc.verify_target_or_raise(DSP_ROOT, "old_dsp_reference")
    ns_map = blc.load_map()
    all_reports = [convert_package(p, ns_map) for p in PACKAGES]

    for r in all_reports:
        print(f"\n=== {r['package']} ===")
        if "error" in r:
            print(f"  ERROR: {r['error']}")
            continue
        print(f"Converted: {len(r['converted'])}")
        print(f"Skipped (already-present-in-DSP globals): {len(r['skipped'])}")
        for rel in r["skipped"]:
            print(f"  SKIP  {rel}")
        print(f"Files with flagged lines: {len(r['flagged'])}")
        for rel, count in r["flagged"]:
            print(f"  FLAG  {rel}: {count} line(s)")

    return all_reports


if __name__ == "__main__":
    main()
