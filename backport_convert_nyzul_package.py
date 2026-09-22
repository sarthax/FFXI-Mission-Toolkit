"""
One-off driver applying backport_lua_convert across the Nyzul Isle Investigation package,
writing DSP-ready output into mission-packages/nyzul_isle_investigation/lua-dsp/ (mirrors the
Topaz source tree under lua/, same relative paths).

Per-zone settings come from data/dsp_namespace_map.json's per_zone_id_file_conventions, checked
against real DSP source during this backport (see NAMESPACE_TRANSLATION.md in the package for the
full evidence trail). Files needing hand judgment (not blind conversion) are listed in
SKIP_GENERIC_CONVERSION and handled separately, documented in DSP_PORT_NOTES.md written alongside
the output.
"""
from pathlib import Path
import backport_lua_convert as blc
import settings

_backport_root = settings.get_backport_root()
if _backport_root is None:
    raise SystemExit("No backport checkout configured -- set Settings' backport_root first.")
PKG_ROOT = _backport_root / "mission-packages" / "nyzul_isle_investigation"
SRC_ROOT = PKG_ROOT / "lua"
OUT_ROOT = PKG_ROOT / "lua-dsp"

# Files that need hand judgment, not the generic converter -- see DSP_PORT_NOTES.md for why each
# one is here instead of being run through convert() like everything else.
SKIP_GENERIC_CONVERSION = {
    "scripts/zones/Nyzul_Isle/IDs.lua",
    "scripts/zones/Aht_Urhgan_Whitegate/IDs.lua",
    "scripts/zones/Alzadaal_Undersea_Ruins/IDs.lua",
    "scripts/zones/Alzadaal_Undersea_Ruins/npcs/_20m.lua",
    # Dropped from this package's conversion scope entirely -- DSP already has complete,
    # independently-evolved versions and nothing Nyzul-specific calls into what Topaz's own
    # versions add (see NAMESPACE_TRANSLATION.md's "region/nation/zoneType" section).
    "scripts/globals/zone.lua",
    "scripts/globals/missions.lua",
    "scripts/globals/teleports.lua",
    "scripts/globals/besieged.lua",
    "scripts/globals/keyitems.lua",
    "scripts/globals/instance.lua",
}

# Files whose real damage-application call needs the MobFinalAdjustments/delHP rewrite documented
# in NAMESPACE_TRANSLATION.md -- the converter correctly flags these (tpz.attackType/damageType,
# takeDamage), but the fix is a real rewrite, not a mechanical substitution the tool should attempt.
NEEDS_DAMAGE_REWRITE = {
    "scripts/globals/mobskills/fulmination.lua",
    "scripts/globals/mobskills/gates_of_hades.lua",
}


ZONE_SETTINGS_BY_PREFIX = {
    "scripts/zones/Nyzul_Isle/": {"zone_table": "NyzulIsle", "id_shape": "nested", "id_file_hint": "IDs"},
    "scripts/zones/Aht_Urhgan_Whitegate/": {"zone_table": None, "id_shape": "flat", "id_file_hint": "TextIDs"},
    "scripts/zones/Alzadaal_Undersea_Ruins/": {"zone_table": None, "id_shape": "flat", "id_file_hint": "TextIDs"},
}
# Maps each zone's require() path (as it appears in Topaz source) to the same settings above --
# needed for files OUTSIDE that zone's own folder that still pull its IDs.lua, e.g. GM commands
# like nyzuldebug.lua doing `local ID = require("scripts/zones/Nyzul_Isle/IDs")`.
ZONE_REQUIRE_TO_SETTINGS = {
    "scripts/zones/Nyzul_Isle/IDs": ZONE_SETTINGS_BY_PREFIX["scripts/zones/Nyzul_Isle/"],
    "scripts/zones/Aht_Urhgan_Whitegate/IDs": ZONE_SETTINGS_BY_PREFIX["scripts/zones/Aht_Urhgan_Whitegate/"],
    "scripts/zones/Alzadaal_Undersea_Ruins/IDs": ZONE_SETTINGS_BY_PREFIX["scripts/zones/Alzadaal_Undersea_Ruins/"],
}


def zone_settings_for(rel_path: str, text: str | None = None) -> dict:
    """Returns {zone_table, id_shape, id_file_hint} for a given package-relative path, per
    per_zone_id_file_conventions. Checked first by the file's own folder; if that doesn't match
    (a GM command or other cross-zone script) and `text` is given, falls back to sniffing its own
    `local ID = require(...)` line so a command referencing e.g. Nyzul_Isle's IDs.lua still gets
    the right zone_table instead of silently being treated as zone-agnostic."""
    for prefix, settings in ZONE_SETTINGS_BY_PREFIX.items():
        if rel_path.startswith(prefix):
            return settings
    if text:
        m = blc.ID_REQUIRE_RE.search(text)
        if m and m.group(1) in ZONE_REQUIRE_TO_SETTINGS:
            return ZONE_REQUIRE_TO_SETTINGS[m.group(1)]
    return {"zone_table": None, "id_shape": None, "id_file_hint": None}


def main():
    ns_map = blc.load_map()
    report = {"converted": [], "skipped": [], "flagged": []}

    for src in SRC_ROOT.rglob("*.lua"):
        rel = src.relative_to(SRC_ROOT).as_posix()
        dst = OUT_ROOT / rel
        dst.parent.mkdir(parents=True, exist_ok=True)

        if rel in SKIP_GENERIC_CONVERSION:
            report["skipped"].append(rel)
            continue

        text = src.read_text(encoding="utf-8", errors="replace")
        settings = zone_settings_for(rel, text)
        result = blc.convert(text, ns_map=ns_map, **settings)
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


if __name__ == "__main__":
    main()
