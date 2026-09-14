#!/usr/bin/env python3
"""
install_xi_tinkerer.py -- auto-downloads and installs the real xi_tinkerer wheel from its
GitHub releases (sruon/xi-tinkerer-py), instead of making the user find and download it by hand.

Uses only the Python standard library (urllib, json) so it can run before requirements.txt's
packages are installed -- this has to work on a completely bare Python install.

Exit codes: 0 = installed (or already present), 1 = failed (message explains why).
"""
import json
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

REPO = "sruon/xi-tinkerer-py"
# 2026-09-06: real fix -- this repo's only real release is tagged "latest" but marked as a
# GitHub PRERELEASE, and GitHub's own /releases/latest endpoint deliberately excludes
# prereleases (confirmed live: 404, not a real error) -- there is no non-prerelease release to
# find. Querying the full /releases list instead and taking the first (most recent) entry
# works regardless of prerelease status.
API_URL = f"https://api.github.com/repos/{REPO}/releases"


def already_installed() -> bool:
    try:
        import xi_tinkerer  # noqa: F401
        return True
    except ImportError:
        return False


def pick_asset(assets: list[dict]) -> dict | None:
    """Prefer a wheel matching this exact Python version's abi tag, but abi3 wheels are built to
    work across Python versions from their pinned floor upward -- so fall back to any win_amd64
    abi3 wheel if no exact match exists, rather than failing outright."""
    py_tag = f"cp{sys.version_info.major}{sys.version_info.minor}"

    candidates = [
        a for a in assets
        if a["name"].endswith(".whl") and "win_amd64" in a["name"]
    ]
    if not candidates:
        return None

    for a in candidates:
        if py_tag in a["name"]:
            return a

    for a in candidates:
        if "abi3" in a["name"]:
            return a

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
    except Exception as e:
        print(f"[ERROR] Could not reach GitHub to check releases: {e}")
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
        except Exception as e:
            print(f"[ERROR] Download failed: {e}")
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
