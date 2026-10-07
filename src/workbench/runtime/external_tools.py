#!/usr/bin/env python3
"""
Runtime service for downloading optional external data/tools straight from their
real GitHub source, same idea as install_xi_tinkerer.py but generalized for the home page's
other "missing" entries. Stdlib only (urllib, json, zipfile) -- no extra pip packages needed.

Usage:
    python install_external_tools.py xi-tinkerer-cli
    python install_external_tools.py ffxi-dats
"""
import json
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path

from workbench.runtime.paths import REPO_ROOT

TOOLS_ROOT = REPO_ROOT


# Tools whose real installer can need a manual admin-elevated run (see install_tesseract()'s
# WinError 740 case) -- glob pattern for that tool's leftover installer file under vendor/, so the
# UI can reference "you already downloaded this, here's the file and the exact folder to type"
# instead of re-downloading or silently forgetting about it.
PENDING_INSTALLER_GLOBS = {
    "tesseract": "tesseract-ocr-w64-setup-*.exe",
}


def pending_installer(tool: str) -> Path | None:
    """Real leftover installer file for `tool` under vendor/, if install_<tool>() downloaded one
    but couldn't finish silently (e.g. needs a UAC prompt only a human can click through)."""
    pattern = PENDING_INSTALLER_GLOBS.get(tool)
    if pattern is None:
        return None
    matches = sorted((TOOLS_ROOT / "vendor").glob(pattern))
    return matches[-1] if matches else None


def _get_json(url: str) -> dict | list:
    req = urllib.request.Request(url, headers={"User-Agent": "mission-toolkit-setup"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def install_xi_tinkerer_cli() -> tuple[bool, str]:
    """Downloads the real prebuilt xi-tinkerer-cli.exe from InoUno/xi-tinkerer's latest real
    (non-prerelease) GitHub release -- confirmed live this session that this repo actually ships
    a ready-to-run Windows exe as a release asset, no Rust/cargo build needed at all."""
    dest = TOOLS_ROOT / "vendor" / "xi-tinkerer" / "target" / "release" / "xi-tinkerer-cli.exe"
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


def install_yt_dlp() -> tuple[bool, str]:
    """Installs the yt-dlp Python package via pip into this same interpreter -- it's a normal pip
    package (not a standalone binary), so this is just `pip install`, same as pytesseract."""
    if shutil.which("yt-dlp"):
        return True, "already installed"
    try:
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "--quiet", "yt-dlp"],
            check=True, capture_output=True, text=True,
        )
    except subprocess.CalledProcessError as e:
        return False, f"pip install failed: {e.stderr.strip()[-500:]}"
    return (True, "installed via pip") if shutil.which("yt-dlp") else (
        False, "pip install reported success but 'yt-dlp' still not on PATH -- check your Scripts/ dir is on PATH"
    )


def install_ffmpeg() -> tuple[bool, str]:
    """Downloads the real prebuilt Windows ffmpeg 'essentials' build from gyan.dev (the same
    build already vendored manually this session, confirmed working via `ffmpeg -version`) and
    vendors it under vendor/ffmpeg/bin/ -- no system PATH changes, matches youtube_chat_ocr.py's
    resolve_tool() fallback lookup."""
    dest_bin = TOOLS_ROOT / "vendor" / "ffmpeg" / "bin"
    if (dest_bin / "ffmpeg.exe").exists():
        return True, "already installed"

    url = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
    with tempfile.TemporaryDirectory() as tmp:
        zip_path = Path(tmp) / "ffmpeg.zip"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "mission-toolkit-setup"})
            with urllib.request.urlopen(req, timeout=120) as resp, open(zip_path, "wb") as out:
                shutil.copyfileobj(resp, out)
        except Exception as e:
            return False, f"download failed: {e}"

        try:
            with zipfile.ZipFile(zip_path) as zf:
                extract_dir = Path(tmp) / "extracted"
                zf.extractall(extract_dir)
                inner_dirs = [d for d in extract_dir.iterdir() if d.is_dir()]
                if len(inner_dirs) != 1:
                    return False, "unexpected zip layout from gyan.dev"
                src_bin = inner_dirs[0] / "bin"
                dest_bin.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(src_bin), str(dest_bin))
        except Exception as e:
            return False, f"extraction failed: {e}"

    return True, "installed (vendored under vendor/ffmpeg/bin/)"


