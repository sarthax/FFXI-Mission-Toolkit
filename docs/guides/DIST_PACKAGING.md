# Distro packaging: what to keep vs. strip

Working notes on what belongs in a clean release/distro copy of this toolkit vs. what's local
generated/cached state that should be stripped (and, where possible, how to regenerate it).
Written 2026-09-08 during CORE_AGNOSTIC_DESIGN.md phase-1 work, after confirming sizes of every
top-level directory in the live D:\Claude\mission_toolkit checkout. Not exhaustive yet -- flagged
items need a follow-up check before being treated as settled.

`D:\Claude\mission_toolkit_dist_test\mission_toolkit` is the existing designated location for
building/testing a clean rebuild-distro copy -- it's already source-only (no DB, no LandSandBoat/
checkout present as of 2026-09-08), which matches the "strip generated data" model below.

## Confirmed: strip (generated/cache/local state, safe to delete, regenerable)

- `ffxi_zone_database.db` (~2.5GB) + `.db-wal`/`.db-shm` -- the whole point of a "clean rebuild"
  per the user's own 2026-09-08 answer to CORE_AGNOSTIC_DESIGN.md's Open Question #3: rebuilt
  fresh from the various `build_*.py` indexers against a real checkout, not shipped.
- `db_backups/` (~1.3GB) -- local automatic DB backups (see settings.py's `backup_retention_count`
  and build_database.py's `backup_database_file()`). Purely local safety net, never distro content.
- `mission_reports/_dialog_index_tmp/` (~582MB), `mission_reports/_npc_index_tmp/` (~4.6MB) --
  named `_tmp` by their own authors; intermediate scratch state for build_dialog_index.py /
  build_npc_index.py, not a real deliverable.
- `mission_reports/_sql_clean/`, `mission_reports/_lsb_clean/` (~9MB) -- build_sql_index.py's/
  build_lsb_index.py's own comment-stripped `.sql` parse cache (see `cleaned_path()`), keyed by a
  hash of the source file's resolved path + its own mtime check -- always safe to delete, always
  regenerates itself on next indexer run.
- `mission_reports/<ZONE_NAME>/` per-zone folders -- generated report output from various
  build_*.py/CLI report commands, not hand-authored content.
- `__pycache__/` -- standard Python bytecode cache.
- `gui_server.log` -- runtime log file.
- `LandSandBoat/` (~179MB) -- the bundled full LandSandBoat/server checkout ("base" branch),
  fetched by `install_external_tools.py`'s `install_landsandboat_full()`. Re-fetchable on demand;
  don't ship the checkout itself in a source/distro package. (Whether a *built* distro should
  bundle it anyway for user convenience -- since core-module users now need a real LSB checkout to
  point the LSB-primary indexer at, per CORE_AGNOSTIC_DESIGN.md -- is a separate packaging-policy
  question, not a "strip" answer; needs a decision once phase 1 is proven out.)
- `FFXI-DATS/` -- similarly fetched by `install_external_tools.py`'s `install_ffxi_dats()`
  (~200MB per its own docstring) when present; strip and re-fetch, not hand content.
- `xi-tinkerer/target/release/xi-tinkerer-cli.exe` -- fetched by
  `install_external_tools.py`'s `install_xi_tinkerer_cli()` (downloads a prebuilt release exe from
  InoUno/xi-tinkerer's GitHub releases); the rest of `xi-tinkerer/` may be real source, not just
  this downloaded binary -- see flagged item below.
- `FFXI-Resources-dist/` -- added 2026-09-08, same class as LandSandBoat/FFXI-DATS above: fetched
  by `install_external_tools.py`'s `install_ffxi_resources_dist()` from sruon/FFXI-Resources' real
  public release bucket (`items.ndjson.gz`/`keyitems.ndjson.gz`), resolves `latest` at fetch time
  rather than a pinned version. Strip and re-fetch, not hand content.
- `toolkit_config.txt` -- added 2026-09-08: `setup.bat`'s own saved FFXI/Topaz path answers from a
  prior run (see setup.bat's own comment: "delete that file if you ever need to change them",
  written specifically to be user-deletable). Install-specific local state, never distro content.
- `.venv/` -- added 2026-09-08: this toolkit's own dedicated Python virtual environment, created
  by `setup.bat` (`python -m venv .venv`) and used for every subsequent Python invocation in that
  script and in `start.bat`. **Why a venv exists at all** (real incident, not precautionary):
  `requirements.txt`'s `luaparser>=4.0` (needed by `xi-events-py`'s event decompiler) permanently
  pins `antlr4-python3-runtime==4.13.2` -- confirmed live that every `luaparser` release since 4.0
  pins the exact same version, no compatible alternative exists -- which directly conflicts with
  at least one other real, unrelated package (`omegaconf`, pinned to `antlr4-python3-runtime==
  4.9.*`) that happened to already be installed in this project's system-wide Python. Installing
  straight into the system Python silently broke `omegaconf` the first time this was tried.
  Regenerable via `python -m venv .venv` + `pip install -r requirements.txt` + `install_xi_tinkerer.py`
  (exactly what `setup.bat` already does) -- strip and recreate, not hand content.

