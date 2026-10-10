"""Local opt-in Ashita addon installer; no game process access or credentials.

Only creates previously absent files. Never replaces existing addon or settings.
"""
from __future__ import annotations

import hashlib
import os
import secrets
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


def preview_upgrade(ashita_root: str) -> dict:
    """Nonmutating preview with the exact current and expected contents hashed."""
    state = preview(ashita_root)
    addon = _paths(ashita_root)
    files = []
    for row in state["files"]:
        target = addon / row["name"]
        current = hashlib.sha256(target.read_bytes()).hexdigest() if target.exists() else None
        files.append({**row, "current_sha256": current,
                      "action": "replace_with_backup" if row["action"] == "blocked_existing" else row["action"]})
    return {**state, "files": files, "can_install": True, "mode": "backup_upgrade"}


def upgrade_with_backup(ashita_root: str, expected: dict) -> dict:
    """Opt-in backup-first update, with no writes if the preview became stale."""
    state = preview_upgrade(ashita_root)
    if expected != state:
        raise ValueError("Upgrade preview changed; preview again")
    addon = _paths(ashita_root)
    if not addon.exists():
        addon.mkdir()
    changed = [row for row in state["files"] if row["action"] != "unchanged"]
    # Check sources and targets before making a single backup or touching addon files.
    for row in changed:
        target = addon / row["name"]
        if target.is_symlink() or (target.exists() and not target.is_file()):
            raise ValueError("Unsafe existing addon file")
        previous = hashlib.sha256(target.read_bytes()).hexdigest() if target.exists() else None
        if previous != row["current_sha256"]:
            raise ValueError("Addon changed since preview")
        source = (SOURCE / MANIFEST[row["name"]]).read_bytes()
        if hashlib.sha256(source).hexdigest() != row["sha256"]:
            raise ValueError("Toolkit source changed since preview")
    replaced = [row for row in changed if row["action"] == "replace_with_backup"]
    backup = None
    if replaced:
        # Sibling backup remains outside the addon loading directory.
        for _ in range(4):
            candidate = addon.parent / ("workbench_live_backup_" + secrets.token_hex(8))
            try:
                candidate.mkdir()
                backup = candidate
                break
            except FileExistsError:
                continue
        if backup is None:
            raise ValueError("Could not reserve a unique backup directory")
        for row in replaced:
            original = addon / row["name"]
            with (backup / row["name"]).open("xb") as handle:
                handle.write(original.read_bytes())
            if hashlib.sha256((backup / row["name"]).read_bytes()).hexdigest() != row["current_sha256"]:
                raise ValueError("Backup verification failed; originals unchanged")
    updated = []
    try:
        for row in changed:
            destination = addon / row["name"]
            # Recheck each target before writing, never follow a new symlink.
            if destination.is_symlink() or (destination.exists() and
                hashlib.sha256(destination.read_bytes()).hexdigest() != row["current_sha256"]):
                raise ValueError("Addon changed during upgrade")
            content = (SOURCE / MANIFEST[row["name"]]).read_bytes()
            if hashlib.sha256(content).hexdigest() != row["sha256"]:
                raise ValueError("Toolkit source changed during upgrade")
            if row["action"] == "create":
                with destination.open("xb") as handle:
                    handle.write(content)
            else:
                temporary = addon / (row["name"] + "." + secrets.token_hex(8) + ".tmp")
                try:
                    with temporary.open("xb") as handle:
                        handle.write(content)
                    os.replace(temporary, destination)
                finally:
                    temporary.unlink(missing_ok=True)
            updated.append(row["name"])
    except Exception:
        # Backups remain intact for manual recovery on partial filesystem failure.
        raise
    return {"target": str(addon), "updated": updated, "backup_directory": str(backup) if backup else None,
            "settings_file_untouched": True}
