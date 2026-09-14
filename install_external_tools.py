#!/usr/bin/env python3
"""
install_external_tools.py -- auto-downloads optional external data/tools straight from their
real GitHub source, same idea as install_xi_tinkerer.py but generalized for the home page's
other "missing" entries. Stdlib only (urllib, json, zipfile) -- no extra pip packages needed.

Usage:
    python install_external_tools.py xi-tinkerer-cli
    python install_external_tools.py ffxi-dats
"""
import json
import shutil
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path

TOOLS_ROOT = Path(__file__).parent


def _get_json(url: str) -> dict | list:
    req = urllib.request.Request(url, headers={"User-Agent": "mission-toolkit-setup"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def install_xi_tinkerer_cli() -> tuple[bool, str]:
    """Downloads the real prebuilt xi-tinkerer-cli.exe from InoUno/xi-tinkerer's latest real
    (non-prerelease) GitHub release -- confirmed live this session that this repo actually ships
    a ready-to-run Windows exe as a release asset, no Rust/cargo build needed at all."""
    dest = TOOLS_ROOT / "xi-tinkerer" / "target" / "release" / "xi-tinkerer-cli.exe"
    if dest.exists():
        return True, "already installed"

    repo = "InoUno/xi-tinkerer"
    try:
        releases = _get_json(f"https://api.github.com/repos/{repo}/releases")
    except Exception as e:
        return False, f"could not reach GitHub: {e}"

    for release in releases:
        if release.get("prerelease"):
            continue
        for asset in release.get("assets", []):
            if asset["name"] == "xi-tinkerer-cli.exe":
                try:
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    urllib.request.urlretrieve(asset["browser_download_url"], dest)
                except Exception as e:
                    return False, f"download failed: {e}"
                return True, f"installed {release.get('tag_name', '?')}"

    return False, f"no xi-tinkerer-cli.exe asset found in any release of {repo}"


def install_ffxi_dats() -> tuple[bool, str]:
    """Downloads Xenonsmurf/FFXI-DATS' real repo contents (door/prop/elevator/zone-line
    positions, all zones) as a GitHub zipball -- works for any public repo with no auth, no git
    client needed. ~200MB, so this can take a minute depending on connection."""
    dest = TOOLS_ROOT / "FFXI-DATS"
    if dest.is_dir():
        return True, "already installed"

    repo = "Xenonsmurf/FFXI-DATS"
    try:
        info = _get_json(f"https://api.github.com/repos/{repo}")
        branch = info.get("default_branch", "main")
    except Exception as e:
        return False, f"could not reach GitHub: {e}"

    zip_url = f"https://github.com/{repo}/archive/refs/heads/{branch}.zip"
    with tempfile.TemporaryDirectory() as tmp:
        zip_path = Path(tmp) / "ffxi-dats.zip"
        try:
            urllib.request.urlretrieve(zip_url, zip_path)
        except Exception as e:
            return False, f"download failed: {e}"

        try:
            with zipfile.ZipFile(zip_path) as zf:
                # GitHub's zip wraps everything in one top-level "<repo>-<branch>/" folder --
                # extract to a temp dir then move that folder's contents up one level so
                # FFXI-DATS/ itself matches what a manual git clone would look like.
                extract_dir = Path(tmp) / "extracted"
                zf.extractall(extract_dir)
                inner_dirs = [d for d in extract_dir.iterdir() if d.is_dir()]
                if len(inner_dirs) != 1:
                    return False, "unexpected zip layout from GitHub"
                shutil.move(str(inner_dirs[0]), str(dest))
        except Exception as e:
            return False, f"extraction failed: {e}"

    return True, "installed"


def install_landsandboat_full(force: bool = False) -> tuple[bool, str]:
    """Replaces the bundled LandSandBoat/ checkout (currently a partial extract -- only 6 zones'
    scripts/zones/, no scripts/globals/ at all, confirmed missing xi.effect and other enum files
    needed for id-drift checking) with the real, full LandSandBoat/server repo from GitHub. Its
    default branch is 'base', not 'main' -- confirmed live via the repos API, not assumed."""
    dest = TOOLS_ROOT / "LandSandBoat"
    if dest.is_dir() and not force:
        return True, "already installed (pass force=True to re-pull)"

    repo = "LandSandBoat/server"
    try:
        info = _get_json(f"https://api.github.com/repos/{repo}")
        branch = info.get("default_branch", "base")
    except Exception as e:
        return False, f"could not reach GitHub: {e}"

    zip_url = f"https://github.com/{repo}/archive/refs/heads/{branch}.zip"
    with tempfile.TemporaryDirectory() as tmp:
        zip_path = Path(tmp) / "landsandboat.zip"
        try:
            urllib.request.urlretrieve(zip_url, zip_path)
        except Exception as e:
            return False, f"download failed: {e}"

        try:
            with zipfile.ZipFile(zip_path) as zf:
                extract_dir = Path(tmp) / "extracted"
                zf.extractall(extract_dir)
                inner_dirs = [d for d in extract_dir.iterdir() if d.is_dir()]
                if len(inner_dirs) != 1:
                    return False, "unexpected zip layout from GitHub"
                # Move the old partial copy aside instead of deleting outright, in case the new
                # one turns out incomplete for some reason -- cheap insurance, cleaned up on success.
                backup = None
                if dest.is_dir():
                    backup = TOOLS_ROOT / "LandSandBoat_partial_backup"
                    if backup.exists():
                        shutil.rmtree(backup)
                    shutil.move(str(dest), str(backup))
                try:
                    shutil.move(str(inner_dirs[0]), str(dest))
                except Exception:
                    if backup is not None:
                        shutil.move(str(backup), str(dest))
                    raise
                if backup is not None:
                    shutil.rmtree(backup)
        except Exception as e:
            return False, f"extraction failed: {e}"

    return True, f"installed full LandSandBoat/server ({branch} branch)"


def install_ffxi_resources_dist(force: bool = False) -> tuple[bool, str]:
    """Downloads items.ndjson.gz + keyitems.ndjson.gz from sruon/FFXI-Resources' own public,
    no-auth-required release bucket (see FFXI-Resources/docs/BUCKET.md) -- real, versioned,
    confirmed live (https://ffxi-resources.sruon.dev/versions.json). Resolves 'latest' at
    install time rather than hardcoding a version, so this stays current as new client versions
    get published -- build_database.py's load_items_external()/load_keyitems_external() only
    ever read these two files back out of FFXI-Resources-dist/, not the parquet/meta/schema
    siblings also published in the same bucket, so only those two are fetched here."""
    dest = TOOLS_ROOT / "FFXI-Resources-dist"
    if dest.is_dir() and not force:
        return True, "already installed (pass force=True to re-pull)"

    base = "https://ffxi-resources.sruon.dev"
    try:
        versions = _get_json(f"{base}/versions.json")
        version = versions["latest"]
    except Exception as e:
        return False, f"could not reach ffxi-resources.sruon.dev: {e}"

    dest.mkdir(parents=True, exist_ok=True)
    for fname in ("items.ndjson.gz", "keyitems.ndjson.gz"):
        try:
            # urlretrieve sends no User-Agent header at all -- this bucket's CDN returns a bare
            # 403 for that (confirmed live), same reason _get_json() above sets one for GitHub's
            # API. A real browser/curl UA isn't required, just a non-empty one.
            req = urllib.request.Request(
                f"{base}/versions/{version}/{fname}", headers={"User-Agent": "mission-toolkit-setup"}
            )
            with urllib.request.urlopen(req, timeout=60) as resp, open(dest / fname, "wb") as out:
                shutil.copyfileobj(resp, out)
        except Exception as e:
            return False, f"download of {fname} failed: {e}"

    return True, f"installed FFXI-Resources-dist (version {version})"


INSTALLERS = {
    "xi-tinkerer-cli": install_xi_tinkerer_cli,
    "ffxi-dats": install_ffxi_dats,
    "landsandboat-full": install_landsandboat_full,
    "ffxi-resources-dist": install_ffxi_resources_dist,
}


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in INSTALLERS:
        print(f"Usage: {sys.argv[0]} <{'|'.join(INSTALLERS)}> [--force]")
        sys.exit(1)
    force = "--force" in sys.argv[2:]
    fn = INSTALLERS[sys.argv[1]]
    ok, message = fn(force=force) if sys.argv[1] in ("landsandboat-full", "ffxi-resources-dist") else fn()
    print(message)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
