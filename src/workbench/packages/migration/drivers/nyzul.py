"""Convert the Nyzul Isle Investigation package to legacy DSP Lua."""
from __future__ import annotations
from pathlib import Path
from workbench.packages.migration import lua_convert as blc

PKG_ROOT: Path | None = None


def _default_pkg_root() -> Path | None:
    from workbench.runtime import legacy_settings

    backport_root = legacy_settings.get_backport_root()
    return (
        backport_root / "mission-packages" / "nyzul_isle_investigation"
        if backport_root is not None
        else None
    )

SKIP_GENERIC_CONVERSION = {
    "scripts/zones/Nyzul_Isle/IDs.lua",
    "scripts/zones/Aht_Urhgan_Whitegate/IDs.lua",
    "scripts/zones/Alzadaal_Undersea_Ruins/IDs.lua",
    "scripts/zones/Alzadaal_Undersea_Ruins/npcs/_20m.lua",
    "scripts/globals/zone.lua",
    "scripts/globals/missions.lua",
    "scripts/globals/teleports.lua",
    "scripts/globals/besieged.lua",
    "scripts/globals/keyitems.lua",
    "scripts/globals/instance.lua",
}

NEEDS_DAMAGE_REWRITE = {
    "scripts/globals/mobskills/fulmination.lua",
    "scripts/globals/mobskills/gates_of_hades.lua",
}

ZONE_SETTINGS_BY_PREFIX = {
    "scripts/zones/Nyzul_Isle/": {"zone_table": "NyzulIsle", "id_shape": "nested", "id_file_hint": "IDs"},
    "scripts/zones/Aht_Urhgan_Whitegate/": {"zone_table": None, "id_shape": "flat", "id_file_hint": "TextIDs"},
    "scripts/zones/Alzadaal_Undersea_Ruins/": {"zone_table": None, "id_shape": "flat", "id_file_hint": "TextIDs"},
}
ZONE_REQUIRE_TO_SETTINGS = {
    "scripts/zones/Nyzul_Isle/IDs": ZONE_SETTINGS_BY_PREFIX["scripts/zones/Nyzul_Isle/"],
    "scripts/zones/Aht_Urhgan_Whitegate/IDs": ZONE_SETTINGS_BY_PREFIX["scripts/zones/Aht_Urhgan_Whitegate/"],
    "scripts/zones/Alzadaal_Undersea_Ruins/IDs": ZONE_SETTINGS_BY_PREFIX["scripts/zones/Alzadaal_Undersea_Ruins/"],
}


def zone_settings_for(rel_path: str, text: str | None = None) -> dict:
    for prefix, settings in ZONE_SETTINGS_BY_PREFIX.items():
        if rel_path.startswith(prefix):
            return settings
    if text:
        match = blc.ID_REQUIRE_RE.search(text)
        if match and match.group(1) in ZONE_REQUIRE_TO_SETTINGS:
            return ZONE_REQUIRE_TO_SETTINGS[match.group(1)]
    return {"zone_table": None, "id_shape": None, "id_file_hint": None}


def main(pkg_root: Path | None = None):
    package = pkg_root or PKG_ROOT or _default_pkg_root()
    if package is None:
        raise SystemExit("No backport checkout configured -- set Settings' backport_root first.")
    src_root = package / "lua"
    out_root = package / "lua-dsp"
    ns_map = blc.load_map()
    report = {"converted": [], "skipped": [], "flagged": []}
    for src in src_root.rglob("*.lua"):
        rel = src.relative_to(src_root).as_posix()
        dst = out_root / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        if rel in SKIP_GENERIC_CONVERSION:
            report["skipped"].append(rel)
            continue
        text = src.read_text(encoding="utf-8", errors="replace")
        result = blc.convert(text, ns_map=ns_map, **zone_settings_for(rel, text))
        dst.write_text(result.converted, encoding="utf-8")
        report["converted"].append(rel)
        if result.flagged:
            report["flagged"].append((rel, len(result.flagged), rel in NEEDS_DAMAGE_REWRITE))
    print(f"Converted: {len(report['converted'])}")
    print(f"Skipped (hand judgment needed): {len(report['skipped'])}")
    for rel in report["skipped"]:
        print(f"  SKIP  {rel}")
    print(f"Files with flagged lines: {len(report['flagged'])}")
    for rel, count, expected in report["flagged"]:
        tag = "(expected -- damage rewrite)" if expected else "(UNEXPECTED -- check)"
        print(f"  FLAG  {rel}: {count} line(s) {tag}")
    return report

if __name__ == "__main__":
    main()
