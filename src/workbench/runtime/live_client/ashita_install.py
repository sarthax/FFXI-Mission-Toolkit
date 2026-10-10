"""Local opt-in Ashita addon installer; no game process access or credentials.

Only creates previously absent files. Never replaces existing addon or settings.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[4] / "addons" / "workbench_live"
MANIFEST = {
    "workbench_live.lua": "workbench_live_ashita.lua",
    "workbench_observation.lua": "workbench_observation.lua",
    "workbench_export.lua": "workbench_export.lua",
    "workbench_packets.lua": "workbench_packets.lua",
    "workbench_bridge.lua": "workbench_bridge.lua",
    "workbench_live_direct.lua": "workbench_live_direct.lua",
}


def _paths(ashita_root: str):
    root = Path(ashita_root).expanduser()
    if not root.is_absolute() or not root.is_dir() or root.is_symlink():
        raise ValueError("Select an existing absolute Ashita installation folder")
    addons = root / "addons"
    if not addons.is_dir() or addons.is_symlink():
        raise ValueError("Selected folder must contain a real addons directory")
    addon = addons / "workbench_live"
    if addon.is_symlink() or (addon.exists() and not addon.is_dir()):
        raise ValueError("Unsafe or non-directory workbench_live target")
    return addon


def preview(ashita_root: str) -> dict:
    addon = _paths(ashita_root)
    files = []
    for dest, src in MANIFEST.items():
        target = addon / dest
        if target.is_symlink() or (target.exists() and not target.is_file()):
            raise ValueError("Unsafe existing addon file: " + dest)
        content = (SOURCE / src).read_bytes()
        identical = target.exists() and target.read_bytes() == content
        action = "unchanged" if identical else ("blocked_existing" if target.exists() else "create")
        files.append({"name": dest, "action": action, "sha256": hashlib.sha256(content).hexdigest()})
    return {"target": str(addon), "files": files,
            "can_install": all(f["action"] != "blocked_existing" for f in files),
            "settings_file_untouched": True}


def install_missing(ashita_root: str, expected: dict) -> dict:
    state = preview(ashita_root)
    if expected != state or not state["can_install"]:
        raise ValueError("Installation preview changed or existing files conflict; preview again")
    addon = _paths(ashita_root)
    if not addon.exists():
        addon.mkdir()  # Only the explicitly selected addon's leaf directory.
    written = []
    for file in state["files"]:
        if file["action"] == "unchanged":
            continue
        destination = addon / file["name"]
        content = (SOURCE / MANIFEST[file["name"]]).read_bytes()
        if hashlib.sha256(content).hexdigest() != file["sha256"]:
            raise ValueError("Toolkit addon changed; preview again")
        try:
            with destination.open("xb") as out:
                out.write(content)
        except FileExistsError as exc:
            raise ValueError("File appeared during installation; no overwrite: " + file["name"]) from exc
        written.append(file["name"])
    return {"target": str(addon), "created": written, "settings_file_untouched": True}
