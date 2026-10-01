"""Read-only client model-id resolution for Client Shared."""
from __future__ import annotations

import subprocess

from workbench.runtime import legacy_settings as settings
from workbench.runtime.paths import VENDOR_ROOT


DAT_EXTRACTOR_DLL = VENDOR_ROOT / "dat-extractor/bin/Debug/net9.0/dat-extractor.dll"

MODEL_RULES = (
    (1500, 1300, "<1500 +1300"),
    (3000, 50295, "1500-2999 +50295"),
    (3500, 96907, "3000-3499 +96907"),
    (None, 98239, "3500+ +98239"),
)


def model_id_to_file_id(model_id: int) -> tuple[int, str]:
    """Map a server look_t model id to the FFXiMain client file-id namespace."""
    mid = int(model_id)
    if mid < 0 or mid > 0xFFFF:
        raise ValueError("model_id must fit the server look_t u16 range (0..65535)")
    for upper, offset, label in MODEL_RULES:
        if upper is None or mid < upper:
            return mid + offset, label
    raise AssertionError("unreachable")


def _resolve_rom_path(ffxi_path: str, file_id: int) -> str | None:
    result = subprocess.run(
        ["dotnet", "exec", str(DAT_EXTRACTOR_DLL), "--resolve", ffxi_path, str(int(file_id))],
        capture_output=True,
        text=True,
    )
    for line in result.stdout.splitlines():
        parts = line.split("\t")
        if len(parts) >= 2 and parts[0].isdigit() and int(parts[0]) == int(file_id):
            return None if parts[1] == "(not found)" else parts[1]
    return None


def resolve_model_id(model_id: int, ffxi_path: str | None = None) -> dict:
    """Resolve one server look_t model id to an actual client DAT with provenance."""
    mid = int(model_id)
    file_id, rule = model_id_to_file_id(mid)
    install = ffxi_path or settings.get_ffxi_install()
    result = {
        "model_id": mid,
        "file_id": file_id,
        "mapping_rule": rule,
        "mapping_source": "FFXiMain monster lookup VA 0x100C513D (piecewise; vekien/xi-tools decompilation)",
        "ffxi_path": install,
        "rom_path": None,
        "registered": False,
    }
    if not install:
        result["error"] = "no FFXI client install path configured -- set one on the Settings page"
        return result
    rom_path = _resolve_rom_path(install, file_id)
    if not rom_path:
        result["error"] = f"client FTABLE/VTABLE has no registered DAT for file_id {file_id}"
        return result
    result["rom_path"] = rom_path
    result["registered"] = True
    return result
