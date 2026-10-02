#!/usr/bin/env python3
"""Install the xi_tinkerer wheel used by Mission Toolkit bootstrap.

This module intentionally uses only the Python standard library so it can run before the
project's requirements or editable package have been installed.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

REPO = "sruon/xi-tinkerer-py"
API_URL = f"https://api.github.com/repos/{REPO}/releases"


def already_installed() -> bool:
    try:
        import xi_tinkerer  # noqa: F401
        return True
    except ImportError:
        return False


def pick_asset(assets: list[dict]) -> dict | None:
    """Prefer this Python's Windows wheel, then any compatible win_amd64 abi3 wheel."""
    py_tag = f"cp{sys.version_info.major}{sys.version_info.minor}"
    candidates = [
        asset for asset in assets
        if asset["name"].endswith(".whl") and "win_amd64" in asset["name"]
    ]
    if not candidates:
        return None

    for asset in candidates:
        if py_tag in asset["name"]:
            return asset
    for asset in candidates:
        if "abi3" in asset["name"]:
            return asset
    return candidates[0]


def main() -> int:
    if already_installed():
        print("xi_tinkerer already installed, nothing to do.")
        return 0

    print(f"Downloading xi_tinkerer from {REPO}'s latest GitHub release...")
    try:
        req = urllib.request.Request(API_URL, headers={"User-Agent": "mission-toolkit-setup"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            releases = json.loads(resp.read().decode("utf-8"))
    except Exception as exc:
        print(f"[ERROR] Could not reach GitHub to check releases: {exc}")
        print(f"Download it yourself from: https://github.com/{REPO}/releases")
        return 1

    if not releases:
        print(f"[ERROR] No releases found for {REPO}.")
        return 1

    release = releases[0]
    asset = pick_asset(release.get("assets", []))
    if not asset:
        print("[ERROR] No matching Windows wheel found in the latest release.")
        print(f"Check manually: https://github.com/{REPO}/releases")
        return 1

    print(f"Found: {asset['name']} ({release.get('tag_name', '?')})")
    with tempfile.TemporaryDirectory() as tmp:
        whl_path = Path(tmp) / asset["name"]
        try:
            urllib.request.urlretrieve(asset["browser_download_url"], whl_path)
        except Exception as exc:
            print(f"[ERROR] Download failed: {exc}")
            return 1

        print("Installing...")
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "--quiet", str(whl_path)]
        )
        if result.returncode != 0:
            print("[ERROR] pip install failed -- see output above.")
            return 1

    if already_installed():
        print("xi_tinkerer installed successfully.")
        return 0

    print("[ERROR] Install command succeeded but xi_tinkerer still can't be imported.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
