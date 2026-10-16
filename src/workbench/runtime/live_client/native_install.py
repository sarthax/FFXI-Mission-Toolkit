"""Local installer for the native Ashita plugin DLL and its opt-in settings.ini.

Copies a prebuilt workbench_native_probe.dll into <Ashita>/plugins (backing up any
existing one) and creates config/workbench_native/settings.ini only when absent.
Never loads the plugin, never touches the game process, never enables anything
beyond what the caller explicitly selects.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import time
import urllib.request
from pathlib import Path

DLL_NAME = "workbench_native_probe.dll"
REPO = Path(__file__).resolve().parents[4]
CACHE = REPO / "dist" / "native" / "download"
CANDIDATES = (
    REPO / "dist" / "native" / DLL_NAME,
    REPO / "build" / "ashita-native-probe" / "Release" / DLL_NAME,
    CACHE / DLL_NAME,
)


# Pinned release manifest: the hash comes from git, not from the download, so a swapped
# release asset is rejected. Fill tag/url/sha256 when publishing a new plugin release.
MANIFEST = REPO / "native" / "ashita_workbench_probe" / "release.json"
MAX_BYTES = 8 * 1024 * 1024


def _manifest() -> dict | None:
    try:
        m = json.loads(MANIFEST.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    ok = all(isinstance(m.get(k), str) and m[k] for k in ("tag", "url", "sha256"))
    return m if ok and m["url"].startswith("https://github.com/sarthax/FFXI-Mission-Toolkit/releases/download/") else None


def download_release() -> Path:
    """Fetch the pinned GitHub release DLL into the cache; verify the pinned SHA-256 before use."""
    m = _manifest()
    if m is None:
        raise ValueError("No published plugin release is pinned (native/ashita_workbench_probe/release.json)")
    CACHE.mkdir(parents=True, exist_ok=True)
    target = CACHE / DLL_NAME
    if target.is_file() and _sha(target) == m["sha256"].lower():
        return target
    req = urllib.request.Request(m["url"], headers={"User-Agent": "workbench-native-install"})
    with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310 (https URL pinned above)
        data = resp.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES or hashlib.sha256(data).hexdigest() != m["sha256"].lower():
        raise ValueError("Downloaded plugin failed SHA-256 verification; not installed")
    tmp = target.with_suffix(".part")
    tmp.write_bytes(data)
    os.replace(tmp, target)
    return target


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def find_dll() -> Path | None:
    override = os.environ.get("WORKBENCH_NATIVE_DLL")
    for c in ((Path(override),) if override else ()) + CANDIDATES:
        if c.is_file() and not c.is_symlink():
            return c
    return None


def _dirs(ashita_root: str) -> tuple[Path, Path]:
    root = Path(ashita_root).expanduser()
    if not root.is_absolute() or not root.is_dir() or root.is_symlink():
        raise ValueError("Select an existing absolute Ashita installation folder")
    plugins = root / "plugins"
    if not plugins.is_dir() or plugins.is_symlink():
        raise ValueError("Selected folder must contain a real plugins directory")
    return plugins, root / "config" / "workbench_native"


def render_settings(allow_file_commands: bool, auto_arm: str = "", speed_percent: int | None = None,
                    allow_chat_commands: bool = False) -> str:
    if auto_arm not in ("", "warp", "autorun", "local"):
        raise ValueError("auto_arm must be empty, warp, autorun or local")
    if speed_percent is not None and not 25 <= int(speed_percent) <= 400:
        raise ValueError("speed_percent must be 25..400")
    lines = [
        "; Workbench native plugin settings (private dev-server use only). Re-read every 2 s.",
        "; REQUIRED: a stock Ashita/server install has no settings.ini. Without the line below the plugin ignores",
        "; every Toolkit command (warp, speed, ...). Set to 1 to let the Toolkit move your character.",
        f"allow_file_commands={1 if allow_file_commands else 0}",
        "; OPTIONAL, off by default: set to 1 to let the GM Command Center type '!' GM commands into your game",
        "; chat (needs a character with GM permission). Independent of allow_file_commands; dev servers only.",
        f"allow_chat_commands={1 if allow_chat_commands else 0}",
        f"auto_arm={auto_arm}",
        "enable_ttl_seconds=0" if auto_arm else "; enable_ttl_seconds=120",
        f"speed_percent={int(speed_percent)}" if speed_percent else "; speed_percent=120",
        "; base_speed=5.0",
    ]
    return "\n".join(lines) + "\n"


def preview(ashita_root: str) -> dict:
    plugins, cfg = _dirs(ashita_root)
    src = find_dll()
    target = plugins / DLL_NAME
    settings = cfg / "settings.ini"
    return {
        "dll_found": src is not None or _manifest() is not None,
        "dll_source": str(src) if src else (("GitHub release " + _manifest()["tag"]) if _manifest() else None),
        "dll_sha256": _sha(src) if src else (_manifest() or {}).get("sha256"),
        "target": str(target),
        "target_exists": target.exists(),
        "target_matches": bool(target.is_file() and (src or _manifest()) and _sha(target) == (_sha(src) if src else _manifest()["sha256"].lower())),
        "settings_path": str(settings),
        "settings_exists": settings.exists(),
        "release_available": _manifest() is not None,
        "note": None if src else ("No local DLL: Install will download the pinned release." if _manifest() else "No DLL available: build it (native/ashita_workbench_probe/README.md) or publish and pin a release."),
    }


def apply(ashita_root: str, expected_sha256: str, allow_file_commands: bool = False,
          auto_arm: str = "", speed_percent: int | None = None, allow_chat_commands: bool = False) -> dict:
    plugins, cfg = _dirs(ashita_root)
    src = find_dll()
    pinned = (_manifest() or {}).get("sha256", "").lower()
    if src is None or _sha(src) != expected_sha256:
        if pinned and expected_sha256 == pinned:
            src = download_release()
        else:
            raise ValueError("DLL changed since preview; preview again")
    sha = _sha(src)
    target = plugins / DLL_NAME
    if target.is_symlink():
        raise ValueError("Refusing to write through a symlinked plugin file")
    result = {"dll_copied": False, "backup": None, "settings_written": False, "dll_sha256": sha}
    if not (target.is_file() and _sha(target) == sha):
        try:
            if target.exists():
                backup = target.with_name(f"{DLL_NAME}.bak-{time.strftime('%Y%m%d-%H%M%S')}")
                shutil.copy2(target, backup)
                result["backup"] = str(backup)
            tmp = target.with_suffix(".dll.tmp")
            shutil.copy2(src, tmp)
            os.replace(tmp, target)
        except PermissionError as exc:
            raise ValueError("DLL is in use: run /unload workbench_native_probe in game, then retry") from exc
        result["dll_copied"] = True
    settings = cfg / "settings.ini"
    if not settings.exists():
        cfg.mkdir(parents=True, exist_ok=True)
        settings.write_text(render_settings(allow_file_commands, auto_arm, speed_percent, allow_chat_commands), encoding="utf-8", newline="\n")
        result["settings_written"] = True
    result["load_command"] = "/load workbench_native_probe"
    return result
