#!/usr/bin/env python3
"""
reset_install.py -- strips this toolkit install back to a clean, source-only state, for testing
`setup.bat` (or any other first-run flow) from scratch without doing it by hand every time.

Deletes exactly what DIST_PACKAGING.md's "Confirmed: strip" section lists -- generated/cached/
fetched data, never hand-authored source -- and nothing else. Every item here is either rebuilt by
a `build_*.py` indexer or re-fetched by `install_external_tools.py` on the next `setup.bat` run, so
none of this is a real loss; it's the same "clean rebuild is fine" answer the user already gave for
CORE_AGNOSTIC_DESIGN.md's Open Question #3, just automated instead of done by hand.

Never touches `test_fixtures/` (checked-in regression data, not install state) or any real source
file (.py/templates/docs/setup.bat/etc) -- only the specific paths listed in TARGETS below, each
one cross-checked against DIST_PACKAGING.md before being added here.

Usage:
    py -3 reset_install.py                    # dry run -- lists what WOULD be deleted, deletes nothing
    py -3 reset_install.py --i-am-sure         # actually deletes it
    py -3 reset_install.py --i-am-sure --keep-db-backup   # back up the DB first (default: on)
"""
import argparse
import shutil
import sys
from pathlib import Path

TOOLS_ROOT = Path(__file__).parent

# (path relative to TOOLS_ROOT, human label) -- checked against DIST_PACKAGING.md's "Confirmed:
# strip" list item for item, not guessed. Directories are removed recursively; files singly.
TARGET_DIRS = [
    ("db_backups", "local DB backup history"),
    ("mission_reports", "generated reports + indexer scratch/parse-cache (_dialog_index_tmp, "
                         "_npc_index_tmp, _sql_clean, _lsb_clean, per-zone folders)"),
    ("LandSandBoat", "bundled LSB checkout (re-fetched by setup.bat / Install button)"),
    ("FFXI-DATS", "door/prop/elevator/zone-line position data (re-fetched)"),
    ("FFXI-Resources-dist", "external item/keyitem reference catalogue (re-fetched)"),
    (".venv", "this toolkit's dedicated Python environment (recreated by setup.bat)"),
    ("gui/static/zone_visual", "build_zone_visual_cache.py's generated per-zone OBJ mesh cache"),
]
TARGET_FILES = [
    ("ffxi_zone_database.db", "the main SQLite database"),
    ("ffxi_zone_database.db-wal", "SQLite WAL journal"),
    ("ffxi_zone_database.db-shm", "SQLite shared-memory index"),
    ("gui_server.log", "runtime log"),
    ("toolkit_config.txt", "setup.bat's saved FFXI/Topaz path answers"),
    ("vendor/xi-tinkerer/target/release/xi-tinkerer-cli.exe", "fetched xi-tinkerer binary (not the "
                                                                "rest of xi-tinkerer/, which is real source)"),
]
# __pycache__ can appear under any subdirectory, not just the root -- found via rglob rather than
# a fixed path list.
PYCACHE_GLOB = "**/__pycache__"


def _dir_size(path: Path) -> int:
    return sum(f.stat().st_size for f in path.rglob("*") if f.is_file())


def plan() -> list[tuple[Path, str, int]]:
    """Returns [(path, label, size_bytes), ...] for every real target that actually exists --
    never lists something that isn't there, so a re-run after a partial reset shows only what's
    genuinely left."""
    items = []
    top_level_dirs = []
    for rel, label in TARGET_DIRS:
        p = TOOLS_ROOT / rel
        if p.is_dir():
            items.append((p, label, _dir_size(p)))
            top_level_dirs.append(p)
    for rel, label in TARGET_FILES:
        p = TOOLS_ROOT / rel
        if p.is_file():
            items.append((p, label, p.stat().st_size))
    for p in TOOLS_ROOT.glob(PYCACHE_GLOB):
        if not p.is_dir():
            continue
        # Skip a __pycache__ that's already inside one of the whole-directory targets above (e.g.
        # .venv/, LandSandBoat/) -- confirmed real bug 2026-09-08: .venv alone has 100+ nested
        # __pycache__ dirs, each individually recursed and listed as its own line, when deleting
        # .venv wholesale already covers every one of them. Only list a __pycache__ that's a real,
        # independent target on its own (e.g. under this project's own source tree).
        if any(top in p.parents for top in top_level_dirs):
            continue
        items.append((p, "Python bytecode cache", _dir_size(p)))
    return items


def human_size(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.0f}{unit}"
        n /= 1024
    return f"{n:.1f}TB"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--i-am-sure", action="store_true",
                     help="actually delete -- without this, only a dry-run listing is printed")
    ap.add_argument("--no-db-backup", action="store_true",
                     help="skip the extra DB backup this script takes before deleting the DB by "
                          "default (db_backups/ itself is also being deleted, so this backup is "
                          "written one level up, in TOOLS_ROOT, not inside db_backups/)")
    args = ap.parse_args()

    items = plan()
    if not items:
        print("Nothing to reset -- this install is already clean (or reset_install.py already ran).")
        return

    total = sum(size for _, _, size in items)
    print(f"{'Would delete' if not args.i_am_sure else 'Deleting'} {len(items)} item(s), "
          f"{human_size(total)} total:\n")
    for path, label, size in items:
        rel = path.relative_to(TOOLS_ROOT)
        print(f"  {human_size(size):>8}  {rel}  -- {label}")

    if not args.i_am_sure:
        print("\nDry run only -- nothing was deleted. Re-run with --i-am-sure to actually reset.")
        return

    db_path = TOOLS_ROOT / "ffxi_zone_database.db"
    if db_path.exists() and not args.no_db_backup:
        import datetime
        stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        backup_path = TOOLS_ROOT / f"ffxi_zone_database-pre-reset-{stamp}.db"
        print(f"\nBacking up the current DB to {backup_path.name} before deleting (pass "
              f"--no-db-backup to skip)...")
        shutil.copy2(db_path, backup_path)

    print()
    for path, label, _ in items:
        rel = path.relative_to(TOOLS_ROOT)
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()
        print(f"  deleted {rel}")

    print("\nDone. This install is now source-only -- run setup.bat (or the individual "
          "install_external_tools.py/build_*.py steps) to rebuild it from scratch.")


if __name__ == "__main__":
    main()
