"""Convert the Assault GM debug-tools package to legacy DSP Lua."""
from __future__ import annotations
from pathlib import Path
from workbench.packages.migration import lua_convert as blc

PKG_ROOT: Path | None = None
DSP_ROOT: Path | None = None


def _default_pkg_root() -> Path | None:
    from workbench.runtime import legacy_settings

    backport_root = legacy_settings.get_backport_root()
    return (
        backport_root / "mission-packages" / "assault_gm_debug_tools"
        if backport_root is not None
        else None
    )


def _default_dsp_root() -> Path | None:
    from workbench.runtime import legacy_settings

    return legacy_settings.get_dsp_root()


def main(pkg_root: Path | None = None, dsp_root: Path | None = None):
    package = pkg_root or PKG_ROOT or _default_pkg_root()
    target = dsp_root or DSP_ROOT or _default_dsp_root()
    if package is None:
        raise SystemExit("No backport checkout configured -- set Settings' backport_root first.")
    if target is None:
        raise SystemExit("No DSP checkout configured -- set Settings' dsp_server_path first.")
    blc.verify_target_or_raise(target, "old_dsp_reference")
    ns_map = blc.load_map()
    src_root = package / "lua"
    out_root = package / "lua-dsp"
    report = {"converted": [], "flagged": []}
    for src in src_root.rglob("*.lua"):
        rel = src.relative_to(src_root).as_posix()
        dst = out_root / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        result = blc.convert(src.read_text(encoding="utf-8", errors="replace"), ns_map=ns_map)
        dst.write_text(result.converted, encoding="utf-8")
        report["converted"].append(rel)
        if result.flagged:
            report["flagged"].append((rel, len(result.flagged)))
    print(f"Converted: {len(report['converted'])}")
    print(f"Files with flagged lines: {len(report['flagged'])}")
    for rel, count in report["flagged"]:
        print(f"  FLAG  {rel}: {count} line(s)")
    return report

if __name__ == "__main__":
    main()