def install_tesseract() -> tuple[bool, str]:
    """Downloads the real UB-Mannheim Windows tesseract-ocr installer (the canonical Windows
    build, linked from https://github.com/UB-Mannheim/tesseract/wiki) and tries to run it
    silently (NSIS /S) into a vendored install dir -- no system PATH or default Program Files
    write needed. Resolves the current version by scraping the UB-Mannheim download index rather
    than hardcoding one, since that page is the real source of truth for the latest build.

    This installer's exe manifest requests admin elevation regardless of install target
    (confirmed live: WinError 740 even with /D pointed outside Program Files) -- there is no
    silent/unattended way around that from an unattended script, and this tool will not attempt
    to defeat a UAC prompt. When that happens the download is kept (not cleaned up) so the caller
    can just double-click it and approve the one UAC prompt themselves, using the /D path printed
    back to them so resolve_tool() still finds it afterwards."""
    dest_dir = TOOLS_ROOT / "vendor" / "tesseract"
    dest_exe = dest_dir / "tesseract.exe"
    if dest_exe.exists():
        return True, "already installed"

    index_url = "https://digi.bib.uni-mannheim.de/tesseract/"
    try:
        req = urllib.request.Request(index_url, headers={"User-Agent": "mission-toolkit-setup"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            html = resp.read().decode("utf-8", errors="ignore")
    except Exception as e:
        return False, f"could not reach {index_url}: {e}"

    names = re.findall(r"tesseract-ocr-w64-setup-([\w.\-]+)\.exe", html)
    if not names:
        return False, "could not find a tesseract-ocr-w64-setup-*.exe link on the UB-Mannheim page"
    # filenames sort correctly as version strings for this project's purposes (5.x.y.YYYYMMDD)
    latest = sorted(names)[-1]
    installer_name = f"tesseract-ocr-w64-setup-{latest}.exe"
    installer_url = index_url + installer_name
    downloaded_path = TOOLS_ROOT / "vendor" / installer_name

    if not downloaded_path.exists():
        downloaded_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            req = urllib.request.Request(installer_url, headers={"User-Agent": "mission-toolkit-setup"})
            with urllib.request.urlopen(req, timeout=120) as resp, open(downloaded_path, "wb") as out:
                shutil.copyfileobj(resp, out)
        except Exception as e:
            return False, f"download failed: {e}"

    dest_dir.mkdir(parents=True, exist_ok=True)
    try:
        # NSIS silent install; /D must be the last argument and unquoted with no trailing slash.
        subprocess.run(
            [str(downloaded_path), "/S", f"/D={dest_dir}"],
            check=True, timeout=180,
        )
    except OSError as e:
        if getattr(e, "winerror", None) == 740:
            return False, (
                f"downloaded {installer_name} to {downloaded_path} but it needs admin rights to "
                f"run (even silently) -- double-click it yourself, approve the UAC prompt, and "
                f"when the installer asks for a folder use exactly: {dest_dir}"
            )
        return False, f"silent install failed: {e}"
    except Exception as e:
        return False, f"silent install failed: {e}"

    if not dest_exe.exists():
        return False, f"installer ran but {dest_exe} was not created -- check {dest_dir} for its actual layout"
    downloaded_path.unlink(missing_ok=True)
    return True, f"installed tesseract {latest} (vendored under vendor/tesseract/)"


INSTALLERS = {
    "xi-tinkerer-cli": install_xi_tinkerer_cli,
    "ffxi-dats": install_ffxi_dats,
    "landsandboat-full": install_landsandboat_full,
    "ffxi-resources-dist": install_ffxi_resources_dist,
    "yt-dlp": install_yt_dlp,
    "ffmpeg": install_ffmpeg,
    "tesseract": install_tesseract,
}

_FORCE_ARGS = ("landsandboat-full", "ffxi-resources-dist")


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in INSTALLERS:
        print(f"Usage: {sys.argv[0]} <{'|'.join(INSTALLERS)}> [--force]")
        sys.exit(1)
    force = "--force" in sys.argv[2:]
    fn = INSTALLERS[sys.argv[1]]
    ok, message = fn(force=force) if sys.argv[1] in _FORCE_ARGS else fn()
    print(message)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
