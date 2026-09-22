"""
One-off driver applying backport_lua_convert across assault_gm_debug_tools, writing DSP-ready
output into mission-packages/assault_gm_debug_tools/lua-dsp/ (mirrors the Topaz source tree under
lua/, same relative paths). Pattern-matched off backport_convert_nyzul_package.py /
backport_convert_7_packages.py.

These are pure GM command scripts (no zone IDs.lua involved), so no zone_table/id_shape settings
are needed -- convert() with defaults handles the new command-shape wrapping
(_convert_command_shape) plus the printToPlayer/gotoEntity/setUntargetable method renames and the
tpz.anim->xi.anim reshape, all added to dsp_namespace_map.json for this package's audit.
"""
from pathlib import Path
import backport_lua_convert as blc
import settings

_backport_root = settings.get_backport_root()
if _backport_root is None:
    raise SystemExit("No backport checkout configured -- set Settings' backport_root first.")
PKG_ROOT = _backport_root / "mission-packages" / "assault_gm_debug_tools"
SRC_ROOT = PKG_ROOT / "lua"
OUT_ROOT = PKG_ROOT / "lua-dsp"


DSP_ROOT = settings.get_dsp_root()


def main():
    if DSP_ROOT is None:
        raise SystemExit("No DSP checkout configured -- set Settings' dsp_server_path first.")
    blc.verify_target_or_raise(DSP_ROOT, "old_dsp_reference")
    ns_map = blc.load_map()
    report = {"converted": [], "flagged": []}

    for src in SRC_ROOT.rglob("*.lua"):
        rel = src.relative_to(SRC_ROOT).as_posix()
        dst = OUT_ROOT / rel
        dst.parent.mkdir(parents=True, exist_ok=True)

        text = src.read_text(encoding="utf-8", errors="replace")
        result = blc.convert(text, ns_map=ns_map)
        dst.write_text(result.converted, encoding="utf-8")
        report["converted"].append(rel)
        if result.flagged:
            report["flagged"].append((rel, len(result.flagged)))

    print(f"Converted: {len(report['converted'])}")
    print(f"Files with flagged lines: {len(report['flagged'])}")
    for rel, count in report["flagged"]:
        print(f"  FLAG  {rel}: {count} line(s)")


if __name__ == "__main__":
    main()
