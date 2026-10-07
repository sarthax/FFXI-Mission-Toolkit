"""Convert the seven Assault-era package trees to legacy DSP Lua."""
from __future__ import annotations

from pathlib import Path

from workbench.packages.migration import lua_convert as blc

PKG_ROOT_BASE: Path | None = None
DSP_ROOT: Path | None = None


def _default_package_root_base() -> Path | None:
    from workbench.runtime import legacy_settings

    backport_root = legacy_settings.get_backport_root()
    return (backport_root / "mission-packages") if backport_root is not None else None


def _default_dsp_root() -> Path | None:
    from workbench.runtime import legacy_settings

    return legacy_settings.get_dsp_root()

PACKAGES = [
    "leujaoam_sanctum_missions_1-4",
    "mamool_ja_training_grounds_missions_1-4",
    "lebros_cavern_missions_1-4",
    "periqia_missions_1-4",
    "ilrusi_atoll_missions_1-4",
    "mercenary_rank_promotions",
    "assault_lockbox_appraisal",
]

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


def convert_package(pkg_name: str, ns_map: dict, package_root_base: Path | None = None) -> dict:
    root_base = package_root_base or PKG_ROOT_BASE
    if root_base is None:
        raise RuntimeError("No backport package root configured.")
    pkg_root = root_base / pkg_name
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
        result = blc.convert(text, ns_map=ns_map, **zone_settings_for(rel))
        dst.write_text(result.converted, encoding="utf-8")
        report["converted"].append(rel)
        if result.flagged:
            report["flagged"].append((rel, len(result.flagged)))
    return report


def main(package_root_base: Path | None = None, dsp_root: Path | None = None):
    root_base = package_root_base or PKG_ROOT_BASE or _default_package_root_base()
    target = dsp_root or DSP_ROOT or _default_dsp_root()
    if root_base is None:
        raise SystemExit("No backport checkout configured -- set Settings' backport_root first.")
    if target is None:
        raise SystemExit("No DSP checkout configured -- set Settings' dsp_server_path first.")
    blc.verify_target_or_raise(target, "old_dsp_reference")
    ns_map = blc.load_map()
    all_reports = [convert_package(p, ns_map, root_base) for p in PACKAGES]
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