See `reset_install.py`/`reset_install.bat` (added 2026-09-08) for a script that strips everything
in this section automatically, for testing a from-scratch `setup.bat` run without doing this by
hand each time.

## `addons/` -- neither strip nor a distro-source concern (added 2026-09-08)

`addons/*.zip` (see `addon_tools.py`) are small, hand-packaged bundles of real data one install
already has that another install would otherwise have to regenerate the slow way (network scrape,
etc.) -- e.g. `addons/bg-wiki-dump.zip` holds the real BG-Wiki page dump `scrape_bg_wiki.py` would
otherwise need to re-scrape from scratch. Not a "strip" item (`reset_install.py` deliberately never
touches `addons/`) and not really "distro source" either -- it's a portable, checksummed local
package a user can carry between their own installs (or attach to a future release) without
re-fetching data that's genuinely already sitting on their disk somewhere. `py -3 addon_tools.py
list` shows what's packaged in a given install; `py -3 addon_tools.py package <name> <file...>`
creates a new one from any real file(s) already present.

## Confirmed: keep (hand-authored source, not reproducible by re-running a script)

- All top-level `.py` files (build_*.py, gui_server.py, settings.py, entity_profile.py, etc.),
  `setup.bat`, `start.bat`, `requirements.txt`, `*.md` docs, `.csv` reference data
  (appraisal_item_id_xref.csv, appraisal_pools_with_item_ids.csv -- small, hand-curated).
- `gui/templates/` (268K) -- the actual page templates.

## Confirmed: strip (settled 2026-09-13)

- `gui/static/zone_visual/` (~311MB as of 2026-09-13, grows per zone visited) -- confirmed
  entirely `build_zone_visual_cache.py`'s generated per-zone Wavefront OBJ cache (real zone visual
  mesh, re-derivable from a real LandSandBoat/FFXI DAT source any install already needs). This was
  the flagged suspicion in the original "needs a follow-up check" note below -- inspected
  (`gui/static/` had exactly one subdirectory, `zone_visual/`, holding only `.obj` files) and
  confirmed generated, not hand-authored frontend assets. `gui/templates/` (268K) is the real
  hand-authored content; `gui/static/` otherwise doesn't exist until a zone is viewed. Added to
  `reset_install.py`'s `TARGET_DIRS`.

## Consolidated under `vendor/` (settled 2026-09-14)

The vendored/cloned third-party tool checkouts flagged below were never individually resolved as
strip-vs-keep -- instead, consolidated under one `vendor/` directory (repo-root cleanup, requested
separately from the strip-vs-keep question) so they're at least visibly separated from this
project's own code, even though the strip-vs-keep decision for each is still genuinely open:
`xi-model-viewer/`, `xi-tinkerer/`, `dat-extractor/`, `xi-events-py/`, `xi-tinkerer-py/`,
`Packetlyzer/`, `ResourceBuilder/`, `ResourceExtractor/`, `Resources/`, `VieweD-master/`,
`XiEvents/`, `FFXI-EventsDump/`, `FFXI-Resources/`, `FFXIDat/`, `ffxi/`, `reference_addons/`,
`upx/`, `ffxi-wiki-dumps-dist/`. Every real code path referencing one of these
(`TOOLS_ROOT / "..."` style constants, ~20 across the codebase) was updated to the new
`vendor/<name>` location and verified live (GUI homepage/Packet Decoder pages load with zero
errors, `addons/bg-wiki-dump.zip`'s manifest re-packaged since it hardcoded the old path).
`FFXI-DATS/`, `FFXI-Resources-dist/`, and `LandSandBoat/` deliberately stay at the repo root, not
under `vendor/` -- they're gitignored, re-fetched install artifacts (see "Confirmed: strip" above),
not checked-in vendored source.

## Needs a follow-up check before deciding (flagged, not yet settled)

The `vendor/` directories above are still not individually confirmed as "safe to strip and
re-clone" vs. "modified locally / no upstream to re-fetch from." Check each against
`TOOLING_OVERVIEW.md` and whether `install_external_tools.py` / `install_xi_tinkerer.py` (or
another install script) actually manages it before stripping.

## How to use this doc

Before building a distro/release copy: strip everything in the first section, keep everything in
the second section as-is, and resolve the third section's open items (inspect the directory, check
whether an install_*.py script owns it) before deciding to strip or keep each one -- update this
doc with the answer once resolved, rather than re-deriving it from scratch next time.
