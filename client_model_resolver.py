"""Client model-id resolution used by the lightweight Model Viewer.

This deliberately separates three namespaces that were previously conflated:
- server look_t modelid (u16 stored in mob_pools.modelid / npc_list.look)
- client file_id (FTABLE/VTABLE key)
- physical ROM DAT path

The server modelid -> client file_id transform follows FFXiMain's monster lookup at VA
0x100C513D as documented by vekien/xi-tools. xi-model-viewer's older zone-NPC generator carries
stale 3193/+98546 tail values; those are intentionally not copied here.
It is piecewise, not one universal additive offset:

    modelid < 1500 -> file_id = modelid + 1300
    modelid < 3000 -> file_id = modelid + 50295
    modelid < 3500 -> file_id = modelid + 96907
    otherwise      -> file_id = modelid + 98239

The resulting file_id is still resolved through the configured client's FTABLE/VTABLE via the
existing dat-extractor-backed resolver. A mapping is not considered usable unless that resolver
returns a real DAT path.
"""

import settings
import model_schedule_dump as msd


MODEL_RULES = (
    (1500, 1300, "<1500 +1300"),
    (3000, 50295, "1500-2999 +50295"),
    (3500, 96907, "3000-3499 +96907"),
    (None, 98239, "3500+ +98239"),
)


def model_id_to_file_id(model_id: int) -> tuple[int, str]:
    mid = int(model_id)
    if mid < 0 or mid > 0xFFFF:
        raise ValueError("model_id must fit the server look_t u16 range (0..65535)")
    for upper, offset, label in MODEL_RULES:
        if upper is None or mid < upper:
            return mid + offset, label
    raise AssertionError("unreachable")


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
    rom_path = msd.resolve_rom_path(install, file_id)
    if not rom_path:
        result["error"] = f"client FTABLE/VTABLE has no registered DAT for file_id {file_id}"
        return result
    result["rom_path"] = rom_path
    result["registered"] = True
    return result
