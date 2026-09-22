#!/usr/bin/env python3
"""
addon_tools.py -- packages/installs local "addon" data bundles: real, already-fetched data (a
BG-Wiki dump, etc.) that doesn't come from a public URL install_external_tools.py's own installers
can hit, but that's genuinely reusable across installs without redownloading/rescraping it from
scratch every time. Complements install_external_tools.py (network fetches from a known public
source) rather than replacing it -- this is for real data ONE install already has that another
install would otherwise have to regenerate the slow way.

An addon is a single self-contained .zip under addons/, containing:
  - manifest.json -- {"name", "description", "created" (ISO date), "files": {relpath: sha256}}
  - the real data file(s) themselves, at whatever relative-to-TOOLS_ROOT paths manifest.json's
    "files" keys say (e.g. "vendor/ffxi-wiki-dumps-dist/bg-wiki.jsonl.gz")

Usage:
    py -3 addon_tools.py list
    py -3 addon_tools.py install bg-wiki-dump
    py -3 addon_tools.py install bg-wiki-dump --force     # overwrite an existing different file
    py -3 addon_tools.py package bg-wiki-dump \\
        vendor/ffxi-wiki-dumps-dist/bg-wiki.jsonl.gz \\
        --description "BG Wiki page dump (real scraped content, see scrape_bg_wiki.py)"
"""
import argparse
import hashlib
import json
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

TOOLS_ROOT = Path(__file__).parent
ADDONS_DIR = TOOLS_ROOT / "addons"


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def cmd_list():
    if not ADDONS_DIR.is_dir():
        print("No addons/ directory yet -- nothing packaged.")
        return
    zips = sorted(ADDONS_DIR.glob("*.zip"))
    if not zips:
        print("addons/ exists but has no .zip packages yet.")
        return
    for zpath in zips:
        try:
            with zipfile.ZipFile(zpath) as zf:
                manifest = json.loads(zf.read("manifest.json"))
        except (KeyError, json.JSONDecodeError, zipfile.BadZipFile) as e:
            print(f"  {zpath.stem}  [!] unreadable/invalid addon package: {e}")
            continue
        size = sum(zi.file_size for zi in zipfile.ZipFile(zpath).infolist())
        print(f"  {manifest.get('name', zpath.stem)}  "
              f"({human_size(size)}, packaged {manifest.get('created', '?')})")
        print(f"      {manifest.get('description', '(no description)')}")
        for relpath in manifest.get("files", {}):
            print(f"      -> {relpath}")


def human_size(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.0f}{unit}"
        n /= 1024
    return f"{n:.1f}TB"


def cmd_package(name: str, files: list[str], description: str):
    ADDONS_DIR.mkdir(parents=True, exist_ok=True)
    manifest = {
        "name": name,
        "description": description or "(no description given)",
        "created": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "files": {},
    }
    out_path = ADDONS_DIR / f"{name}.zip"
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for rel in files:
            src = TOOLS_ROOT / rel
            if not src.is_file():
                print(f"[!] {rel} doesn't exist under {TOOLS_ROOT} -- skipping, not packaged")
                continue
            manifest["files"][rel] = _sha256(src)
            zf.write(src, arcname=rel)
        zf.writestr("manifest.json", json.dumps(manifest, indent=2))
    if not manifest["files"]:
        out_path.unlink()
        print("Nothing real to package -- no addon written.")
        return
    print(f"Packaged {out_path.relative_to(TOOLS_ROOT)} "
          f"({human_size(out_path.stat().st_size)}, {len(manifest['files'])} file(s)):")
    for rel in manifest["files"]:
        print(f"  {rel}")


def install_addon(name: str, force: bool = False) -> tuple[bool, str]:
    """Real install logic, (ok, message) return -- same shape install_external_tools.py's own
    INSTALLERS functions use, so gui_server.py's /install/{tool} route can drive this one the same
    way it already drives those (see the ADDON_PREFIX dispatch there). cmd_install below is a thin
    CLI wrapper around this, not a second implementation."""
    zpath = ADDONS_DIR / f"{name}.zip"
    if not zpath.is_file():
        return False, (f"No such addon package: {zpath.relative_to(TOOLS_ROOT)} -- run "
                        f"'py -3 addon_tools.py list' to see what's available.")

    lines = []
    any_failed = False
    with zipfile.ZipFile(zpath) as zf:
        manifest = json.loads(zf.read("manifest.json"))
        for rel, expected_hash in manifest.get("files", {}).items():
            dest = TOOLS_ROOT / rel
            if dest.exists():
                if _sha256(dest) == expected_hash:
                    lines.append(f"{rel}: already installed, identical, skipped")
                    continue
                if not force:
                    lines.append(f"{rel}: exists with DIFFERENT content, not overwritten "
                                  f"(pass force to replace it)")
                    any_failed = True
                    continue
            dest.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(rel) as src, open(dest, "wb") as out:
                out.write(src.read())
            if _sha256(dest) != expected_hash:
                lines.append(f"{rel}: WARNING -- extracted content doesn't match the package's "
                              f"own checksum (corrupted package or extraction issue)")
                any_failed = True
            else:
                lines.append(f"{rel}: installed, checksum verified")
    label = manifest.get("name", name)
    return not any_failed, f"{label}: " + "; ".join(lines)


def cmd_install(name: str, force: bool):
    ok, message = install_addon(name, force)
    print(message.replace("; ", "\n  "))
    if not ok:
        sys.exit(1)
    print("Done.")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="command", required=True)

    sub.add_parser("list", help="show available addons/*.zip packages")

    p_install = sub.add_parser("install", help="extract an addon package into this install")
    p_install.add_argument("name", help="addon name (matches addons/<name>.zip)")
    p_install.add_argument("--force", action="store_true",
                            help="overwrite an existing destination file with different content")

    p_package = sub.add_parser("package", help="bundle existing real file(s) from this install into a new addon package")
    p_package.add_argument("name", help="name for the new addon package (addons/<name>.zip)")
    p_package.add_argument("files", nargs="+", help="path(s), relative to this install's root, to include")
    p_package.add_argument("--description", default="", help="human-readable description stored in the manifest")

    args = ap.parse_args()
    if args.command == "list":
        cmd_list()
    elif args.command == "install":
        cmd_install(args.name, args.force)
    elif args.command == "package":
        cmd_package(args.name, args.files, args.description)


if __name__ == "__main__":
    main()
