#!/usr/bin/env python3
"""
gui_server.py -- Mission Toolkit GUI, the actual browsable front end.

Wraps the CLI tools already built this session (build_dialog_index.py, build_npc_index.py,
build_sql_index.py, lookup_entity.py, ingest_global_tables.py, explore_event.py) in a local
FastAPI + server-rendered HTML app -- per the Mission Toolkit GUI proposal's own recommended
stack. Every route below imports and reuses those modules' real functions directly (no reimplemented
logic, no subprocess-shelling-out-to-itself) -- this is a front end for data that's already real
and already indexed, not a new data pipeline.

Run:
    py -3 gui_server.py
    then open http://localhost:8420
"""
import base64
import colorsys
import csv
import gzip
from collections import Counter
import io
import json
import os
import re
import subprocess
import sqlite3
import shutil
import tempfile
import threading
import zipfile
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, Form, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates

import yaml
from PIL import Image, ImageDraw

import build_capture_index
import build_database
import build_dialog_index
import build_npc_index
import build_sql_index
import build_zone_visual_cache
import entity_profile
import explore_event
import ingest_global_tables
import addon_tools
import install_external_tools
import build_lsb_index
import backport_lua_convert
import backport_sql_convert
import backport_binding_index
import backport_binding_audit
import backport_lua_sanity_check
import backport_package
import build_dsp_index
import build_topaz_index
import llm_client
import llm_log
import llm_db_tools
import scrape_bg_wiki
import lookup_entity
import packet_decode
import settings as settings_mod
import wiki_compile

TOOLS_ROOT = Path(__file__).parent
DB_PATH = TOOLS_ROOT / "ffxi_zone_database.db"
TEMPLATES_DIR = TOOLS_ROOT / "gui" / "templates"
# Real in-game 2D zone map PNGs, extracted straight from client DAT files by ResourceExtractor's
# MapParser (see MapDats.json) -- "{zoneid}_{mapindex}.png", one file per submap/floor. Served
# directly from ResourceExtractor's own output dir rather than duplicating 164MB into gui/static.
MAPS_DIR = TOOLS_ROOT / "vendor" / "ResourceExtractor" / "bin" / "Release" / "net9.0-windows" / "resources" / "maps"
# Real, coordinate-aligned top-down silhouettes rasterized from the client's own collision mesh
# (build_zone_topdown.py) -- unlike MAPS_DIR's decorative minimap PNGs, a path plotted using this
# cache's own transform.json lands in the right place by construction (verified empirically
# 2026-09-03, see build_zone_topdown.py's docstring).
TOPDOWN_DIR = TOOLS_ROOT / "gui" / "static" / "zone_topdown"
ZONE_VISUAL_DIR = TOOLS_ROOT / "gui" / "static" / "zone_visual"

from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles

app = FastAPI(title="Mission Toolkit GUI")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
# Zone visual-mesh OBJs (build_zone_visual_cache.py) are real but large (tens of MB of ASCII
# text per zone) -- gzip compresses that ratio very well over the wire, worth it app-wide.
app.add_middleware(GZipMiddleware, minimum_size=1000)
if MAPS_DIR.exists():
    app.mount("/maps", StaticFiles(directory=str(MAPS_DIR)), name="maps")
STATIC_DIR = TOOLS_ROOT / "gui" / "static"
STATIC_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


def get_con() -> sqlite3.Connection:
    # 2026-09-06: real fix -- "database is locked" errors on pages that open a second connection
    # mid-request (e.g. entity_profile.py's own connect() for a write while this connection is
    # still open for reads). WAL mode lets readers and a writer coexist without blocking each
    # other the way the default rollback-journal mode does; PRAGMA is a no-op after the first
    # call (it persists in the db file itself), safe to set on every connection. The timeout
    # bump means two genuinely-concurrent writers wait a moment instead of erroring immediately.
    con = sqlite3.connect(DB_PATH, timeout=30)
    con.execute("PRAGMA journal_mode=WAL")
    con.row_factory = sqlite3.Row
    return con


def _ensure_capture_schema_exists():
    """Real gap found live this session: build_capture_index.init_db() (all CREATE TABLE IF NOT
    EXISTS -- safe to call any time) only ever ran when a capture was actually ingested, or via
    setup.bat's one-off `build_capture_index.py list` CLI call. Nothing recreated it if the
    database was rebuilt/restored/started fresh any other way -- confirmed live: after a database
    recovery, /captures and /missions (which depends on capture_npc_entries for its rollup counts)
    both hard-crashed with "no such table", instead of the intended "0 captures, not something to
    download" empty state. Called once at process startup (below), not per-request -- this is a
    schema guarantee, not per-request work."""
    con = sqlite3.connect(DB_PATH, timeout=30)
    try:
        build_capture_index.init_db(con)
    finally:
        con.close()


_ensure_capture_schema_exists()


# 2026-09-06: real feature -- lets a user rebuild each data source from the home page instead of
# needing a terminal + the right CLI flags memorized. Every rebuild_* function below calls the
# same real, already-existing functions the CLI scripts use (same convention as
# zone_build_visual_cache further down) -- no reimplemented logic, no subprocess. Runs
# synchronously in the request, same accepted trade-off as that existing route: no job queue for
# a single-user local tool, but --all-zones rebuilds (npc/dialog) genuinely take several minutes,
# not the 10-60s that route's docstring describes -- the "Rebuild" buttons say so.
#
# rebuild_database() deliberately does NOT reuse build_database.main()'s body as-is: that function
# unconditionally deletes the whole db file first (DB_PATH.unlink()), which would wipe out the
# npc/dialog/sql indexes this rebuild has nothing to do with. Calling the individual load_*
# functions directly against the existing connection is safe -- they're all INSERT OR REPLACE
# keyed on real primary keys (zoneid, etc), confirmed idempotent on rerun.
def rebuild_database() -> dict:
    """Thin wrapper over build_database.safe_rebuild() -- the actual DELETE-then-reload logic
    lives there as the single shared implementation both this route and build_database.py's own
    CLI main() call, specifically so they can't diverge again the way they did before (main()
    used to unconditionally delete the whole database file; see safe_rebuild()'s own docstring)."""
    con = get_con()
    build_database.safe_rebuild(con)
    counts = {
        t: con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        for t in ("zones", "door_props", "elevators", "zone_lines", "entities",
                   "items_external", "items_ours", "keyitems_external", "keyitems_ours")
    }
    con.close()
    return counts


def rebuild_npc_index(ffxi_path: str) -> int:
    con = get_con()
    build_npc_index.init_db(con)
    zones_dir = build_npc_index.TOPAZ_ROOT / "scripts/zones"
    if zones_dir.is_dir():
        for zone_dir in sorted(zones_dir.iterdir()):
            if zone_dir.is_dir():
                build_npc_index.process_zone(con, zone_dir.name, ffxi_path, force=False)
    con.commit()
    count = con.execute("SELECT COUNT(*) FROM npc_names").fetchone()[0]
    con.close()
    return count


def rebuild_dialog_index(ffxi_path: str) -> int:
    con = get_con()
    build_dialog_index.init_db(con)
    zones_dir = build_dialog_index.TOPAZ_ROOT / "scripts/zones"
    if zones_dir.is_dir():
        for zone_dir in sorted(zones_dir.iterdir()):
            if (zone_dir / "IDs.lua").exists():
                build_dialog_index.process_zone(con, zone_dir.name, ffxi_path, force=False)
    con.commit()
    count = con.execute("SELECT COUNT(*) FROM dialog_text").fetchone()[0]
    con.close()
    return count


def rebuild_events(ffxi_path: str) -> int:
    """2026-09-06: this bucket lost its rebuild button when door/prop data moved to the bundled
    FFXI-DATS auto-download and key items/missions moved to direct-from-client ingestion -- those
    changes each got their own "Rebuild"/"Install" wiring, but events (the one source that's
    genuinely per-zone, using the same xi-tinkerer-cli.exe as the door-prop and events dat ids)
    never got an equivalent "do all zones" button, so it sat there uninstallable-looking with 0
    rows and no control once the CLI itself was already installed. Runs build_database.py's own
    per-zone loader (load_events_for_zone) against every zone -- same function `--zones all`
    uses on the CLI, just driven from the existing connection instead of main()'s destructive
    DB_PATH.unlink()."""
    if not XI_TINKERER_CLI.exists():
        raise RuntimeError("xi-tinkerer-cli.exe is not installed -- use the Install button first.")
    con = get_con()
    con.executescript(build_database.SCHEMA)
    tmp_dir = TOOLS_ROOT / "mission_reports" / "_events_tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    zoneids = [r[0] for r in con.execute("SELECT zoneid FROM zones")]
    total = 0
    for zoneid in zoneids:
        total += build_database.load_events_for_zone(con, zoneid, ffxi_path, tmp_dir)
    con.commit()
    con.close()
    return total


def rebuild_lsb_index() -> str:
    """LSB is bundled in the repo (D:\\Claude\\mission_toolkit\\LandSandBoat), no download/path
    setting needed -- unlike the other rebuild_* functions above, this never depends on ffxi_path
    or TOPAZ_PATH being configured beyond what settings.py already resolves at import time."""
    con = get_con()
    build_lsb_index.init_db(con)
    build_lsb_index.build_all(con)
    lsb_events = con.execute("SELECT COUNT(*) FROM npc_event_refs WHERE source='lsb'").fetchone()[0]
    topaz_events = con.execute("SELECT COUNT(*) FROM npc_event_refs WHERE source='topaz'").fetchone()[0]
    lsb_items = con.execute("SELECT COUNT(*) FROM lsb_item_basic").fetchone()[0]
    con.close()
    return f"{lsb_items} LSB items, {lsb_events} LSB / {topaz_events} Topaz npc event refs scraped"


def rebuild_dsp_index() -> str:
    """DSP is a real local checkout the user points at via Settings' dsp_server_path (unlike LSB,
    which is bundled), so build_dsp_index's own DSP_ROOT/DSP_SQL_DIR (resolved at import time from
    settings.get_dsp_root()) can be None here -- init_db()/build_all() both degrade gracefully to
    0 rows per table in that case rather than raising, matching every other optional source here."""
    con = get_con()
    build_dsp_index.init_db(con)
    build_dsp_index.build_all(con)
    dsp_events = con.execute("SELECT COUNT(*) FROM npc_event_refs WHERE source='dsp'").fetchone()[0]
    dsp_items = con.execute("SELECT COUNT(*) FROM dsp_item_basic").fetchone()[0]
    con.close()
    return f"{dsp_items} DSP items, {dsp_events} DSP npc event refs scraped"


def rebuild_topaz_index() -> str:
    """Topaz is a real local checkout the user points at via Settings' topaz_server_path (same
    optional-checkout model as DSP) -- build_topaz_index's own TOPAZ_SQL_DIR (resolved at import
    time from settings.get_topaz_root()) can be None here, so init_db()/build_all() both degrade
    gracefully to 0 rows per table in that case rather than raising, matching rebuild_dsp_index()."""
    con = get_con()
    build_topaz_index.init_db(con)
    build_topaz_index.build_all(con)
    topaz_items = con.execute("SELECT COUNT(*) FROM topaz_item_basic").fetchone()[0]
    topaz_npcs = con.execute("SELECT COUNT(*) FROM topaz_npc_list").fetchone()[0]
    con.close()
    return f"{topaz_items} Topaz items, {topaz_npcs} Topaz npcs scraped"


def rebuild_bg_wiki() -> str:
    """Real automated replacement for the "AI model manually pulls the BG Wiki dump" step -- talks
    directly to bg-wiki.com's own MediaWiki API (confirmed live: reachable, robots.txt allows
    api.php). Always runs INCREMENTAL sync here (recentchanges since the dump's own newest known
    edit, typically seconds to a few minutes) rather than a full crawl -- a full from-scratch crawl
    respecting the site's real Crawl-Delay: 30 is ~8 hours for all ~47,600 pages, far too slow for
    a synchronous button click. Run `py -3 scrape_bg_wiki.py --full` by hand for that instead."""
    total, updated = scrape_bg_wiki.run_incremental(limit=None)
    if total == 0:
        raise RuntimeError("No existing BG Wiki dump found -- run `py -3 scrape_bg_wiki.py --full` "
                           "once from a terminal first (this is a long, one-time ~8 hour crawl).")
    return f"{updated} page(s) updated, {total} total in dump"


def rebuild_sql_index() -> int:
    con = get_con()
    build_sql_index.init_db(con)
    build_sql_index.build_all(con)
    con.commit()
    count = con.execute("SELECT COUNT(*) FROM sql_npc_list").fetchone()[0]
    con.close()
    return count


def rebuild_global_tables(ffxi_path: str) -> tuple[int, int]:
    # 2026-09-06: real fix -- these no longer need MassExtractor. Both are DMSGStringBlock dats,
    # pulled directly from the real client the same way dialog/npc already are (dat-extractor +
    # xi_tinkerer, both already in this package) -- confirmed live this session. The old
    # MassExtractor-based ingest_missions()/ingest_key_items() functions are still there as a
    # fallback (real client dat resolution can only fail if dat-extractor itself is missing).
    con = get_con()
    ingest_global_tables.init_db(con)
    missions = ingest_global_tables.ingest_missions_from_client(con, ffxi_path)
    keyitems = ingest_global_tables.ingest_key_items_from_client(con, ffxi_path)
    if not missions:
        missions = ingest_global_tables.ingest_missions(con)
    if not keyitems:
        keyitems = ingest_global_tables.ingest_key_items(con)
    con.commit()
    con.close()
    return missions, keyitems


# Where each optional (not bundled) external data source is expected to land, and where to get
# it if it isn't there -- real repos/tools already confirmed this session, not guessed.
FFXI_DATS_DIR = TOOLS_ROOT / "FFXI-DATS"
XI_TINKERER_CLI = TOOLS_ROOT / "vendor" / "xi-tinkerer" / "target" / "release" / "xi-tinkerer-cli.exe"


def system_status(con: sqlite3.Connection) -> list[dict]:
    """Powers the home page's "Data & Tools" section -- what's actually loaded right now, and
    for anything that's empty because an optional external source isn't bundled, exactly what
    to get and where, rather than a silent 0."""

    def count(table: str) -> int:
        try:
            return con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        except sqlite3.OperationalError:
            return 0

    def count_where(table: str, where: str) -> int:
        try:
            return con.execute(f"SELECT COUNT(*) FROM {table} WHERE {where}").fetchone()[0]
        except sqlite3.OperationalError:
            return 0

    lsb_src_clause = "source='lsb'"
    topaz_src_clause = "source='topaz'"
    dsp_src_clause = "source='dsp'"

    bg_wiki_page_count = 0
    bg_wiki_mtime = ""
    if scrape_bg_wiki.DUMP_PATH.exists():
        import datetime
        with gzip.open(scrape_bg_wiki.DUMP_PATH, "rt", encoding="utf-8") as f:
            bg_wiki_page_count = sum(1 for _ in f)
        bg_wiki_mtime = datetime.datetime.fromtimestamp(
            scrape_bg_wiki.DUMP_PATH.stat().st_mtime
        ).strftime("%Y-%m-%d")

    return [
        {
            "label": "Dialog text",
            "count": count("dialog_text"),
            "detail": f"{count('dialog_text')} entries across zones",
            "rebuild": "dialog",
            "rebuild_note": "reads your FFXI client directly -- takes several minutes for all zones",
            "missing": None,
        },
        {
            "label": "NPC/mob names",
            "count": count("npc_names"),
            "detail": f"{count('npc_names')} entries across zones",
            "rebuild": "npc",
            "rebuild_note": "reads your FFXI client directly -- takes several minutes for all zones",
            "missing": None,
        },
        {
            "label": "Your LSB server's own SQL",
            "count": count("sql_npc_list"),
            "detail": "npc_list, mob_spawn_points, mob_groups, mob_pools, mob_droplist, instance_entities, instance_list",
            "rebuild": "sql",
            "rebuild_note": "reads the bundled LandSandBoat/ checkout's sql/ folder -- usually under a minute",
            "missing": None,
        },
        {
            "label": "Zones & item reference data",
            "count": count("zones"),
            "detail": f"{count('zones')} zones, {count('items_ours')} items (LSB), {count('items_external')} items (external reference)",
            "rebuild": "database",
            "rebuild_note": "reads your FFXI client + the bundled LandSandBoat/ checkout -- usually under a minute",
            "missing": None,
        },
        {
            "label": "Door/prop/elevator positions (all zones)",
            "count": count("door_props") + count("elevators") + count("zone_lines"),
            "detail": (
                f"{count('door_props')} door props, {count('elevators')} elevators, {count('zone_lines')} zone lines"
                if FFXI_DATS_DIR.is_dir()
                else "0 -- not bundled, optional"
            ),
            "rebuild": "database" if FFXI_DATS_DIR.is_dir() else None,
            "rebuild_note": "included in the zone/item data rebuild above once FFXI-DATS is present",
            "missing": None if FFXI_DATS_DIR.is_dir() else {
                "what": "the FFXI-DATS folder (real door/prop/elevator/zone-line positions, every zone)",
                "where_label": "Xenonsmurf/FFXI-DATS on GitHub",
                "where_url": "https://github.com/Xenonsmurf/FFXI-DATS",
                "how": f"~200MB download -- or place it yourself at: {FFXI_DATS_DIR}",
                "install_tool": "ffxi-dats",
            },
        },
        {
            "label": "Assault mission text & key items",
            "count": count("assault_missions") + count("key_items"),
            "detail": f"{count('assault_missions')} missions, {count('key_items')} key items",
            "rebuild": "global",
            "rebuild_note": "reads your FFXI client directly -- usually under a minute",
            "missing": None,
        },
        {
            "label": "Per-zone event data (advanced, optional)",
            "count": count("events"),
            "detail": (
                f"{count('events')} events indexed"
                if XI_TINKERER_CLI.exists()
                else "0 -- optional compiled tool not present"
            ),
            "rebuild": "events" if XI_TINKERER_CLI.exists() else None,
            "rebuild_note": "reads your FFXI client directly, all zones -- slow, several minutes",
            "missing": None if XI_TINKERER_CLI.exists() else {
                "what": "a compiled xi-tinkerer-cli.exe",
                "where_label": "InoUno/xi-tinkerer on GitHub",
                "where_url": "https://github.com/InoUno/xi-tinkerer",
                "how": f"real prebuilt Windows exe, no build needed -- or place it yourself at: {XI_TINKERER_CLI}",
                "install_tool": "xi-tinkerer-cli",
            },
        },
        {
            "label": "LandSandBoat cross-reference (real 3rd id source)",
            "count": count("lsb_item_basic"),
            "detail": (
                f"{count('lsb_item_basic')} LSB items, {count('lsb_npc_list')} LSB npcs, "
                f"{count('lsb_mob_groups')} LSB mob groups -- "
                f"{count_where('npc_event_refs', lsb_src_clause)} LSB / "
                f"{count_where('npc_event_refs', topaz_src_clause)} Topaz npc event(csid) refs scraped"
            ),
            "rebuild": "lsb" if build_lsb_index.LSB_ROOT.is_dir() else None,
            "rebuild_note": "parses the bundled LandSandBoat/ checkout + scrapes real csid literals from both LSB's and your Topaz server's own npc scripts -- usually under a minute",
            "missing": None if build_lsb_index.LSB_ROOT.is_dir() else {
                "what": "the LandSandBoat/server checkout (real backport source, needed for all LSB-vs-Topaz id drift checks)",
                "where_label": "LandSandBoat/server on GitHub",
                "where_url": "https://github.com/LandSandBoat/server",
                "how": "~180MB download -- or place it yourself at: " + str(build_lsb_index.LSB_ROOT),
                "install_tool": "landsandboat-full",
            },
        },
        {
            "label": "Old-DSP cross-reference (real 4th id source, optional)",
            "count": count("dsp_item_basic"),
            "detail": (
                f"{count('dsp_item_basic')} DSP items, {count('dsp_npc_list')} DSP npcs, "
                f"{count('dsp_mob_groups')} DSP mob groups -- "
                f"{count_where('npc_event_refs', dsp_src_clause)} DSP npc event(csid) refs scraped"
                if build_dsp_index.DSP_SQL_DIR else "not configured -- optional"
            ),
            "rebuild": "dsp" if build_dsp_index.DSP_SQL_DIR else None,
            "rebuild_note": "parses your configured old-DSP checkout's sql/ + scrapes real csid literals from its npc scripts -- usually under a minute",
            "missing": None if build_dsp_index.DSP_SQL_DIR else {
                "what": "an old-DSP (DarkStar-lineage) server checkout -- a real pre-existing local checkout, not something this toolkit downloads",
                "where_label": "set its path in Settings",
                "where_url": "/settings",
                "how": "enter the checkout's root folder (the one containing sql/, scripts/, src/) in Settings' Paths section, then Save + Restart",
                "install_tool": None,
            },
        },
        {
            "label": "Your Topaz server's own SQL (backport module, optional)",
            "count": count("topaz_item_basic"),
            "detail": (
                f"{count('topaz_item_basic')} Topaz items, {count('topaz_npc_list')} Topaz npcs, "
                f"{count('topaz_mob_groups')} Topaz mob groups"
                if build_topaz_index.TOPAZ_SQL_DIR else "not configured -- optional"
            ),
            "rebuild": "topaz" if build_topaz_index.TOPAZ_SQL_DIR else None,
            "rebuild_note": "parses your configured Topaz server's sql/ folder -- usually under a minute",
            "missing": None if build_topaz_index.TOPAZ_SQL_DIR else {
                "what": "a Topaz server checkout -- only needed for the backport/ID Drift module",
                "where_label": "set its path in Settings",
                "where_url": "/settings",
                "how": "enter the checkout's root folder (the one containing conf/map.conf, sql/, scripts/) in Settings' Paths section, then Save + Restart",
                "install_tool": None,
            },
        },
        {
            "label": "BG Wiki dump (real page content, item/npc/quest lookups)",
            "count": bg_wiki_page_count,
            "detail": (
                f"{bg_wiki_page_count} pages, last synced {bg_wiki_mtime}"
                if bg_wiki_page_count else "not downloaded yet"
            ),
            "rebuild": "bgwiki" if bg_wiki_page_count else None,
            "rebuild_note": "incremental sync against bg-wiki.com's own API (only pages changed since the last sync) -- usually seconds to a few minutes",
            "missing": None if bg_wiki_page_count else {
                "what": "the BG Wiki dump (vendor/ffxi-wiki-dumps-dist/bg-wiki.jsonl.gz)",
                "where_label": "bg-wiki.com (fetched live via its own API)",
                "where_url": "https://www.bg-wiki.com/",
                "how": (
                    "installs a real, already-scraped dump packaged as a local addon -- instant, "
                    "not a live crawl"
                    if (TOOLS_ROOT / "addons" / "bg-wiki-dump.zip").exists() else
                    "run `py -3 scrape_bg_wiki.py --full` once from a terminal -- a real, one-time "
                    "~8 hour crawl (respects the site's own Crawl-Delay: 30), not something to "
                    "trigger from this button. If another install of this toolkit already has the "
                    "dump, `py -3 addon_tools.py package bg-wiki-dump "
                    "vendor/ffxi-wiki-dumps-dist/bg-wiki.jsonl.gz` there packages it for this button "
                    "instead of re-crawling."
                ),
                "install_tool": (
                    "addon-bg-wiki-dump"
                    if (TOOLS_ROOT / "addons" / "bg-wiki-dump.zip").exists() else None
                ),
            },
        },
        {
            "label": "Captures (your own recorded gameplay)",
            "count": count("captures"),
            "detail": f"{count('captures')} capture bundle(s) ingested" if count("captures") else "none yet -- this is your own data, not something to download",
            "rebuild": None,
            "rebuild_note": None,
            "missing": {
                "what": "your own NPCLogger/Captain (or idview/Wiggo) capture bundles",
                "where_label": None,
                "where_url": None,
                "how": "use the Captures page's \"Add a capture\" form to point at a folder or .zip on your own machine",
            } if not count("captures") else None,
        },
    ]


def current_theme() -> str:
    con = get_con()
    try:
        return settings_mod.get(con, "theme") or "light"
    finally:
        con.close()


templates.env.globals["current_theme"] = current_theme


def backport_enabled() -> bool:
    """Module boundary from CORE_AGNOSTIC_DESIGN.md: the backport module (ID Drift, and any future
    Topaz/DSP-vs-LSB browse page) is gated by whether the user has a real Topaz or DSP checkout
    configured at all -- same "optional, tell us if you have it" pattern build_dsp_index.py already
    used for DSP alone, extended to cover the whole module. Checked against the resolved root
    actually existing on disk (get_topaz_root() always returns a path -- it has a real default,
    C:/topaz, even when topaz_server_path is unset -- so testing the setting string alone would
    read as "enabled" for a user who never configured anything and doesn't have C:/topaz either)."""
    topaz_root = settings_mod.get_topaz_root()
    dsp_root = settings_mod.get_dsp_root()
    return (topaz_root / "sql").is_dir() or (dsp_root is not None and (dsp_root / "sql").is_dir())


templates.env.globals["backport_enabled"] = backport_enabled


@app.get("/help", response_class=HTMLResponse)
def help_page(request: Request):
    return templates.TemplateResponse(request, "help.html", {})


@app.get("/roadmap", response_class=HTMLResponse)
def roadmap_page(request: Request):
    """Static status/roadmap page -- mirrors the 'Mission Toolkit GUI' status-report artifact
    (published externally for sharing) so the same content lives inside the running app too,
    not only on claude.ai. Content is plain HTML in the template, not database-driven, since it's
    a narrative history/plan document rather than live data."""
    return templates.TemplateResponse(request, "roadmap.html", {})


@app.get("/", response_class=HTMLResponse)
def home(request: Request, rebuilt: str = "", ok: int = 1, detail: str = ""):
    con = get_con()
    stats = {
        "dialog_entries": con.execute("SELECT COUNT(*) FROM dialog_text").fetchone()[0],
        "dialog_zones": con.execute("SELECT COUNT(DISTINCT zoneid) FROM dialog_text").fetchone()[0],
        "npc_entries": con.execute("SELECT COUNT(*) FROM npc_names").fetchone()[0],
        "npc_zones": con.execute("SELECT COUNT(DISTINCT zoneid) FROM npc_names").fetchone()[0],
        "missions": con.execute("SELECT COUNT(*) FROM assault_missions").fetchone()[0],
        "keyitems": con.execute("SELECT COUNT(*) FROM key_items").fetchone()[0],
        "sql_npc_list": con.execute("SELECT COUNT(*) FROM sql_npc_list").fetchone()[0],
        "drift_mismatches": con.execute(
            "SELECT COUNT(*) FROM dialog_drift_report WHERE status='mismatch'"
        ).fetchone()[0],
    }
    status = system_status(con)
    zones = con.execute("SELECT zoneid, name FROM zones WHERE zoneid > 0 ORDER BY name").fetchall()
    con.close()
    return templates.TemplateResponse(request, "home.html", {
        "stats": stats, "zones": zones, "status": status,
        "rebuilt": rebuilt, "rebuilt_ok": bool(ok), "rebuilt_detail": detail,
    })


REBUILDABLE_SOURCES = {"dialog", "npc", "sql", "database", "global", "events", "lsb", "dsp", "topaz", "bgwiki"}


@app.get("/rebuild/{source}/confirm", response_class=HTMLResponse)
def rebuild_source_confirm(request: Request, source: str):
    """Confirm page for a Rebuild click -- same explicit-second-step pattern as
    /captures/{id}/delete and /backup/restore/{name}/confirm, rather than a single click gated
    only by a JS confirm() dialog. Rebuilds are far less destructive than a restore (a real
    automatic backup is taken first, and safe_rebuild() never touches another module's tables --
    see its own docstring), but the user asked for the same real confirm-page treatment here too,
    not just the (easily-missed, easy-to-reflexively-accept) browser confirm() popup."""
    if source not in REBUILDABLE_SOURCES:
        return RedirectResponse(url="/")
    con = get_con()
    row = next((s for s in system_status(con) if s["rebuild"] == source), None)
    con.close()
    if row is None:
        return RedirectResponse(url="/")
    return templates.TemplateResponse(request, "rebuild_confirm.html", {"source": source, "row": row})


@app.post("/rebuild/{source}")
def rebuild_source(source: str):
    """Triggers one of the rebuild_* functions above from a home-page button. Synchronous --
    see rebuild_database()'s own comment for why (matches this app's one existing precedent,
    zone_build_visual_cache, just longer-running for the --all-zones cases)."""
    if source not in REBUILDABLE_SOURCES:
        return RedirectResponse(url="/?rebuilt=&ok=0&detail=Unknown+source", status_code=303)

    build_database.backup_database_file(min_interval_seconds=300)
    ffxi_path = settings_mod.get_ffxi_install()
    try:
        if source == "dialog":
            if not ffxi_path:
                raise RuntimeError("Could not find your FFXI install -- set it in Settings first.")
            n = rebuild_dialog_index(ffxi_path)
            detail = f"{n} dialog entries indexed"
        elif source == "npc":
            if not ffxi_path:
                raise RuntimeError("Could not find your FFXI install -- set it in Settings first.")
            n = rebuild_npc_index(ffxi_path)
            detail = f"{n} NPC/mob names indexed"
        elif source == "sql":
            n = rebuild_sql_index()
            detail = f"{n} npc_list rows indexed"
        elif source == "database":
            counts = rebuild_database()
            detail = ", ".join(f"{v} {k}" for k, v in counts.items())
        elif source == "global":
            if not ffxi_path:
                raise RuntimeError("Could not find your FFXI install -- set it in Settings first.")
            missions, keyitems = rebuild_global_tables(ffxi_path)
            detail = f"{missions} missions, {keyitems} key items"
        elif source == "events":
            if not ffxi_path:
                raise RuntimeError("Could not find your FFXI install -- set it in Settings first.")
            n = rebuild_events(ffxi_path)
            detail = f"{n} events indexed across all zones (this can take several minutes)"
        elif source == "lsb":
            detail = rebuild_lsb_index()
        elif source == "dsp":
            detail = rebuild_dsp_index()
        elif source == "topaz":
            detail = rebuild_topaz_index()
        elif source == "bgwiki":
            detail = rebuild_bg_wiki()
    except Exception as e:
        from urllib.parse import quote
        return RedirectResponse(url=f"/?rebuilt={source}&ok=0&detail={quote(str(e))}", status_code=303)

    from urllib.parse import quote
    return RedirectResponse(url=f"/?rebuilt={source}&ok=1&detail={quote(detail)}", status_code=303)


ADDON_PREFIX = "addon-"


@app.post("/install/{tool}")
def install_tool(tool: str):
    """Auto-downloads one of the optional external tools/data straight from its real GitHub
    source (install_external_tools.py) instead of the user needing to find, download, and place
    it by hand. Same synchronous-request pattern as /rebuild/{source} above -- FFXI-DATS is a
    real ~200MB download, so this button can take a minute or so.

    A tool name starting with "addon-" (e.g. "addon-bg-wiki-dump") is routed to addon_tools.py's
    own install_addon() instead -- a LOCAL package (see addons/*.zip) rather than a network fetch,
    same real (ok, message) return shape so this one route can drive both without the template/
    button needing to know which kind a given row is."""
    from urllib.parse import quote
    if tool.startswith(ADDON_PREFIX):
        ok, message = addon_tools.install_addon(tool[len(ADDON_PREFIX):])
    elif tool in install_external_tools.INSTALLERS:
        ok, message = install_external_tools.INSTALLERS[tool]()
    else:
        return RedirectResponse(url="/?rebuilt=&ok=0&detail=Unknown+tool", status_code=303)
    return RedirectResponse(url=f"/?rebuilt={tool}&ok={1 if ok else 0}&detail={quote(message)}", status_code=303)


ITEMS_PAGE_SIZE = 50


def _external_item_by_id(ext_id: int) -> dict | None:
    """Reads the one matching record out of FFXI-Resources-dist's items.ndjson.gz -- the full
    real description/type/flags data items_external's own table doesn't store (it only kept
    id/name/norm_name, see build_database.py's load_items_external). Read live rather than
    re-indexed into SQL: this is a single-item detail lookup, not a bulk query, same "read the
    real source live" approach lookup_entity.py already uses for SQL rows."""
    path = build_database.FFXI_RESOURCES_DIST / "items.ndjson.gz"
    if not path.exists():
        return None
    import gzip as _gzip
    with _gzip.open(path, "rt", encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            if d.get("id") == ext_id:
                return d
    return None


@app.get("/items", response_class=HTMLResponse)
def items_search(request: Request, q: str = "", status: str = "all", page: int = 1):
    """Compares our own server's items (items_ours + the richer sql_item_basic/equipment/weapon/
    usable tables) against the bundled external reference catalogue (items_external) by
    normalized name -- same real norm_name join build_database.py's own compute_id_drift() uses
    for entities. SQLite has no FULL OUTER JOIN, so this is our-anchored rows UNIONed in Python
    with the external-only rows a LEFT JOIN the other direction reveals."""
    con = get_con()
    page = max(1, page)

    name_params: list = [f"%{q}%", f"%{q}%"] if q else []
    name_clause = "AND (io.name LIKE ? OR ie.name LIKE ?)" if q else ""
    rows = con.execute(f"""
        SELECT io.itemid AS our_id, io.name AS our_name,
               ie.id AS ext_id, ie.name AS ext_name,
               sb.stackSize, sb.flags, sb.BaseSell,
               CASE WHEN se.itemid IS NOT NULL THEN 'equipment'
                    WHEN sw.itemid IS NOT NULL THEN 'weapon'
                    WHEN su.itemid IS NOT NULL THEN 'usable'
                    ELSE 'basic' END AS category
        FROM items_ours io
        LEFT JOIN items_external ie ON ie.norm_name = io.norm_name
        LEFT JOIN sql_item_basic sb ON sb.itemid = io.itemid
        LEFT JOIN sql_item_equipment se ON se.itemid = io.itemid
        LEFT JOIN sql_item_weapon sw ON sw.itemid = io.itemid
        LEFT JOIN sql_item_usable su ON su.itemid = io.itemid
        WHERE 1=1 {name_clause}
        ORDER BY io.itemid
    """, name_params).fetchall()

    ext_params: list = [f"%{q}%"] if q else []
    ext_clause = "AND ie.name LIKE ?" if q else ""
    ext_only_rows = con.execute(f"""
        SELECT ie.id AS ext_id, ie.name AS ext_name
        FROM items_external ie
        LEFT JOIN items_ours io ON io.norm_name = ie.norm_name
        WHERE io.itemid IS NULL {ext_clause}
        ORDER BY ie.id
    """, ext_params).fetchall()
    con.close()

    all_items = []
    for r in rows:
        if r["ext_id"] is None:
            item_status = "ours_only"
        elif r["our_id"] == r["ext_id"]:
            item_status = "matched"
        else:
            item_status = "drift"
        all_items.append({**dict(r), "status": item_status})
    for r in ext_only_rows:
        all_items.append({
            "our_id": None, "our_name": None, "ext_id": r["ext_id"], "ext_name": r["ext_name"],
            "stackSize": None, "flags": None, "BaseSell": None, "category": None,
            "status": "external_only",
        })

    counts = {"all": len(all_items)}
    for s in ("matched", "drift", "ours_only", "external_only"):
        counts[s] = sum(1 for i in all_items if i["status"] == s)

    items = all_items if status == "all" else [i for i in all_items if i["status"] == status]
    total = len(items)
    total_pages = max(1, (total + ITEMS_PAGE_SIZE - 1) // ITEMS_PAGE_SIZE)
    offset = (page - 1) * ITEMS_PAGE_SIZE
    page_items = items[offset:offset + ITEMS_PAGE_SIZE]

    return templates.TemplateResponse(request, "items.html", {
        "q": q, "status": status, "items": page_items,
        "page": page, "total_pages": total_pages, "total": total, "counts": counts,
    })


@app.get("/items/{itemid}", response_class=HTMLResponse)
def item_detail(request: Request, itemid: int):
    con = get_con()
    our_row = con.execute(
        "SELECT itemid, name, norm_name FROM items_ours WHERE itemid = ?", (itemid,)
    ).fetchone()
    basic = con.execute("SELECT * FROM sql_item_basic WHERE itemid = ?", (itemid,)).fetchone()
    equipment = con.execute("SELECT * FROM sql_item_equipment WHERE itemid = ?", (itemid,)).fetchone()
    weapon = con.execute("SELECT * FROM sql_item_weapon WHERE itemid = ?", (itemid,)).fetchone()
    usable = con.execute("SELECT * FROM sql_item_usable WHERE itemid = ?", (itemid,)).fetchone()
    ext_row = None
    topaz_row = None
    if our_row:
        ext_row = con.execute(
            "SELECT id, name FROM items_external WHERE norm_name = ?", (our_row["norm_name"],)
        ).fetchone()
        # 2026-09-08: this used to be a "LandSandBoat (backport source)" panel querying
        # lsb_item_basic, distinct from "our server" (items_ours) back when items_ours meant
        # Topaz. Since items_ours now means LSB itself (see build_database.py's LSB_ROOT rework),
        # that panel had collapsed into showing the same LSB data twice under two different
        # labels, and its "id drift: LSB uses X, we use Y" line was comparing LSB against itself.
        # The genuinely useful second comparison now is Topaz (the real backport source), only
        # queried/shown when the backport module is actually relevant -- same gating
        # backport_enabled() already applies to ID Drift and the Keyitems page's Topaz section.
        if backport_enabled():
            topaz_row = con.execute(
                "SELECT itemid, name FROM topaz_item_basic WHERE norm_name = ?", (our_row["norm_name"],)
            ).fetchone()
    con.close()

    external_detail = _external_item_by_id(ext_row["id"]) if ext_row else None

    return templates.TemplateResponse(request, "item_detail.html", {
        "itemid": itemid, "our_row": our_row, "basic": basic, "equipment": equipment,
        "weapon": weapon, "usable": usable, "ext_row": ext_row, "external_detail": external_detail,
        "topaz_row": topaz_row,
    })


def _iddrift_events(con, q):
    params = [f"%{q}%", f"%{q}%"] if q else []
    clause = "AND (l.zone_name LIKE ? OR l.npc_script LIKE ?)" if q else ""
    return con.execute(f"""
        SELECT l.zone_name, l.npc_script, l.csid AS lsb_csid, t.csid AS topaz_csid
        FROM npc_event_refs l
        JOIN npc_event_refs t ON t.source='topaz' AND t.zone_name=l.zone_name AND t.npc_script=l.npc_script
        WHERE l.source='lsb' AND l.csid != t.csid {clause}
        ORDER BY l.zone_name, l.npc_script
    """, params).fetchall()


def _iddrift_not_backported(con, q):
    params = [f"%{q}%", f"%{q}%"] if q else []
    clause = "AND (l.zone_name LIKE ? OR l.npc_script LIKE ?)" if q else ""
    return con.execute(f"""
        SELECT DISTINCT l.zone_name, l.npc_script FROM npc_event_refs l
        WHERE l.source='lsb' AND NOT EXISTS (
            SELECT 1 FROM npc_event_refs t WHERE t.source='topaz' AND t.zone_name=l.zone_name AND t.npc_script=l.npc_script
        ) {clause}
        ORDER BY l.zone_name, l.npc_script
    """, params).fetchall()


def _iddrift_items(con, q):
    # 3-way, LSB anchored: several real names are shared by many distinct items (e.g. "linkshell"
    # x16, one per rank) -- a plain name-equality join cross-products every same-name pair on both
    # sides into pure noise. Ranking each side by id within its own name group and joining
    # same-rank-to-same-rank pairs the two sequences up positionally instead, which is how a
    # backport actually maps them.
    # "Our"/backport side is topaz_item_basic, not items_ours -- since the LSB-primary rework,
    # items_ours IS the LSB catalog (repointed in build_database.py), so joining it here would
    # just compare LSB against itself. topaz_item_basic (build_topaz_index.py) is the real Topaz
    # side of this specific comparison.
    params = [f"%{q}%"] if q else []
    clause = "AND l.name LIKE ?" if q else ""
    return con.execute(f"""
        WITH l AS (
            SELECT itemid, name, norm_name,
                   ROW_NUMBER() OVER (PARTITION BY norm_name ORDER BY itemid) AS rn
            FROM lsb_item_basic
        ),
        o AS (
            SELECT itemid, name, norm_name,
                   ROW_NUMBER() OVER (PARTITION BY norm_name ORDER BY itemid) AS rn
            FROM topaz_item_basic
        ),
        e AS (
            SELECT id, name, norm_name,
                   ROW_NUMBER() OVER (PARTITION BY norm_name ORDER BY id) AS rn
            FROM items_external
        )
        SELECT l.itemid AS lsb_id, l.name AS lsb_name,
               o.itemid AS our_id, o.name AS our_name,
               e.id AS ext_id, e.name AS ext_name
        FROM l
        JOIN o ON o.norm_name = l.norm_name AND o.rn = l.rn
        LEFT JOIN e ON e.norm_name = l.norm_name AND e.rn = l.rn
        WHERE l.itemid != o.itemid {clause}
        ORDER BY l.itemid
    """, params).fetchall()


def _iddrift_keyitems(con, q):
    # Same rank-pairing shape as _iddrift_items, but a direct 2-way Topaz-vs-LSB backport
    # comparison (topaz_keyitems vs keyitems_ours), NOT a 3-way join against keyitems_external --
    # this is specifically about the user's own Topaz backport's readiness against the LSB
    # baseline, not retail-id drift (that's what the Keyitems page's per-row readiness check is
    # already for, via ingest_global_tables.resolve_keyitem_readiness()).
    params = [f"%{q}%"] if q else []
    clause = "AND l.const_name LIKE ?" if q else ""
    return con.execute(f"""
        WITH l AS (
            SELECT id, const_name, norm_name,
                   ROW_NUMBER() OVER (PARTITION BY norm_name ORDER BY id) AS rn
            FROM keyitems_ours
        ),
        t AS (
            SELECT id, const_name, norm_name,
                   ROW_NUMBER() OVER (PARTITION BY norm_name ORDER BY id) AS rn
            FROM topaz_keyitems
        )
        SELECT l.const_name AS lsb_name, l.id AS lsb_id, t.id AS our_id, t.const_name AS our_name
        FROM l JOIN t ON t.norm_name = l.norm_name AND t.rn = l.rn
        WHERE l.id != t.id {clause}
        ORDER BY l.id
    """, params).fetchall()


def _iddrift_npcs(con, q, zoneid=None):
    # Same zone (derived from npcid the same way for both -- neither table has an explicit zoneid
    # column) + same normalized name, different literal npcid. Same rank-pairing fix as items.
    params = [f"%{q}%"] if q else []
    clause = "AND l.name LIKE ?" if q else ""
    if zoneid is not None:
        clause += " AND l.zoneid = ?"
        params.append(zoneid)
    return con.execute(f"""
        WITH l AS (
            SELECT npcid, name, zoneid,
                   ROW_NUMBER() OVER (PARTITION BY zoneid, name ORDER BY npcid) AS rn
            FROM lsb_npc_list
        ),
        t AS (
            SELECT npcid, name, zoneid,
                   ROW_NUMBER() OVER (PARTITION BY zoneid, name ORDER BY npcid) AS rn
            FROM topaz_npc_list
        )
        SELECT l.zoneid, l.npcid AS lsb_id, l.name AS lsb_name, t.npcid AS our_id, t.name AS our_name
        FROM l JOIN t ON t.zoneid = l.zoneid AND t.name = l.name AND t.rn = l.rn
        WHERE l.npcid != t.npcid {clause}
        ORDER BY l.zoneid, l.name
    """, params).fetchall()


def _iddrift_npc_zone_offsets(npc_rows):
    """A known real bug class (see topaz_npc_list_offset_regions memory): a whole zone's npc ids
    can be shifted by one constant amount block-wide, rather than drifting per-entity -- that
    shows up as dozens of individual npc-drift rows all sharing the same (lsb_id - our_id) delta.
    Detected here (not guessed) straight from the real rows just queried: if one delta covers most
    of a zone's mismatches, it's a block offset worth calling out on its own instead of making the
    reader notice the pattern across dozens of rows."""
    from collections import Counter
    zone_deltas: dict[int, Counter] = {}
    for r in npc_rows:
        zone_deltas.setdefault(r["zoneid"], Counter())[r["lsb_id"] - r["our_id"]] += 1
    summary = []
    for zoneid, counter in sorted(zone_deltas.items()):
        delta, hits = counter.most_common(1)[0]
        total = sum(counter.values())
        if hits >= 3 and hits >= total * 0.6:
            summary.append({"zoneid": zoneid, "delta": delta, "hits": hits, "total": total})
    return summary


def _iddrift_mobgroups(con, q, zoneid=None):
    params = [f"%{q}%"] if q else []
    clause = "AND l.name LIKE ?" if q else ""
    if zoneid is not None:
        clause += " AND l.zoneid = ?"
        params.append(zoneid)
    return con.execute(f"""
        WITH l AS (
            SELECT zoneid, groupid, poolid, name,
                   ROW_NUMBER() OVER (PARTITION BY zoneid, name ORDER BY groupid) AS rn
            FROM lsb_mob_groups
        ),
        t AS (
            SELECT zoneid, groupid, poolid, name,
                   ROW_NUMBER() OVER (PARTITION BY zoneid, name ORDER BY groupid) AS rn
            FROM topaz_mob_groups
        )
        SELECT l.zoneid, l.groupid AS lsb_groupid, l.poolid AS lsb_poolid, l.name AS lsb_name,
               t.groupid AS our_groupid, t.poolid AS our_poolid, t.name AS our_name
        FROM l JOIN t ON t.zoneid = l.zoneid AND t.name = l.name AND t.rn = l.rn
        WHERE (l.groupid != t.groupid OR l.poolid != t.poolid) {clause}
        ORDER BY l.zoneid, l.name
    """, params).fetchall()


def _iddrift_mobskills(con, q):
    # Topaz and LSB each hand-add mob skills independently (confirmed: LSB's "combo" is id 1,
    # Topaz's is id 3413), so a same-name mismatch here is real, not noise.
    params = [f"%{q}%"] if q else []
    clause = "AND l.name LIKE ?" if q else ""
    return con.execute(f"""
        WITH l AS (
            SELECT mob_skill_id, name, ROW_NUMBER() OVER (PARTITION BY name ORDER BY mob_skill_id) AS rn
            FROM lsb_mob_skills
        ),
        t AS (
            SELECT mob_skill_id, name, ROW_NUMBER() OVER (PARTITION BY name ORDER BY mob_skill_id) AS rn
            FROM topaz_mob_skills
        )
        SELECT l.mob_skill_id AS lsb_id, l.name AS lsb_name, t.mob_skill_id AS our_id, t.name AS our_name
        FROM l JOIN t ON t.name = l.name AND t.rn = l.rn
        WHERE l.mob_skill_id != t.mob_skill_id {clause}
        ORDER BY l.name
    """, params).fetchall()


def _iddrift_spells(con, q):
    # Real spell ids are the client's own canonical resource ids, so this should almost always be
    # empty; any hit here is a genuine, surprising mismatch worth flagging.
    params = [f"%{q}%"] if q else []
    clause = "AND l.name LIKE ?" if q else ""
    return con.execute(f"""
        SELECT l.spellid AS lsb_id, l.name AS lsb_name, t.spellid AS our_id, t.name AS our_name
        FROM lsb_spell_list l
        JOIN topaz_spell_list t ON t.name = l.name
        WHERE l.spellid != t.spellid {clause}
        ORDER BY l.name
    """, params).fetchall()


def _iddrift_abilities(con, q):
    params = [f"%{q}%"] if q else []
    clause = "AND l.name LIKE ?" if q else ""
    return con.execute(f"""
        SELECT l.abilityId AS lsb_id, l.name AS lsb_name, t.abilityId AS our_id, t.name AS our_name
        FROM lsb_abilities l
        JOIN topaz_abilities t ON t.name = l.name
        WHERE l.abilityId != t.abilityId {clause}
        ORDER BY l.name
    """, params).fetchall()


def _iddrift_weaponskills(con, q):
    params = [f"%{q}%"] if q else []
    clause = "AND l.name LIKE ?" if q else ""
    return con.execute(f"""
        SELECT l.weaponskillid AS lsb_id, l.name AS lsb_name, t.weaponskillid AS our_id, t.name AS our_name
        FROM lsb_weapon_skills l
        JOIN topaz_weapon_skills t ON t.name = l.name
        WHERE l.weaponskillid != t.weaponskillid {clause}
        ORDER BY l.name
    """, params).fetchall()


def _iddrift_traits(con, q):
    params = [f"%{q}%"] if q else []
    clause = "AND l.name LIKE ?" if q else ""
    return con.execute(f"""
        SELECT l.traitid AS lsb_id, l.name AS lsb_name, t.traitid AS our_id, t.name AS our_name
        FROM lsb_traits l
        JOIN topaz_traits t ON t.name = l.name
        WHERE l.traitid != t.traitid {clause}
        ORDER BY l.name
    """, params).fetchall()


def _iddrift_blu(con, q):
    # Association check, not name-based: same real spellid on both sides (BLU spells share the
    # normal client spell id space), but does it copy the same mob ability?
    params = [f"%{q}%"] if q else []
    clause = "AND sl.name LIKE ?" if q else ""
    return con.execute(f"""
        SELECT l.spellid, sl.name AS spell_name, l.mob_skill_id AS lsb_mob_skill_id,
               t.mob_skill_id AS our_mob_skill_id
        FROM lsb_blue_spell_list l
        JOIN topaz_blue_spell_list t ON t.spellid = l.spellid
        LEFT JOIN lsb_spell_list sl ON sl.spellid = l.spellid
        WHERE l.mob_skill_id != t.mob_skill_id {clause}
        ORDER BY l.spellid
    """, params).fetchall()


def _iddrift_pets(con, q):
    params = [f"%{q}%"] if q else []
    clause = "AND l.name LIKE ?" if q else ""
    return con.execute(f"""
        WITH l AS (
            SELECT petid, name, ROW_NUMBER() OVER (PARTITION BY name ORDER BY petid) AS rn
            FROM lsb_pet_list
        ),
        t AS (
            SELECT petid, name, ROW_NUMBER() OVER (PARTITION BY name ORDER BY petid) AS rn
            FROM topaz_pet_list
        )
        SELECT l.petid AS lsb_id, l.name AS lsb_name, t.petid AS our_id, t.name AS our_name
        FROM l JOIN t ON t.name = l.name AND t.rn = l.rn
        WHERE l.petid != t.petid {clause}
        ORDER BY l.name
    """, params).fetchall()


def _iddrift_effects(con, q):
    # "none"/placeholder slot names excluded: both sides reuse that exact name for several
    # unrelated unused ids, which would otherwise show as false drift.
    params = [f"%{q}%"] if q else []
    clause = "AND l.name LIKE ?" if q else ""
    return con.execute(f"""
        SELECT l.effectid AS lsb_id, l.name AS lsb_name, t.effectid AS our_id, t.name AS our_name
        FROM lsb_effects l
        JOIN topaz_effects t ON t.norm_name = l.norm_name
        WHERE l.effectid != t.effectid AND l.name != 'none' {clause}
        ORDER BY l.effectid
    """, params).fetchall()


def _iddrift_effects_gap(con, q):
    params = [f"%{q}%"] if q else []
    clause = "AND l.name LIKE ?" if q else ""
    return con.execute(f"""
        SELECT l.effectid, l.name FROM lsb_effects l
        WHERE l.name != 'none' AND NOT EXISTS (
            SELECT 1 FROM topaz_effects t WHERE t.norm_name = l.norm_name
        ) {clause}
        ORDER BY l.effectid
    """, params).fetchall()


def _iddrift_items_count(con, q):
    # Every id-drift category above only ever compares entries that exist on BOTH sides of a
    # same-name group -- if LSB has 3 "linkshell"-family items and Topaz has 2, only 2 pairs get
    # compared and the 3rd is invisible to the drift check entirely. This surfaces that gap
    # directly: real count mismatches per normalized name, independent of whether any id drifted.
    # Restricted to names present on BOTH sides -- a name only one side has at all (Topaz simply
    # hasn't implemented an LSB item yet, or vice versa) isn't a "count mismatch," it's the much
    # more common "not backported"/"LSB doesn't have this" case and would otherwise drown this
    # section in tens of thousands of expected, not-a-bug rows (confirmed live: unfiltered this
    # produced 19700+ hits, almost all zero-on-one-side noise).
    params = [f"%{q}%"] if q else []
    clause = "AND norm_name LIKE ?" if q else ""
    rows = con.execute(f"""
        SELECT norm_name, MIN(name) AS name, COUNT(*) AS cnt FROM lsb_item_basic
        WHERE 1=1 {clause} GROUP BY norm_name
    """, params).fetchall()
    lsb_counts = {r["norm_name"]: (r["name"], r["cnt"]) for r in rows}
    # our_counts is topaz_item_basic, not items_ours -- see _iddrift_items' comment: items_ours
    # is LSB's own catalog post-rework, so comparing it here would be LSB-vs-LSB.
    our_counts = dict(con.execute("SELECT norm_name, COUNT(*) FROM topaz_item_basic GROUP BY norm_name").fetchall())
    out = []
    for norm_name, (name, lsb_cnt) in lsb_counts.items():
        our_cnt = our_counts.get(norm_name, 0)
        if our_cnt > 0 and our_cnt != lsb_cnt:
            out.append({"name": name, "lsb_count": lsb_cnt, "our_count": our_cnt})
    out.sort(key=lambda r: r["name"])
    return out


def _iddrift_keyitems_count(con, q):
    # Same both-sides-present restriction as items -- see _iddrift_items_count's comment.
    params = [f"%{q}%"] if q else []
    clause = "AND norm_name LIKE ?" if q else ""
    rows = con.execute(f"""
        SELECT norm_name, MIN(const_name) AS name, COUNT(*) AS cnt FROM keyitems_ours
        WHERE 1=1 {clause} GROUP BY norm_name
    """, params).fetchall()
    lsb_counts = {r["norm_name"]: (r["name"], r["cnt"]) for r in rows}
    our_counts = dict(con.execute("SELECT norm_name, COUNT(*) FROM topaz_keyitems GROUP BY norm_name").fetchall())
    out = []
    for norm_name, (name, lsb_cnt) in lsb_counts.items():
        our_cnt = our_counts.get(norm_name, 0)
        if our_cnt > 0 and our_cnt != lsb_cnt:
            out.append({"name": name, "lsb_count": lsb_cnt, "our_count": our_cnt})
    out.sort(key=lambda r: r["name"])
    return out


def _iddrift_npcs_count(con, q, zoneid=None):
    # Same both-sides-present restriction as items -- see that function's comment.
    params = [f"%{q}%"] if q else []
    clause = "AND name LIKE ?" if q else ""
    if zoneid is not None:
        clause += " AND zoneid = ?"
        params.append(zoneid)
    lsb_rows = con.execute(f"""
        SELECT zoneid, name, COUNT(*) AS cnt FROM lsb_npc_list WHERE 1=1 {clause} GROUP BY zoneid, name
    """, params).fetchall()
    our_rows = con.execute(f"""
        SELECT zoneid, name, COUNT(*) AS cnt FROM topaz_npc_list
        WHERE 1=1 {clause} GROUP BY zoneid, name
    """, params).fetchall()
    our_counts = {(r["zoneid"], r["name"]): r["cnt"] for r in our_rows}
    out = []
    for r in lsb_rows:
        key = (r["zoneid"], r["name"])
        our_cnt = our_counts.get(key, 0)
        if our_cnt > 0 and our_cnt != r["cnt"]:
            out.append({"zoneid": r["zoneid"], "name": r["name"], "lsb_count": r["cnt"], "our_count": our_cnt})
    out.sort(key=lambda r: (r["zoneid"], r["name"]))
    return out


def _iddrift_mobgroups_count(con, q, zoneid=None):
    # Same both-sides-present restriction as items -- see that function's comment.
    params = [f"%{q}%"] if q else []
    clause = "AND name LIKE ?" if q else ""
    if zoneid is not None:
        clause += " AND zoneid = ?"
        params.append(zoneid)
    lsb_rows = con.execute(f"""
        SELECT zoneid, name, COUNT(*) AS cnt FROM lsb_mob_groups WHERE 1=1 {clause} GROUP BY zoneid, name
    """, params).fetchall()
    our_rows = con.execute(f"""
        SELECT zoneid, name, COUNT(*) AS cnt FROM topaz_mob_groups WHERE 1=1 {clause} GROUP BY zoneid, name
    """, params).fetchall()
    our_counts = {(r["zoneid"], r["name"]): r["cnt"] for r in our_rows}
    out = []
    for r in lsb_rows:
        key = (r["zoneid"], r["name"])
        our_cnt = our_counts.get(key, 0)
        if our_cnt > 0 and our_cnt != r["cnt"]:
            out.append({"zoneid": r["zoneid"], "name": r["name"], "lsb_count": r["cnt"], "our_count": our_cnt})
    out.sort(key=lambda r: (r["zoneid"], r["name"]))
    return out


def _iddrift_pets_count(con, q):
    # Same both-sides-present restriction as items -- see that function's comment.
    params = [f"%{q}%"] if q else []
    clause = "AND name LIKE ?" if q else ""
    lsb_counts = dict(con.execute(
        f"SELECT name, COUNT(*) FROM lsb_pet_list WHERE 1=1 {clause} GROUP BY name", params
    ).fetchall())
    our_counts = dict(con.execute(
        f"SELECT name, COUNT(*) FROM topaz_pet_list WHERE 1=1 {clause} GROUP BY name", params
    ).fetchall())
    out = []
    for name in set(lsb_counts) & set(our_counts):
        lsb_cnt, our_cnt = lsb_counts[name], our_counts[name]
        if lsb_cnt != our_cnt:
            out.append({"name": name, "lsb_count": lsb_cnt, "our_count": our_cnt})
    out.sort(key=lambda r: r["name"])
    return out


def _iddrift_npc_zone_blocks(con, q, zoneid=None):
    """Per-zone id-range overview (not a mismatch list) -- lets you visually confirm each zone's
    npc id block sits where you'd expect and doesn't overlap a neighboring zone's block, per the
    user's own framing ("any out of boundary ranges 'should' not interfere with other zones... but
    we can see"). Flags a zone whose Topaz range overlaps the very next zoneid's Topaz range --
    real overlap, not guessed, computed directly from the two MIN/MAX queries below."""
    effective_zoneid = zoneid if zoneid is not None else (int(q) if q and q.isdigit() else None)
    clause = "AND zoneid = ?" if effective_zoneid is not None else ""
    filter_params = [effective_zoneid] if effective_zoneid is not None else []
    lsb_rows = con.execute(f"""
        SELECT zoneid, COUNT(*) AS cnt, MIN(npcid) AS lo, MAX(npcid) AS hi FROM lsb_npc_list
        WHERE 1=1 {clause} GROUP BY zoneid
    """, filter_params).fetchall()
    our_rows = con.execute(f"""
        SELECT zoneid, COUNT(*) AS cnt, MIN(npcid) AS lo, MAX(npcid) AS hi
        FROM topaz_npc_list WHERE 1=1 {clause} GROUP BY zoneid
    """, filter_params).fetchall()
    lsb_by_zone = {r["zoneid"]: r for r in lsb_rows}
    our_by_zone = {r["zoneid"]: r for r in our_rows}
    zoneids = sorted(set(lsb_by_zone) | set(our_by_zone))
    out = []
    for i, zoneid in enumerate(zoneids):
        l, t = lsb_by_zone.get(zoneid), our_by_zone.get(zoneid)
        overlaps_next = False
        if t is not None and i + 1 < len(zoneids):
            nxt = our_by_zone.get(zoneids[i + 1])
            if nxt is not None and t["hi"] >= nxt["lo"]:
                overlaps_next = True
        out.append({
            "zoneid": zoneid,
            "lsb_range": f"{l['lo']}-{l['hi']}" if l else "",
            "lsb_count": l["cnt"] if l else 0,
            "our_range": f"{t['lo']}-{t['hi']}" if t else "",
            "our_count": t["cnt"] if t else 0,
            "overlaps_next": overlaps_next,
        })
    return out


# Registry powering both the /iddrift category index and each /iddrift/{slug} detail page --
# one source of truth for label/description/columns/query, so the two pages can't drift apart
# from each other the way the sections themselves used to drift between forks.
IDDRIFT_CATEGORIES = [
    {"slug": "events", "label": "Event / CSID drift", "query": _iddrift_events,
     "description": "Same NPC script file in both LSB and Topaz, but the literal csid it fires differs.",
     "columns": [("zone_name", "Zone"), ("npc_script", "NPC script"), ("lsb_csid", "LSB csid"), ("topaz_csid", "Topaz csid")]},
    {"slug": "not-backported", "label": "Not yet backported", "query": _iddrift_not_backported,
     "description": "LSB npc scripts with no Topaz counterpart at all in the same zone -- not a bug, just content that doesn't exist here yet.",
     "columns": [("zone_name", "Zone"), ("npc_script", "NPC script")]},
    {"slug": "items-count", "label": "Item name-count mismatch", "query": _iddrift_items_count,
     "description": "Same normalized name has a different NUMBER of items on each side (e.g. LSB has 3 in a family, we have 2) -- the extra/missing one is invisible to the id-drift check above, which only ever compares pairs that exist on both sides.",
     "columns": [("name", "Name"), ("lsb_count", "LSB count"), ("our_count", "Our count")]},
    {"slug": "items", "label": "Item id drift", "query": _iddrift_items,
     "description": "Same normalized item name in both LSB and our own item_basic.sql, but a different itemid.",
     "columns": [("lsb_name", "Name"), ("lsb_id", "LSB id"), ("our_id", "Our id"), ("ext_id", "Retail id")],
     "link_col": ("lsb_name", "/items/", "our_id")},
    {"slug": "keyitems-count", "label": "Key item name-count mismatch", "query": _iddrift_keyitems_count,
     "description": "Same normalized key item constant name has a different NUMBER of entries on each side (LSB's key_item.lua vs Topaz's keyitems.lua).",
     "columns": [("name", "Name"), ("lsb_count", "LSB count"), ("our_count", "Our count")]},
    {"slug": "keyitems", "label": "Key item id drift", "query": _iddrift_keyitems,
     "description": "Same normalized key item constant name in both LSB's key_item.lua and Topaz's keyitems.lua, but a different id.",
     "columns": [("lsb_name", "Name"), ("lsb_id", "LSB id"), ("our_id", "Our id")]},
    {"slug": "npcs-count", "label": "NPC name-count mismatch", "query": _iddrift_npcs_count,
     "description": "Same zone + same npc name has a different NUMBER of entries on each side -- the extra/missing one is invisible to the id-drift check.",
     "columns": [("zoneid", "Zone"), ("name", "Name"), ("lsb_count", "LSB count"), ("our_count", "Our count")],
     "zone_scoped": True},
    {"slug": "npcs", "label": "NPC id drift", "query": _iddrift_npcs,
     "description": "Same zone + same npc name in both, but a different npcid.",
     "columns": [("zoneid", "Zone"), ("lsb_name", "Name"), ("lsb_id", "LSB npcid"), ("our_id", "Our npcid")],
     "zone_offsets": True, "zone_scoped": True},
    {"slug": "npc-zone-blocks", "label": "NPC zone id-block overview", "query": _iddrift_npc_zone_blocks,
     "description": "Not a mismatch list -- per-zone npc id range on each side, so you can visually confirm a zone's block sits where expected and doesn't overlap the next zone's block.",
     "columns": [("zoneid", "Zone"), ("lsb_range", "LSB range"), ("lsb_count", "LSB count"), ("our_range", "Our range"), ("our_count", "Our count"), ("overlaps_next", "Overlaps next zone?")],
     "zone_scoped": True},
    {"slug": "mobgroups-count", "label": "Mob group name-count mismatch", "query": _iddrift_mobgroups_count,
     "description": "Same zone + same mob group name has a different NUMBER of entries on each side.",
     "columns": [("zoneid", "Zone"), ("name", "Name"), ("lsb_count", "LSB count"), ("our_count", "Our count")],
     "zone_scoped": True},
    {"slug": "mobgroups", "label": "Mob group id drift", "query": _iddrift_mobgroups,
     "description": "Same zone + same mob group name in both, but a different groupid/poolid.",
     "columns": [("zoneid", "Zone"), ("lsb_name", "Name"), ("lsb_groupid", "LSB group"), ("lsb_poolid", "LSB pool"), ("our_groupid", "Our group"), ("our_poolid", "Our pool")],
     "zone_scoped": True},
    {"slug": "mobskills", "label": "Mob skill id drift", "query": _iddrift_mobskills,
     "description": "Topaz-vs-LSB registration check, not client-based: same skill name in both sql/mob_skills.sql tables, but a different mob_skill_id -- these are hand-added independently by each fork.",
     "columns": [("lsb_name", "Name"), ("lsb_id", "LSB mob_skill_id"), ("our_id", "Our mob_skill_id")]},
    {"slug": "spells", "label": "Spell id drift", "query": _iddrift_spells,
     "description": "Real spell ids are the client's own canonical resource ids, so both forks should agree almost always -- any row here is a genuine surprise.",
     "columns": [("lsb_name", "Name"), ("lsb_id", "LSB spellid"), ("our_id", "Our spellid")]},
    {"slug": "abilities", "label": "Job ability id drift", "query": _iddrift_abilities,
     "description": "Same check for sql/abilities.sql. Client-canonical ids -- any row is a genuine surprise.",
     "columns": [("lsb_name", "Name"), ("lsb_id", "LSB abilityId"), ("our_id", "Our abilityId")]},
    {"slug": "weaponskills", "label": "Weapon skill id drift", "query": _iddrift_weaponskills,
     "description": "Client-canonical ids, same as spells/abilities -- any row is a genuine surprise.",
     "columns": [("lsb_name", "Name"), ("lsb_id", "LSB weaponskillid"), ("our_id", "Our weaponskillid")]},
    {"slug": "traits", "label": "Job trait id drift", "query": _iddrift_traits,
     "description": "Client-canonical ids -- any row is a genuine surprise.",
     "columns": [("lsb_name", "Name"), ("lsb_id", "LSB traitid"), ("our_id", "Our traitid")]},
    {"slug": "blu", "label": "Blue Magic spell -> mob skill drift", "query": _iddrift_blu,
     "description": "Does a BLU spell copy the same real mob ability in both? The spellid already matches (both use the client's own space) -- this checks whether the mob_skill_id it's wired to is the same.",
     "columns": [("spell_name", "Spell"), ("spellid", "Spellid"), ("lsb_mob_skill_id", "LSB mob_skill_id"), ("our_mob_skill_id", "Our mob_skill_id")]},
    {"slug": "pets-count", "label": "Pet name-count mismatch", "query": _iddrift_pets_count,
     "description": "Same name has a different NUMBER of pet entries on each side.",
     "columns": [("name", "Name"), ("lsb_count", "LSB count"), ("our_count", "Our count")]},
    {"slug": "pets", "label": "Pet id drift", "query": _iddrift_pets,
     "description": "Avatars, wyverns, automatons, spirits etc -- same zone-independent id/name check as items/npcs.",
     "columns": [("lsb_name", "Name"), ("lsb_id", "LSB petid"), ("our_id", "Our petid")]},
    {"slug": "effects", "label": "Status effect id drift", "query": _iddrift_effects,
     "description": "Topaz-vs-LSB registration check, not client-based. LSB generates both its C++ enum and its Lua xi.effect table from one data/status_effects.yaml; Topaz's src/map/status_effect.h is a separate hand-written C++ enum.",
     "columns": [("lsb_name", "Name"), ("lsb_id", "LSB effectid"), ("our_id", "Our effectid")]},
    {"slug": "effects-gap", "label": "Effects LSB has that Topaz doesn't", "query": _iddrift_effects_gap,
     "description": "Not a bug -- effects LSB has added that this server hasn't implemented yet.",
     "columns": [("effectid", "LSB effectid"), ("name", "Name")]},
]
IDDRIFT_BY_SLUG = {c["slug"]: c for c in IDDRIFT_CATEGORIES}
IDDRIFT_PAGE_SIZE = 50


@app.get("/iddrift", response_class=HTMLResponse)
def iddrift_index(request: Request):
    """Category browser -- one row per drift category with a real count, linking to its own
    /iddrift/{slug} page instead of one giant page dumping every category's full table at once."""
    con = get_con()
    rows = []
    for cat in IDDRIFT_CATEGORIES:
        count = len(cat["query"](con, ""))
        rows.append({"slug": cat["slug"], "label": cat["label"], "description": cat["description"], "count": count})
    con.close()
    return templates.TemplateResponse(request, "iddrift.html", {"categories": rows})


@app.get("/iddrift/{slug}", response_class=HTMLResponse)
def iddrift_detail(request: Request, slug: str, q: str = "", zone: str = "", page: int = 1):
    cat = IDDRIFT_BY_SLUG.get(slug)
    if not cat:
        return RedirectResponse(url="/iddrift")
    con = get_con()
    zones = []
    zoneid = None
    if cat.get("zone_scoped"):
        zones = con.execute("SELECT zoneid, name FROM zones WHERE zoneid > 0 ORDER BY name").fetchall()
        if zone:
            zoneid_row = con.execute("SELECT zoneid FROM zones WHERE name = ?", (zone.upper(),)).fetchone()
            zoneid = zoneid_row[0] if zoneid_row else None
        all_rows = cat["query"](con, q, zoneid)
    else:
        all_rows = cat["query"](con, q)
    zone_offset_summary = _iddrift_npc_zone_offsets(all_rows) if cat.get("zone_offsets") else None
    con.close()
    zone_names = {z["zoneid"]: z["name"] for z in zones}

    page = max(1, page)
    total = len(all_rows)
    total_pages = max(1, (total + IDDRIFT_PAGE_SIZE - 1) // IDDRIFT_PAGE_SIZE)
    offset = (page - 1) * IDDRIFT_PAGE_SIZE
    page_rows = all_rows[offset:offset + IDDRIFT_PAGE_SIZE]

    return templates.TemplateResponse(request, "iddrift_detail.html", {
        "slug": slug, "label": cat["label"], "description": cat["description"],
        "columns": cat["columns"], "link_col": cat.get("link_col"),
        "rows": page_rows, "total": total, "q": q, "page": page, "total_pages": total_pages,
        "zone_offset_summary": zone_offset_summary,
        "zone_scoped": cat.get("zone_scoped", False), "zones": zones, "zone": zone,
        "zone_names": zone_names,
    })


def _target_flavor_banner() -> dict:
    """Live fingerprint of whatever DSP checkout Settings has configured -- surfaced on every
    load of this page so a mismatch between the configured target and what a conversion is about
    to assume is visible BEFORE running one, not discovered later. This is the GUI-side half of
    the same lesson backport_lua_convert.detect_target_flavor()/verify_target_or_raise() exist
    for: an entire session's worth of DSP work was once checked against the wrong codebase with
    nothing surfacing that fact anywhere."""
    dsp_root = settings_mod.get_dsp_root()
    if not dsp_root:
        return {"dsp_root": None, "flavor": None}
    flavor = backport_lua_convert.detect_target_flavor(dsp_root)
    return {"dsp_root": str(dsp_root), "flavor": flavor}


@app.get("/backport/lua-convert", response_class=HTMLResponse)
def lua_convert_form(request: Request):
    """Paste-a-file-in, get-a-converted-file-out page for the Topaz -> DSP Lua conversion. Same
    backport_enabled() gate as ID Drift -- this only matters to someone actually doing Topaz/DSP
    backport work. Defaults target/id_shape to old_dsp_reference/flat -- the REAL production
    target (Valhalla) -- not landsandboat/nested, which was this page's stale default from before
    the 2026-09-13 correction (old_dsp_reference_full_remediation_2026-09-13.md)."""
    return templates.TemplateResponse(request, "backport_lua_convert.html", {
        "source": "", "converted": "", "flagged": [], "zone_table": "", "id_shape": "flat",
        "target": "old_dsp_reference", "id_file_hint": "", "ran": False,
        "map_path": str(backport_lua_convert.MAP_PATH), **_target_flavor_banner(),
    })


@app.post("/backport/lua-convert", response_class=HTMLResponse)
async def lua_convert_submit(request: Request):
    form = await request.form()
    source = form.get("source") or ""
    zone_table = (form.get("zone_table") or "").strip() or None
    id_shape = form.get("id_shape") or "flat"
    target = form.get("target") or "old_dsp_reference"
    id_file_hint = (form.get("id_file_hint") or "").strip() or None

    result = backport_lua_convert.convert(
        source, zone_table=zone_table, id_shape=id_shape, id_file_hint=id_file_hint, target=target,
    )
    return templates.TemplateResponse(request, "backport_lua_convert.html", {
        "source": source, "converted": result.converted, "flagged": result.flagged,
        "zone_table": zone_table or "", "id_shape": id_shape, "target": target,
        "id_file_hint": id_file_hint or "", "ran": True,
        "map_path": str(backport_lua_convert.MAP_PATH), **_target_flavor_banner(),
    })


BINDINGS_PAGE_SIZE = 100


def _bindings_rows() -> list[dict]:
    """Full Topaz-vs-old-dsp-reference binding inventory, one row per distinct name from EITHER
    side, cross-referenced against dsp_namespace_map.json's method_renames -- so this page answers
    "what does DSP call this" for a name a converter run flagged, without leaving the browser to
    grep two codebases by hand (the exact workflow backport_binding_index.py --diff was built for,
    surfaced here for browsing/searching instead of a one-shot CLI dump). Recomputed on every
    request from the cached indexes (data/*_binding_index.json) -- cheap (in-memory dict work over
    ~1300 names), so no need to cache further; run backport_binding_index.py --build to refresh the
    underlying indexes after a DSP engine patch adds/renames a binding."""
    topaz = backport_binding_index.load_index(backport_binding_index.TOPAZ_INDEX_PATH)
    dsp = backport_binding_index.load_index(backport_binding_index.DSP_INDEX_PATH)
    dsp_lower = {name.lower(): name for name in dsp}

    namespace_map = backport_lua_convert.load_map()
    method_renames = namespace_map.get("method_renames", {})

    rows = []
    seen_dsp_names = set()
    for name in sorted(topaz):
        renamed = method_renames.get(name)
        if renamed:
            dsp_name = renamed.get("dsp_name")
            status = "renamed"
        elif name in dsp:
            dsp_name = name
            status = "exact"
        elif name.lower() in dsp_lower:
            dsp_name = dsp_lower[name.lower()]
            status = "case_only"
        else:
            dsp_name = None
            status = "topaz_only"
        if dsp_name:
            seen_dsp_names.add(dsp_name)
        rows.append({
            "name": name, "topaz_locations": topaz[name],
            "dsp_name": dsp_name, "dsp_locations": dsp.get(dsp_name, []) if dsp_name else [],
            "status": status,
            "rename_evidence": renamed.get("evidence") if renamed else None,
            "rename_source": renamed.get("source") if renamed else None,
        })

    # DSP-only names (no Topaz name maps to them at all, renamed or otherwise) -- real bindings
    # this codebase has that Topaz never had a reason to call, still worth being able to find here.
    for name in sorted(set(dsp) - seen_dsp_names):
        rows.append({
            "name": None, "topaz_locations": [],
            "dsp_name": name, "dsp_locations": dsp[name],
            "status": "dsp_only", "rename_evidence": None, "rename_source": None,
        })
    return rows


STATUS_LABELS = {
    "exact": "Exact match", "renamed": "Confirmed rename", "case_only": "Case-only mismatch",
    "topaz_only": "Topaz-only (needs a look)", "dsp_only": "DSP-only (no Topaz caller)",
}


@app.get("/backport/bindings", response_class=HTMLResponse)
def bindings_index(request: Request, q: str = "", status: str = "", page: int = 1):
    """Dedicated browse/search page over the full Topaz<->old-dsp-reference binding inventory --
    separate from the Lua Converter (which only surfaces bindings actually hit by whatever source
    got pasted in) so a name can be looked up for reference at any time, not just mid-conversion."""
    try:
        all_rows_full = _bindings_rows()
        index_missing = None
    except FileNotFoundError as e:
        all_rows_full = []
        index_missing = str(e)

    counts = {}
    for r in all_rows_full:
        counts[r["status"]] = counts.get(r["status"], 0) + 1

    all_rows = all_rows_full
    q_lower = q.strip().lower()
    if q_lower:
        all_rows = [r for r in all_rows
                    if (r["name"] and q_lower in r["name"].lower())
                    or (r["dsp_name"] and q_lower in r["dsp_name"].lower())]
    if status:
        all_rows = [r for r in all_rows if r["status"] == status]

    page = max(1, page)
    total = len(all_rows)
    total_pages = max(1, (total + BINDINGS_PAGE_SIZE - 1) // BINDINGS_PAGE_SIZE)
    offset = (page - 1) * BINDINGS_PAGE_SIZE
    page_rows = all_rows[offset:offset + BINDINGS_PAGE_SIZE]

    return templates.TemplateResponse(request, "backport_bindings.html", {
        "rows": page_rows, "total": total, "q": q, "status": status,
        "page": page, "total_pages": total_pages, "counts": counts,
        "status_labels": STATUS_LABELS, "index_missing": index_missing,
    })


@app.get("/backport/sql-convert", response_class=HTMLResponse)
def sql_convert_form(request: Request):
    """Paste-INSERT-statements-in, get-DSP-shaped-INSERTs-out page, plus a real id-collision check
    against DSP's already-indexed data (dsp_* tables from build_dsp_index.py) -- not just a raw
    dump diff. Same backport_enabled() gate as the Lua converter/ID Drift."""
    return templates.TemplateResponse(request, "backport_sql_convert.html", {
        "source": "", "table": "npc_list", "converted": "", "warnings": [], "collisions": None,
        "ran": False, "tables": sorted(backport_sql_convert.load_schema_map().keys() - {"_readme"}),
        "map_path": str(backport_sql_convert.MAP_PATH),
    })


@app.post("/backport/sql-convert", response_class=HTMLResponse)
async def sql_convert_submit(request: Request):
    form = await request.form()
    source = form.get("source") or ""
    table = form.get("table") or "npc_list"

    schema_map = backport_sql_convert.load_schema_map()
    rows = [r for t, r in backport_sql_convert.parse_insert_values(source) if t == table]
    result = backport_sql_convert.convert_table(table, rows, schema_map)

    collisions = None
    if result.converted_ids:
        con = get_con()
        try:
            collisions = backport_sql_convert.check_id_collisions(
                con, table, result.converted_ids, schema_map, id_to_name=result.id_to_name,
            )
        finally:
            con.close()

    return templates.TemplateResponse(request, "backport_sql_convert.html", {
        "source": source, "table": table, "converted": result.converted_sql,
        "warnings": result.warnings, "collisions": collisions, "ran": True,
        "tables": sorted(schema_map.keys() - {"_readme"}), "map_path": str(backport_sql_convert.MAP_PATH),
    })


def _backport_packages_root() -> Path:
    return settings_mod.get_backport_root() / "mission-packages"


def _list_backport_packages() -> list[str]:
    """Every subfolder of the packages root that has a real lua/ tree -- same convention
    backport_binding_audit.py --all-packages / backport_lua_sanity_check.py --all-packages glob
    for (*/lua-dsp), just checking the SOURCE side here since a package may not be converted yet."""
    root = _backport_packages_root()
    if not root.is_dir():
        return []
    return sorted(p.name for p in root.iterdir() if p.is_dir() and (p / "lua").is_dir())


@app.get("/backport/package", response_class=HTMLResponse)
def backport_package_form(request: Request):
    """Point-and-run end-to-end package backport: pick a package folder already sitting under
    backport_root/mission-packages/, run backport_package.py's full convert+verify pipeline
    against it, see the consolidated report inline -- the GUI front end for the same tool a user
    would otherwise run from a terminal after editing a package's Lua/SQL, so a change can be
    re-checked for gaps (missing bindings, flagged conversions, real SQL id collisions) without
    leaving the browser. Still per-package, not a cross-package/cross-zone dependency crawl."""
    return templates.TemplateResponse(request, "backport_package.html", {
        "packages": _list_backport_packages(), "packages_root": str(_backport_packages_root()),
        "package": "", "target": "old_dsp_reference", "id_shape": "flat", "zone_table": "",
        "id_file_hint": "", "verify_only": False, "ran": False, "report": None, "error": None,
        **_target_flavor_banner(),
    })


@app.post("/backport/package", response_class=HTMLResponse)
async def backport_package_submit(request: Request):
    form = await request.form()
    package = (form.get("package") or "").strip()
    target = form.get("target") or "old_dsp_reference"
    id_shape = form.get("id_shape") or "flat"
    zone_table = (form.get("zone_table") or "").strip() or None
    id_file_hint = (form.get("id_file_hint") or "").strip() or None
    verify_only = form.get("verify_only") == "on"

    ctx = {
        "packages": _list_backport_packages(), "packages_root": str(_backport_packages_root()),
        "package": package, "target": target, "id_shape": id_shape, "zone_table": zone_table or "",
        "id_file_hint": id_file_hint or "", "verify_only": verify_only, "ran": True, "report": None,
        "error": None, **_target_flavor_banner(),
    }

    packages_root = _backport_packages_root()
    package_dir = packages_root / package if package else None
    if not package or not package_dir.is_dir():
        ctx["error"] = f"No such package under {packages_root}: {package!r}"
        return templates.TemplateResponse(request, "backport_package.html", ctx)

    dsp_root = settings_mod.get_dsp_root()
    if dsp_root is None:
        ctx["error"] = "No DSP checkout configured -- set it on the Settings page first."
        return templates.TemplateResponse(request, "backport_package.html", ctx)
    flavor = backport_lua_convert.detect_target_flavor(dsp_root)
    if flavor is None:
        ctx["error"] = f"{dsp_root} does not fingerprint as either known DSP flavor -- check the path on Settings."
        return templates.TemplateResponse(request, "backport_package.html", ctx)
    if flavor != target:
        ctx["error"] = f"Configured DSP checkout fingerprints as '{flavor}', but target is '{target}' -- pick '{flavor}' above."
        return templates.TemplateResponse(request, "backport_package.html", ctx)

    lua_src, lua_dst = package_dir / "lua", package_dir / "lua-dsp"
    sql_src, sql_dst = package_dir / "sql", package_dir / "sql-dsp"

    lua_result = None
    sql_result = None
    if not verify_only:
        if lua_src.is_dir():
            lua_result = backport_package.convert_lua_tree(
                lua_src, lua_dst, target, zone_table, id_shape, id_file_hint)
        schema_map = backport_sql_convert.load_schema_map()
        sql_result = backport_package.convert_sql_tree(sql_src, sql_dst, schema_map)
    elif not lua_dst.is_dir():
        ctx["error"] = f"Verify-only needs an existing {lua_dst} -- run a real conversion first."
        return templates.TemplateResponse(request, "backport_package.html", ctx)

    binding_result = backport_binding_audit.audit_package(lua_dst, dsp_root, flavor) if lua_dst.is_dir() else \
        {"confirmed": [], "missing": []}
    sanity_result = backport_lua_sanity_check.check_package(lua_dst) if lua_dst.is_dir() else \
        {"syntax_errors": [], "undeclared_globals": []}

    collision_results = {}
    if sql_result and sql_result["ids_by_table"]:
        collision_results = backport_package.run_id_collision_checks(
            sql_result["ids_by_table"], sql_result["id_to_name_by_table"],
            backport_sql_convert.load_schema_map())

    report_md = backport_package.build_report(
        package_dir, target, dsp_root, flavor, lua_result, sql_result,
        binding_result, sanity_result, collision_results)
    (package_dir / "BACKPORT_REPORT.md").write_text(report_md, encoding="utf-8", newline="\n")

    overall_clean = (
        (lua_result is None or lua_result["total_flags"] == 0)
        and not binding_result["missing"]
        and not sanity_result["syntax_errors"]
        and not sanity_result["undeclared_globals"]
        and not any(r.get("name_mismatch") for r in collision_results.values())
    )

    ctx["report"] = {
        "lua_result": lua_result, "sql_result": sql_result, "binding_result": binding_result,
        "sanity_result": sanity_result, "collision_results": collision_results,
        "overall_clean": overall_clean, "report_path": str(package_dir / "BACKPORT_REPORT.md"),
        "report_md": report_md,
    }
    return templates.TemplateResponse(request, "backport_package.html", ctx)


# Files this large take a while even on the faster 7B models, and gemma4:26b longer still --
# a longer timeout than llm_client's own 60s default so a real (if slow) response isn't cut off
# and mistaken for a dead server. Bumped further per-call below when a file/image is attached.
LLM_PAGE_TIMEOUT = 180

# Hard cap on how much of a file gets pasted into a prompt -- past this, a summary request just
# turns into "the model reads half a truncated file," not a real summary. Anything longer should
# be chunked by a real automated tool (not built yet), not force-fed here.
LLM_FILE_SUMMARY_MAX_CHARS = 40000


def _llm_models(base_url: str) -> tuple[list[dict], str | None]:
    if not llm_client.has_api_key():
        return [], "No API key configured -- set one on the Settings page first."
    try:
        return llm_client.list_models(base_url=base_url), None
    except llm_client.LLMClientError as e:
        return [], str(e)


def _model_supports_vision(models: list[dict], model_id: str) -> bool:
    """True if `model_id` is one of `models` (from _llm_models()) AND reports the "vision"
    capability. False (not True) for a model_id not found in the list at all -- an unknown/stale
    selection should never be treated as vision-capable by default."""
    for m in models:
        if m.get("id") == model_id:
            return "vision" in m.get("ollama", {}).get("capabilities", [])
    return False


LLM_TOOLS_SYSTEM_PROMPT = (
    "You can use tools to answer questions using this project's real, live database. Available tools:\n"
    + "\n".join(f"- {desc}" for _fn, desc in llm_db_tools.TOOLS.values())
    + """

To call a tool, respond with ONLY a single JSON object on one line, nothing else:
{"tool": "<name>", "args": {...}}

Do NOT call list_tables as your first move for an ordinary question -- it dumps 100+ table names
and wastes your limited number of tool calls. Instead, go straight to query_sql against whichever
of these real, commonly-useful tables actually fits the question (call describe_table first only
if you're unsure of a column name):
- dsp_mob_pools (poolid, name, norm_name, familyid, modelid) -- one row per mob TYPE (not spawn).
- dsp_mob_skills (mob_skill_id, mob_anim_id, name, norm_name, aoe, distance, ...) -- one row per
  mob skill definition, matched by `name` (e.g. WHERE name = 'firespit').
- dsp_mob_spawn_points (mobid, mobname, norm_name, groupid, pos_x/y/z, pos_rot) -- one row per
  actual spawned mob instance in the world.
- dsp_npc_list (npcid, name, norm_name, zoneid, pos_x/y/z, entityFlags) -- non-mob NPCs.
- dsp_item_basic (itemid, name, norm_name, stackSize, ...) -- items.
- dsp_mob_droplist (dropid, dropType, groupId, groupRate, itemId, itemRate) -- drop tables.
Prefix swap for a different source: lsb_*, topaz_*, sql_* mirror the same dsp_* shapes above for
the other three data sources this toolkit cross-references.

KNOWN REAL GAP, be honest about it: there is no indexed join table linking a specific mob to the
list of mob skills it uses (mob_pools has no skill_list_id/similar column in what's queryable
here) -- querying dsp_mob_skills can confirm a skill NAME/id exists, but cannot tell you WHICH
mobs use it. If a question needs that link, say plainly that this isn't answerable from the
tables available rather than answering vaguely (e.g. never say something like "used by multiple
NPCs" unless you actually queried and named which ones).

Once you have enough real information to answer, respond in plain text (not JSON). Never guess at
data you haven't actually queried, never claim a number/fact you didn't get from a real tool
result, and never pad out an answer with a vague-sounding claim to cover for a query that returned
nothing or a question the schema can't actually answer -- say so plainly instead."""
)
MAX_TOOL_ROUNDS = 8
_CODE_FENCE_RE = re.compile(r"^```(?:json)?\s*\n?(.*?)\n?```$", re.DOTALL)


def _parse_tool_call(content: str) -> dict | None:
    """Returns the parsed {"tool": ..., "args": {...}} dict if `content` starts with (or, wrapped
    in a markdown code fence, contains) a tool-call JSON object, else None. Two real robustness
    gaps found live 2026-09-14, both handled here:
      1. The model doesn't always emit bare JSON as instructed -- it sometimes wraps it in a
         ```json ... ``` fence. A naive "does the whole string look like {...}" check misses this
         entirely, silently treating a real tool-call attempt as a final answer instead.
      2. The model sometimes emits SEVERAL tool-call JSON objects back to back in one response
         (guessing ahead at a whole call sequence) instead of one at a time as instructed. Using
         json.loads() on the whole string then fails (trailing data), again silently falling
         through to "final answer". json.JSONDecoder().raw_decode() parses just the FIRST JSON
         value and ignores anything after it -- exactly right here: only ever act on the first
         call, then let the real tool result drive what the model does next, rather than trusting
         a guessed-ahead sequence that assumed the wrong result for an earlier call."""
    stripped = content.strip()
    fence = _CODE_FENCE_RE.match(stripped)
    if fence:
        stripped = fence.group(1).strip()
    if not stripped.startswith("{"):
        return None
    try:
        parsed, _end = json.JSONDecoder().raw_decode(stripped)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) and "tool" in parsed else None


def _run_tool_chat(prompt: str, model: str, system: str | None, base_url: str, timeout: float) -> dict:
    """Real, prompt-based ReAct-style tool loop (see llm_db_tools.py's own docstring for why this
    project uses this instead of the formal OpenAI tools/tool_calls API field -- verified live
    that field doesn't round-trip reliably against this project's actual local Open WebUI/Ollama
    setup). Every tool call is read-only (llm_db_tools.call_tool's own guarantee) and every round
    is recorded in the returned transcript for the caller to display -- the model's DB access is
    never a black box. Returns {"content": final_text, "transcript": [...], "usage": dict,
    "hit_round_limit": bool}."""
    combined_system = (system + "\n\n" if system else "") + LLM_TOOLS_SYSTEM_PROMPT
    messages = [{"role": "system", "content": combined_system}, {"role": "user", "content": prompt}]
    transcript: list[dict] = []
    content, usage = "", {}
    for _round in range(MAX_TOOL_ROUNDS):
        result = llm_client.chat_messages(messages, model=model, base_url=base_url, timeout=timeout)
        content, usage = result["content"], result["usage"]

        parsed = _parse_tool_call(content)
        if parsed is None:
            return {"content": content, "transcript": transcript, "usage": usage, "hit_round_limit": False}

        tool_name = parsed.get("tool")
        tool_args = parsed.get("args") or {}
        tool_result = llm_db_tools.call_tool(tool_name, tool_args)
        transcript.append({"tool": tool_name, "args": tool_args, "result": tool_result})
        messages.append({"role": "assistant", "content": content})
        messages.append({"role": "user", "content": "Tool result: " + json.dumps(tool_result)})

    return {"content": content, "transcript": transcript, "usage": usage, "hit_round_limit": True}


@app.get("/llm/log/{log_id}", response_class=HTMLResponse)
def llm_log_detail(request: Request, log_id: int):
    """Full-text view of one Recent Calls row -- the log table itself only shows the first 200
    chars per field (readability in a compact table), and even the DB only ever stores up to
    llm_log.MAX_STORED_CHARS -- there is no un-truncated copy beyond that anywhere. This page just
    stops throwing away the rest of what WAS actually stored."""
    row = llm_log.get_by_id(log_id)
    if row is None:
        return HTMLResponse(f'<p class="muted" style="color:var(--red);">No log entry with id {log_id}.</p>', status_code=404)
    return templates.TemplateResponse(request, "llm_log_detail.html", {
        "row": row, "draft_tag": llm_client.LLM_DRAFT_TAG,
    })


@app.get("/llm", response_class=HTMLResponse)
def llm_page(request: Request, source: str = "", model_filter: str = "", q: str = ""):
    """Manual "pass off a prompt, see the response" page for the local Open WebUI/Ollama
    instance, plus a visible, filterable log of every call made through llm_client.py -- both
    this page's own manual calls and anything an automated tool records via llm_log.record().
    Never assume the server is reachable/configured: a missing key or a down server degrades to
    an inline error, not a crashed page."""
    con = get_con()
    values = settings_mod.get_all(con)
    con.close()

    models, models_error = _llm_models(values["llm_base_url"])

    return templates.TemplateResponse(request, "llm.html", {
        "values": values, "models": models, "models_error": models_error,
        "prompt": "", "system": "", "file_path": "", "model": values["llm_default_model"],
        "response": None, "usage_display": None, "call_error": None, "ran": False,
        "tool_transcript": None, "hit_round_limit": False, "use_db_tools": False,
        "log": llm_log.recent(source=source or None, model=model_filter or None, q=q or None),
        "log_sources": llm_log.distinct_sources(),
        "filter_source": source, "filter_model": model_filter, "filter_q": q,
        "draft_tag": llm_client.LLM_DRAFT_TAG, "quick_actions": QUICK_ACTIONS,
    })


@app.post("/llm", response_class=HTMLResponse)
async def llm_submit(request: Request):
    form = await request.form()
    prompt = form.get("prompt", "")
    system = form.get("system", "").strip() or None
    file_path = form.get("file_path", "").strip()
    image_upload = form.get("image")
    # Set when the Prompt box was loaded from the quick-action dropdown (see
    # /llm/quick-action-prompt) and left unedited enough to still count as that action, rather
    # than a free-form manual prompt -- lets the log correctly attribute it instead of every
    # quick-action-originated call collapsing into "manual".
    log_source = form.get("quick_action", "").strip() or "manual"
    use_db_tools = form.get("use_db_tools") == "on"

    con = get_con()
    values = settings_mod.get_all(con)
    con.close()
    model = form.get("model", "").strip() or values["llm_default_model"]
    models, models_error = _llm_models(values["llm_base_url"])

    # File-path summarize input: read the file server-side and fold it into the prompt, rather
    # than requiring it be pasted by hand. A prompt AND a file both given appends the file's
    # content after the user's own instructions instead of overwriting -- e.g. "focus on the
    # mission-fail conditions" as the prompt, with the actual doc attached below it.
    file_error = None
    if file_path:
        target = Path(file_path)
        if not target.is_file():
            file_error = f"Not a file: {file_path}"
        else:
            try:
                content = target.read_text(encoding="utf-8", errors="replace")
            except OSError as e:
                file_error = f"Could not read {file_path}: {e}"
            else:
                truncated = len(content) > LLM_FILE_SUMMARY_MAX_CHARS
                if truncated:
                    content = content[:LLM_FILE_SUMMARY_MAX_CHARS]
                file_block = (
                    f"\n\n--- {target.name}{' (truncated)' if truncated else ''} ---\n{content}"
                )
                prompt = (prompt.strip() + file_block) if prompt.strip() else (
                    f"Summarize the following file ({target.name}) for someone unfamiliar with it:"
                    f"{file_block}"
                )

    image_b64 = None
    image_mime = "image/png"
    if image_upload and getattr(image_upload, "filename", ""):
        image_bytes = await image_upload.read()
        if image_bytes:
            image_b64 = base64.b64encode(image_bytes).decode("ascii")
            image_mime = getattr(image_upload, "content_type", None) or "image/png"

    response_text = None
    usage_display = None
    tool_transcript = None
    hit_round_limit = False
    call_error = file_error
    if not call_error:
        if not prompt.strip():
            call_error = "Prompt (or a file path) is required."
        elif use_db_tools and image_b64:
            call_error = "Read-only DB tools and image attachments can't be combined -- pick one."
        elif image_b64 and not _model_supports_vision(models, model):
            # Real error found live 2026-09-14: sending an image to a non-vision model gets a
            # generic "Multimodal data provided, but model does not support multimodal requests"
            # from Open WebUI -- correct but unhelpful (doesn't say WHICH models would work).
            # Caught here with a clear, actionable message instead of surfacing the raw API error;
            # the model dropdown's own JS also filters to vision models once an image is chosen,
            # so this is a safety net for a stale selection, not the primary defense.
            vision_models = ", ".join(m["id"] for m in models if "vision" in m.get("ollama", {}).get("capabilities", [])) or "(none currently loaded)"
            call_error = (f"'{model}' doesn't support image input. Vision-capable models "
                          f"currently loaded: {vision_models}.")
        else:
            try:
                timeout = LLM_PAGE_TIMEOUT * (2 if image_b64 else 1)
                if use_db_tools:
                    # Tool rounds each cost their own model call, so give this real headroom --
                    # MAX_TOOL_ROUNDS sequential calls, not one.
                    result = _run_tool_chat(
                        prompt, model, system, values["llm_base_url"], timeout=LLM_PAGE_TIMEOUT)
                    tool_transcript = result["transcript"]
                    hit_round_limit = result["hit_round_limit"]
                    if hit_round_limit:
                        log_source = "manual_db_tools_truncated"
                    elif tool_transcript:
                        log_source = "manual_db_tools"
                else:
                    result = llm_client.chat_full(
                        prompt, model=model, system=system, base_url=values["llm_base_url"],
                        timeout=timeout, image_b64=image_b64, image_mime=image_mime,
                    )
                response_text = result["content"]
                usage = result["usage"]
                tok_s = usage.get("response_token/s")
                total_s = usage.get("total_duration")
                usage_display = (
                    f"{tok_s:.0f} tok/s, {total_s / 1e9:.1f}s" if tok_s and total_s else ""
                )
                log_prompt = prompt if not tool_transcript else (
                    prompt + "\n\n[tool calls: " + json.dumps(tool_transcript) + "]"
                )
                llm_log.record(log_source, model, log_prompt, response=response_text, usage=usage)
            except llm_client.LLMClientError as e:
                call_error = str(e)
                llm_log.record(log_source, model, prompt, error=call_error)

    return templates.TemplateResponse(request, "llm.html", {
        "values": values, "models": models, "models_error": models_error,
        "prompt": prompt, "system": system or "", "file_path": file_path, "model": model,
        "response": response_text, "usage_display": usage_display, "call_error": call_error,
        "tool_transcript": tool_transcript, "hit_round_limit": hit_round_limit,
        "use_db_tools": use_db_tools,
        "ran": True, "log": llm_log.recent(), "log_sources": llm_log.distinct_sources(),
        "filter_source": "", "filter_model": "", "filter_q": "",
        "draft_tag": llm_client.LLM_DRAFT_TAG, "quick_actions": QUICK_ACTIONS,
    })


def _suggest_grep_prompt(line_text: str, citation: str = "") -> str:
    """Shared with /llm/quick-action-prompt so the main LLM Assistant page's quick-action dropdown
    builds the EXACT same prompt this route sends -- one real template, not two copies to keep in
    sync."""
    return (
        "A Topaz FFXI server Lua line failed to convert to our DSP target automatically:\n\n"
        f"{line_text}\n\n"
        + (f"Known context: {citation}\n\n" if citation else "")
        + "In one or two sentences, suggest what a real DSP C++/Lua source file and function name "
          "to grep for might plausibly be, to find the equivalent. Be concise. Do not claim "
          "certainty -- this is only a starting point for a human to go verify against real source."
    )


def _capture_summary_prompt(con: sqlite3.Connection, capture_id: int) -> str | None:
    """Shared with /llm/quick-action-prompt -- returns None if the capture doesn't exist.

    Pulls real sampled CONTENT (named entities, combat actions, events, chat) from the capture's
    own indexed tables, not just metadata/row counts -- a model asked to summarize "139 npc
    entries, 74 events" has nothing to actually describe; a model given "Qutrub cast Thunder,
    Absorb-STR, Stun; Lamia Graverobber cast Waterga III" can write something a developer would
    actually find useful. Every table is queried defensively (a capture format that doesn't
    populate a given table, e.g. no chat log, just contributes an empty section, not an error)."""
    row = con.execute("SELECT * FROM captures WHERE capture_id=?", (capture_id,)).fetchone()
    if not row:
        return None
    cap = dict(row)
    tags = build_capture_index.get_capture_tags(con, capture_id)

    hp_events = con.execute(
        "SELECT mob_name, hp_low, hp_high FROM capture_hp_events WHERE capture_id=? ORDER BY seq LIMIT 30",
        (capture_id,)).fetchall()
    n_history = con.execute("SELECT COUNT(*) FROM capture_npc_history WHERE capture_id=?", (capture_id,)).fetchone()[0]
    n_events = con.execute("SELECT COUNT(*) FROM capture_events WHERE capture_id=?", (capture_id,)).fetchone()[0]

    named_entities = con.execute(
        "SELECT DISTINCT name FROM capture_npc_entries WHERE capture_id=? AND name IS NOT NULL "
        "AND name NOT LIKE '\\_%' ESCAPE '\\' ORDER BY name LIMIT 25", (capture_id,)).fetchall()
    actions = con.execute(
        "SELECT actor_name, name FROM capture_actions WHERE capture_id=? AND name IS NOT NULL "
        "ORDER BY ts LIMIT 25", (capture_id,)).fetchall()
    events = con.execute(
        "SELECT DISTINCT opcode_name, entity_name FROM capture_events WHERE capture_id=? "
        "AND entity_name IS NOT NULL ORDER BY seq LIMIT 25", (capture_id,)).fetchall()
    chat = con.execute(
        "SELECT text FROM capture_caplog_chat WHERE capture_id=? AND text IS NOT NULL "
        "ORDER BY seq LIMIT 15", (capture_id,)).fetchall()
    ki_events = con.execute(
        "SELECT keyitem_name FROM capture_ki_events WHERE capture_id=? AND keyitem_name IS NOT NULL "
        "ORDER BY seq LIMIT 15", (capture_id,)).fetchall()

    zones = json.loads(cap["zones"]) if cap.get("zones") else []
    lines = [
        f"label: {cap.get('capture_label')}",
        f"content_type: {cap.get('content_type')}",
        f"mission: {cap.get('mission_name') or '(unresolved)'}",
        f"zones: {', '.join(zones) or '(none recorded)'}",
        f"capturer: {cap.get('capturer') or '(unknown)'}",
        f"tags: {', '.join(tags) or '(none)'}",
        f"npc history deltas: {n_history}, real events: {n_events}",
    ]
    if named_entities:
        lines.append("Named entities present (sample): " + ", ".join(r["name"] for r in named_entities))
    if actions:
        lines.append("Combat/ability actions in order (actor: action, sample): " + "; ".join(
            f"{a['actor_name']}: {a['name']}" for a in actions if a["actor_name"]
        ))
    if events:
        lines.append("Notable events (type -- entity, sample): " + "; ".join(
            f"{e['opcode_name']} -- {e['entity_name']}" for e in events
        ))
    if chat:
        lines.append("Chat/system text (sample): " + " | ".join(c["text"] for c in chat if c["text"]))
    if ki_events:
        lines.append("Key items obtained (sample): " + ", ".join(k["keyitem_name"] for k in ki_events))
    if hp_events:
        lines.append("HP events (mob, hp% range): " + "; ".join(
            f"{h['mob_name']} {h['hp_low']}-{h['hp_high']}%" for h in hp_events
        ))
    return (
        "Here is metadata for one FFXI Assault-mission gameplay capture. Write a single, plain "
        "one-paragraph summary a developer could read to quickly understand what this capture "
        "shows, without restating every field verbatim:\n\n" + "\n".join(lines)
    )


QUICK_ACTIONS = {
    "lua_converter_suggest_grep": {
        "label": "Lua Converter: suggest a grep target for a flagged line",
        "fields": [
            {"name": "line_text", "label": "Flagged line text", "type": "textarea"},
            {"name": "citation", "label": "Known context (optional)", "type": "text"},
        ],
    },
    "capture_summarize": {
        "label": "Captures: summarize one capture's indexed data",
        "fields": [{"name": "capture_id", "label": "Capture id", "type": "number"}],
    },
}


@app.post("/llm/quick-action-prompt")
async def llm_quick_action_prompt(request: Request):
    """Builds the real prompt text for one of QUICK_ACTIONS server-side (same helper functions
    the dedicated routes below use) and returns it as JSON, so the main LLM Assistant page's
    dropdown can load the exact real template into the Prompt box instead of a user having to
    know these actions exist at all, let alone reconstruct their wording by hand."""
    form = await request.form()
    action = form.get("action", "")
    if action == "lua_converter_suggest_grep":
        line_text = form.get("line_text", "").strip()
        if not line_text:
            return JSONResponse({"error": "Flagged line text is required."}, status_code=400)
        return JSONResponse({"prompt": _suggest_grep_prompt(line_text, form.get("citation", "").strip())})
    if action == "capture_summarize":
        try:
            capture_id = int(form.get("capture_id", ""))
        except ValueError:
            return JSONResponse({"error": "Capture id must be a number."}, status_code=400)
        con = get_con()
        try:
            prompt = _capture_summary_prompt(con, capture_id)
        finally:
            con.close()
        if prompt is None:
            return JSONResponse({"error": f"No capture with id {capture_id}."}, status_code=404)
        return JSONResponse({"prompt": prompt})
    return JSONResponse({"error": f"Unknown quick action: {action!r}"}, status_code=400)


@app.post("/llm/suggest-grep", response_class=HTMLResponse)
async def llm_suggest_grep(request: Request):
    """Quick action from the Lua Converter page: given one flagged line (a real tpz.* reference
    the namespace map doesn't cover yet) plus whatever citation text the converter already
    attached, ask the model to draft a suggestion for WHERE a human should go grep in the real
    DSP source to resolve it -- never an answer, just a starting point, same draft-only boundary
    as everything else in llm_client.py. Returns a small HTML fragment (not a full page) for the
    calling page to insert inline next to the flagged row."""
    form = await request.form()
    line_text = form.get("line_text", "").strip()
    citation = form.get("citation", "").strip()
    if not line_text:
        return HTMLResponse('<p class="muted" style="color:var(--red);">No line text given.</p>')

    con = get_con()
    values = settings_mod.get_all(con)
    con.close()

    prompt = _suggest_grep_prompt(line_text, citation)
    try:
        model = values["llm_default_model"]
        text = llm_client.chat(prompt, model=model, base_url=values["llm_base_url"], timeout=LLM_PAGE_TIMEOUT)
        llm_log.record("lua_converter_suggest_grep", model, prompt, response=text)
    except llm_client.LLMClientError as e:
        return HTMLResponse(f'<p class="muted" style="color:var(--red);">error: {e}</p>')

    return HTMLResponse(
        f'<div class="warn" style="border-left-color:var(--accent); background:var(--accent-soft); margin-top:6px;">'
        f'<strong>{llm_client.LLM_DRAFT_TAG}</strong><br>{text}</div>'
    )


@app.post("/llm/summarize-capture/{capture_id}", response_class=HTMLResponse)
def llm_summarize_capture(capture_id: int):
    """Quick action from the capture detail page: builds a plain-text summary of this capture's
    already-indexed structured data (no raw file read needed -- it's all in the DB) and asks the
    model for a one-paragraph human-readable summary. Useful for a capture with a long/unclear
    label, or before deciding whether it's worth watching the linked video."""
    con = get_con()
    prompt = _capture_summary_prompt(con, capture_id)
    if prompt is None:
        con.close()
        return HTMLResponse('<p class="muted" style="color:var(--red);">Capture not found.</p>')
    values = settings_mod.get_all(con)
    con.close()

    try:
        model = values["llm_default_model"]
        text = llm_client.chat(prompt, model=model, base_url=values["llm_base_url"], timeout=LLM_PAGE_TIMEOUT)
        llm_log.record("capture_summarize", model, prompt, response=text)
    except llm_client.LLMClientError as e:
        return HTMLResponse(f'<p class="muted" style="color:var(--red);">error: {e}</p>')

    return HTMLResponse(
        f'<div class="warn" style="border-left-color:var(--accent); background:var(--accent-soft); margin-top:6px;">'
        f'<strong>{llm_client.LLM_DRAFT_TAG}</strong><br>{text}</div>'
    )


ENTITY_PAGE_SIZE = 50


@app.get("/entity", response_class=HTMLResponse)
def entity_search(request: Request, q: str = "", page: int = 1):
    """List-only search page -- a single exact-id match redirects straight to its own
    /entity/{npcid} page (real navigation, not a same-page reload) rather than embedding the
    profile inline here. Mirrors the same fix applied to /captures: clicking through to a real
    URL means the browser's back button restores this page's scroll position on its own."""
    con = get_con()
    matches = []
    total = 0
    page = max(1, page)
    total_pages = 1
    if q:
        if q.isdigit():
            id_matches = lookup_entity.resolve_query_to_ids(con, q)
            if id_matches and id_matches[0][1] != "(unknown -- not in npc_names index)":
                con.close()
                return RedirectResponse(url=f"/entity/{id_matches[0][0]}")
            matches = id_matches
            total = 0
        else:
            total = lookup_entity.count_name_matches(con, q)
            offset = (page - 1) * ENTITY_PAGE_SIZE
            matches = lookup_entity.resolve_query_to_ids(con, q, limit=ENTITY_PAGE_SIZE, offset=offset)
            total_pages = max(1, (total + ENTITY_PAGE_SIZE - 1) // ENTITY_PAGE_SIZE)
    zone_names = {}
    if matches:
        zoneids = {zid for _, _, zid in matches if zid is not None}
        if zoneids:
            placeholders = ",".join("?" * len(zoneids))
            zone_names = dict(con.execute(
                f"SELECT zoneid, name FROM zones WHERE zoneid IN ({placeholders})", list(zoneids)
            ).fetchall())
    con.close()
    return templates.TemplateResponse(request, "entity.html", {
        "q": q, "matches": matches, "zone_names": zone_names,
        "page": page, "total_pages": total_pages, "total": total,
    })


@app.get("/entity/{npcid}", response_class=HTMLResponse)
def entity_detail(request: Request, npcid: int, q: str = "", page: int = 1):
    """Dedicated profile page. When reached from a name search, prev/next cycles through that
    search's current page of results (q/page carried as query params) -- the same "cycle through
    them" pattern as /captures/{id}. Registered as a plain path param, so like /captures/{id} it
    must come after any other more specific /entity/* route (none currently exist, but keep this
    at the bottom of the /entity routes if one is ever added)."""
    con = get_con()
    profile = entity_profile.build_profile(con, npcid)
    xi_model_viewer_url = settings_mod.get_all(con).get("xi_model_viewer_url", "").rstrip("/")

    prev_id = next_id = position = None
    if q and not q.isdigit():
        page = max(1, page)
        offset = (page - 1) * ENTITY_PAGE_SIZE
        page_matches = lookup_entity.resolve_query_to_ids(con, q, limit=ENTITY_PAGE_SIZE, offset=offset)
        page_ids = [m[0] for m in page_matches]
        if npcid in page_ids:
            idx = page_ids.index(npcid)
            position = f"{idx + 1} of {len(page_ids)} on page {page}"
            if idx > 0:
                prev_id = page_ids[idx - 1]
            if idx < len(page_ids) - 1:
                next_id = page_ids[idx + 1]
    con.close()
    return templates.TemplateResponse(request, "entity_detail.html", {
        "profile": profile, "q": q, "page": page,
        "prev_id": prev_id, "next_id": next_id, "position": position,
        "xi_model_viewer_url": xi_model_viewer_url,
    })


DIALOG_PAGE_SIZE = 200


@app.get("/dialog", response_class=HTMLResponse)
def dialog_search(request: Request, q: str = "", zone: str = "", page: int = 1, jump_id: int | None = None):
    con = get_con()
    results = []
    total = 0
    page = max(1, page)
    offset = (page - 1) * DIALOG_PAGE_SIZE
    zoneid = None
    if zone:
        row = con.execute("SELECT zoneid FROM zones WHERE name = ?", (zone.upper(),)).fetchone()
        zoneid = row[0] if row else None

    if not q and zoneid is not None:
        # Browse an entire zone's real dialog table -- no search term, just a zone picked.
        total = con.execute("SELECT COUNT(*) FROM dialog_text WHERE zoneid = ?", (zoneid,)).fetchone()[0]
        if jump_id is not None:
            # Jump to whichever page this real id would fall on within the zone's own idx
            # ordering (ids aren't contiguous, so this is a rank lookup, not a direct offset).
            rank = con.execute(
                "SELECT COUNT(*) FROM dialog_text WHERE zoneid = ? AND idx < ?", (zoneid, jump_id)
            ).fetchone()[0]
            page = (rank // DIALOG_PAGE_SIZE) + 1
        offset = (page - 1) * DIALOG_PAGE_SIZE
        rows = con.execute(
            "SELECT zoneid, idx, text FROM dialog_text WHERE zoneid = ? ORDER BY idx LIMIT ? OFFSET ?",
            (zoneid, DIALOG_PAGE_SIZE, offset),
        ).fetchall()
        for r in rows:
            results.append({"zone": zone.upper(), "idx": r["idx"], "text": r["text"]})
    if q:
        if q.isdigit():
            # Dialog id lookup -- exact idx match, not a text search. Across all zones unless a
            # zone is picked, since the same numeric id means something different per zone.
            count_sql = "SELECT COUNT(*) FROM dialog_text WHERE idx = ?"
            sql = "SELECT zoneid, idx, text FROM dialog_text WHERE idx = ?"
            params = [int(q)]
            if zoneid is not None:
                count_sql += " AND zoneid = ?"
                sql += " AND zoneid = ?"
                params.append(zoneid)
            total = con.execute(count_sql, params).fetchone()[0]
            sql += " ORDER BY zoneid LIMIT ? OFFSET ?"
            rows = con.execute(sql, params + [DIALOG_PAGE_SIZE, offset]).fetchall()
        else:
            count_sql = "SELECT COUNT(*) FROM dialog_text_fts WHERE dialog_text_fts MATCH ?"
            sql = "SELECT zoneid, idx, text FROM dialog_text_fts WHERE dialog_text_fts MATCH ?"
            params = [q]
            if zoneid is not None:
                count_sql += " AND zoneid = ?"
                sql += " AND zoneid = ?"
                params.append(zoneid)
            sql += " LIMIT ? OFFSET ?"
            try:
                total = con.execute(count_sql, params).fetchone()[0]
                rows = con.execute(sql, params + [DIALOG_PAGE_SIZE, offset]).fetchall()
            except sqlite3.OperationalError:
                rows = []
        for r in rows:
            zname = con.execute("SELECT name FROM zones WHERE zoneid = ?", (r["zoneid"],)).fetchone()
            results.append({"zone": zname[0] if zname else "?", "idx": r["idx"], "text": r["text"]})

    total_pages = max(1, (total + DIALOG_PAGE_SIZE - 1) // DIALOG_PAGE_SIZE)
    zones = con.execute("SELECT zoneid, name FROM zones WHERE zoneid > 0 ORDER BY name").fetchall()
    con.close()
    return templates.TemplateResponse(request, "dialog.html", {
        "q": q, "zone": zone, "results": results, "zones": zones,
        "page": page, "total_pages": total_pages, "total": total, "jump_id": jump_id,
    })


@app.get("/zone/{zone_name}/drift", response_class=HTMLResponse)
def zone_drift(request: Request, zone_name: str):
    con = get_con()
    zones = con.execute("SELECT zoneid, name FROM zones WHERE zoneid > 0 ORDER BY name").fetchall()
    zoneid_row = con.execute("SELECT zoneid FROM zones WHERE name = ?", (zone_name.upper(),)).fetchone()
    zoneid = zoneid_row[0] if zoneid_row else None
    rows = []
    content_tags = ""
    if zoneid is not None:
        rows = con.execute(
            """SELECT constant_name, wired_id, real_text, commented_text, status, zone_content_tags
               FROM dialog_drift_report WHERE zoneid = ? ORDER BY
               CASE status WHEN 'mismatch' THEN 0 WHEN 'no_real_entry' THEN 1
                            WHEN 'unannotated' THEN 2 ELSE 3 END, wired_id""",
            (zoneid,),
        ).fetchall()
        if rows:
            content_tags = rows[0]["zone_content_tags"] or ""
    con.close()
    return templates.TemplateResponse(request, "drift.html", {
        "zone_name": zone_name, "rows": rows, "content_tags": content_tags, "zones": zones,
    })


@app.get("/missions", response_class=HTMLResponse)
def missions(request: Request, q: str = ""):
    con = get_con()
    if q:
        rows = con.execute(
            "SELECT mission_id, name, full_text FROM assault_missions WHERE name LIKE ? ORDER BY mission_id",
            (f"%{q}%",),
        ).fetchall()
    else:
        rows = con.execute(
            "SELECT mission_id, name, full_text FROM assault_missions ORDER BY mission_id"
        ).fetchall()
    rollups = {r["mission_id"]: entity_profile.get_mission_rollup(con, r["mission_id"], r["name"]) for r in rows}
    con.close()
    return templates.TemplateResponse(request, "missions.html", {"q": q, "rows": rows, "rollups": rollups})


KEYITEMS_PAGE_SIZE = 100


@app.get("/keyitems", response_class=HTMLResponse)
def keyitems(request: Request, q: str = "", page: int = 1):
    con = get_con()
    rows = []
    total = 0
    total_pages = 1
    if q:
        page = max(1, page)
        offset = (page - 1) * KEYITEMS_PAGE_SIZE
        total = con.execute(
            "SELECT COUNT(*) FROM key_items WHERE name LIKE ?", (f"%{q}%",)
        ).fetchone()[0]
        total_pages = max(1, (total + KEYITEMS_PAGE_SIZE - 1) // KEYITEMS_PAGE_SIZE)
        ki_rows = con.execute(
            "SELECT keyitem_id, name, plural, description FROM key_items WHERE name LIKE ? "
            "ORDER BY name LIMIT ? OFFSET ?",
            (f"%{q}%", KEYITEMS_PAGE_SIZE, offset),
        ).fetchall()
        topaz_ready = backport_enabled()
        for r in ki_rows:
            readiness = ingest_global_tables.resolve_keyitem_readiness(con, r["keyitem_id"], r["name"])
            # Backport-module-only extra check -- skipped entirely (no query run) when the user
            # has no Topaz/DSP checkout configured, so the core module's page stays fast for a
            # typical LSB-only user.
            topaz_readiness = (
                ingest_global_tables.resolve_keyitem_readiness(
                    con, r["keyitem_id"], r["name"], table="topaz_keyitems"
                ) if topaz_ready else None
            )
            # Joined by NAME, not id -- capture_ki_events.keyitem_id is whatever real id the
            # client itself reported live, which is exactly what's known to drift from
            # key_items.keyitem_id (this row's own readiness check above proves it: e.g. "map of
            # Ilrusi Atoll" is id 2763 in key_items but the client-observed real id is 1869).
            # Name is the one field both sources get from real client text, so it's the
            # reliable join key here, not either id.
            capture_events = con.execute(
                """SELECT capture_id, event_type, x, y, z, zone_name FROM capture_ki_events
                   WHERE LOWER(keyitem_name) = LOWER(?) ORDER BY capture_id""",
                (r["name"],),
            ).fetchall()
            rows.append({
                "keyitem_id": r["keyitem_id"], "name": r["name"], "plural": r["plural"],
                "description": r["description"], "readiness": readiness,
                "topaz_readiness": topaz_readiness,
                "capture_events": capture_events,
            })
    con.close()
    return templates.TemplateResponse(request, "keyitems.html", {
        "q": q, "rows": rows, "page": page, "total": total, "total_pages": total_pages,
    })


ZONE_BROWSE_PAGE_SIZE = 100


@app.get("/zones", response_class=HTMLResponse)
def zones_browse(request: Request, zone: str = "", tag: str = "", page: int = 1):
    """Zone/content_tag entity/mob browser -- either filter works alone or combined (zone only,
    tag only across every zone, or both narrowed together); at least one must be set to run a
    query at all. content_tag is a real server-side content-category flag from sql/npc_list.sql
    (e.g. TOAU/SOA), NOT proof of mission membership. Each result links to its own /entity
    profile. Replaces the old tag-primary /tags page (tag search -> zone list only, no entities)."""
    con = get_con()
    zones = con.execute("SELECT zoneid, name FROM zones WHERE zoneid > 0 ORDER BY name").fetchall()
    all_tags = con.execute(
        """SELECT content_tag, COUNT(*) AS n FROM npc_names WHERE content_tag IS NOT NULL
           GROUP BY content_tag ORDER BY content_tag"""
    ).fetchall()

    entities = []
    total = 0
    total_pages = 1
    zoneid = None
    if zone:
        zrow = con.execute("SELECT zoneid FROM zones WHERE name = ?", (zone.upper(),)).fetchone()
        zoneid = zrow[0] if zrow else None
    show_zone_col = zoneid is None  # tag-only (or no filter) spans multiple zones -- show which one
    if zoneid is not None or tag:
        page = max(1, page)
        offset = (page - 1) * ZONE_BROWSE_PAGE_SIZE
        where = []
        params = []
        if zoneid is not None:
            where.append("n.zoneid=?")
            params.append(zoneid)
        if tag:
            where.append("n.content_tag=?")
            params.append(tag)
        where_sql = " AND ".join(where)
        count_sql = f"SELECT COUNT(*) FROM npc_names n WHERE {where_sql}"
        sql = f"""SELECT n.npcid, n.name, n.content_tag, z.name AS zone_name
                  FROM npc_names n JOIN zones z ON z.zoneid = n.zoneid WHERE {where_sql}"""
        total = con.execute(count_sql, params).fetchone()[0]
        total_pages = max(1, (total + ZONE_BROWSE_PAGE_SIZE - 1) // ZONE_BROWSE_PAGE_SIZE)
        sql += " ORDER BY z.name, n.name LIMIT ? OFFSET ?"
        entities = con.execute(sql, params + [ZONE_BROWSE_PAGE_SIZE, offset]).fetchall()
    con.close()
    return templates.TemplateResponse(request, "zones_browse.html", {
        "zone": zone, "tag": tag, "zones": zones, "all_tags": all_tags,
        "entities": entities, "total": total, "page": page, "total_pages": total_pages,
        "show_zone_col": show_zone_col,
    })


@app.get("/gaps", response_class=HTMLResponse)
def gaps_browse(request: Request, zone: str = "", mode: str = "zero_position"):
    con = get_con()
    zones = con.execute("SELECT zoneid, name FROM zones WHERE zoneid > 0 ORDER BY name").fetchall()
    rows = []
    if zone:
        zoneid = build_sql_index.resolve_zoneid_for_report(con, zone)
        if zoneid is not None:
            if mode == "unregistered":
                rows = build_sql_index.query_unregistered(con, zoneid)
            else:
                rows = build_sql_index.query_zero_position(con, zoneid)
    con.close()
    return templates.TemplateResponse(request, "gaps.html", {
        "zone": zone, "mode": mode, "zones": zones, "rows": rows,
    })


SQL_TABLES = {
    # "entity_col" names the column (if any) that's a real npcid -- confirmed live that the SQL
    # Browser rendered every column as plain text with no link to Entity Lookup, even for tables
    # whose id genuinely IS an npcid (npc_list.npcid, mob_spawn_points.mobid, instance_entities.id
    # all reference the same real npc_list/mob entity space). groupid/poolid/instanceid are real
    # ids too, but into different tables (mob_groups/mob_pools/instance_list respectively, not
    # Entity Lookup), so those deliberately get no entity_col.
    "npc_list": {
        "table": "sql_npc_list", "id_col": "npcid", "name_col": "name", "entity_col": "npcid",
        "cols": ["npcid", "name", "polutils_name", "pos_x", "pos_y", "pos_z", "content_tag"],
    },
    "mob_spawn_points": {
        "table": "sql_mob_spawn_points", "id_col": "mobid", "name_col": "mobname", "entity_col": "mobid",
        "cols": ["mobid", "mobname", "polutils_name", "groupid", "pos_x", "pos_y", "pos_z"],
    },
    "mob_groups": {
        "table": "sql_mob_groups", "id_col": "groupid", "name_col": "name", "entity_col": None,
        "cols": ["zoneid", "groupid", "poolid", "name", "respawntime", "minLevel", "maxLevel"],
    },
    "mob_pools": {
        "table": "sql_mob_pools", "id_col": "poolid", "name_col": "name", "entity_col": None,
        "cols": ["poolid", "name", "packet_name", "familyid"],
    },
    "instance_entities": {
        "table": "sql_instance_entities", "id_col": "id", "name_col": None, "entity_col": "id",
        "cols": ["instanceid", "id"],
    },
    "instance_list": {
        "table": "sql_instance_list", "id_col": "instanceid", "name_col": "instance_name", "entity_col": None,
        "cols": ["instanceid", "instance_name", "instance_zone", "entrance_zone", "start_x", "start_y", "start_z"],
    },
}


# Every real capture_* table (excluding "captures" itself, already served by /captures and
# /captures/{id}) -- id_col/name_col name a real column worth an exact-id/substring-name filter
# when one exists, matching SQL_TABLES' own pattern above. Columns themselves are read live via
# PRAGMA table_info() rather than hardcoded here (see capture_query_columns()) since these tables
# have many real columns (capture_npc_entries alone has 23) and a hardcoded list would be one more
# thing to drift out of sync with build_capture_index.py's own init_db(), the same class of bug
# this project has already hit more than once with sql_*/lsb_*/topaz_* schema assumptions.
CAPTURE_QUERY_TABLES = {
    "capture_npc_entries": {"id_col": "entity_id", "name_col": "name"},
    "capture_npc_history": {"id_col": "entity_id", "name_col": None},
    "capture_npc_path": {"id_col": "entity_id", "name_col": None},
    "capture_actions": {"id_col": "actor", "name_col": "name"},
    "capture_hp_events": {"id_col": None, "name_col": "mob_name"},
    "capture_events": {"id_col": "entity_id", "name_col": "entity_name"},
    "capture_ki_events": {"id_col": "keyitem_id", "name_col": "keyitem_name"},
    "capture_eventview": {"id_col": "entity_id", "name_col": None},
    "capture_level_range": {"id_col": "entity_id", "name_col": "name"},
    "capture_attack_delay": {"id_col": None, "name_col": "mob_name"},
    "capture_pc_path": {"id_col": None, "name_col": None},
    "capture_raw_packets": {"id_col": None, "name_col": "opcode"},
    "capture_caplog_chat": {"id_col": None, "name_col": "text"},
    "capture_tags": {"id_col": None, "name_col": "tag"},
    "capture_source_files": {"id_col": None, "name_col": "filename"},
}
CAPTURE_QUERY_PAGE_SIZE = 200


def capture_query_columns(con, table: str) -> list[str]:
    return [r[1] for r in con.execute(f"PRAGMA table_info({table})").fetchall()]


def build_capture_query_sql(table: str, cols: list[str], spec: dict, capture_id: int | None, q: str):
    """Shared WHERE/params builder for both the paginated HTML view and the unpaginated CSV export
    below -- one real query definition, so the CSV export can never silently drift from what the
    HTML page actually shows for the same filters."""
    where = ["1=1"]
    params: list = []
    if capture_id is not None:
        where.append("capture_id = ?")
        params.append(capture_id)
    if q:
        id_col, name_col = spec["id_col"], spec["name_col"]
        if id_col and q.lstrip("-").isdigit():
            where.append(f"{id_col} = ?")
            params.append(int(q))
        elif name_col:
            where.append(f"{name_col} LIKE ?")
            params.append(f"%{q}%")
        else:
            where.append("0")  # no filterable column for this q -- real zero rows, not "ignore the filter"
    return f"SELECT {', '.join(cols)} FROM {table} WHERE {' AND '.join(where)}", params


@app.get("/captures/query", response_class=HTMLResponse)
def captures_query(request: Request, table: str = "capture_npc_entries", capture_id: str = "",
                    q: str = "", page: int = 1):
    if table not in CAPTURE_QUERY_TABLES:
        table = "capture_npc_entries"
    spec = CAPTURE_QUERY_TABLES[table]
    cid = int(capture_id) if capture_id.strip().lstrip("-").isdigit() else None
    con = get_con()
    cols = capture_query_columns(con, table)
    base_sql, params = build_capture_query_sql(table, cols, spec, cid, q)

    total = con.execute(f"SELECT COUNT(*) FROM ({base_sql})", params).fetchone()[0]
    total_pages = max(1, (total + CAPTURE_QUERY_PAGE_SIZE - 1) // CAPTURE_QUERY_PAGE_SIZE)
    page = max(1, min(page, total_pages))
    offset = (page - 1) * CAPTURE_QUERY_PAGE_SIZE
    order_col = "capture_id" if "capture_id" in cols else cols[0]
    rows = con.execute(
        f"{base_sql} ORDER BY {order_col} LIMIT ? OFFSET ?", params + [CAPTURE_QUERY_PAGE_SIZE, offset]
    ).fetchall()
    con.close()

    return templates.TemplateResponse(request, "capture_query.html", {
        "table": table, "tables": list(CAPTURE_QUERY_TABLES.keys()), "capture_id": capture_id,
        "q": q, "cols": cols, "rows": rows, "page": page, "total": total, "total_pages": total_pages,
    })


@app.get("/captures/query.csv")
def captures_query_csv(table: str = "capture_npc_entries", capture_id: str = "", q: str = ""):
    """Same real filters as /captures/query above (shared query builder, not reimplemented) --
    exports the FULL matching result set, not just the current page, since the point of a CSV
    export is taking the real data elsewhere, not mirroring the in-browser page size."""
    if table not in CAPTURE_QUERY_TABLES:
        table = "capture_npc_entries"
    spec = CAPTURE_QUERY_TABLES[table]
    cid = int(capture_id) if capture_id.strip().lstrip("-").isdigit() else None
    con = get_con()
    cols = capture_query_columns(con, table)
    base_sql, params = build_capture_query_sql(table, cols, spec, cid, q)
    order_col = "capture_id" if "capture_id" in cols else cols[0]
    rows = con.execute(f"{base_sql} ORDER BY {order_col}", params).fetchall()
    con.close()

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(cols)
    for r in rows:
        writer.writerow([r[c] for c in cols])
    filename = f"{table}.csv"
    return Response(
        content=buf.getvalue(), media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/captures/{capture_id}/export.zip")
def captures_export_zip(capture_id: int):
    """One CSV per capture_* table that has any real rows for this capture, bundled into a single
    zip -- "get all of this capture's own data out," the direct counterpart to /captures/query.csv's
    "get one filtered slice out across captures." Tables with zero rows for this capture are
    skipped rather than included empty, so the zip's contents tell you at a glance what this
    specific capture actually has data for."""
    con = get_con()
    row = con.execute("SELECT capture_id, capture_label FROM captures WHERE capture_id=?", (capture_id,)).fetchone()
    if not row:
        con.close()
        return HTMLResponse("Capture not found", status_code=404)
    label = row["capture_label"] or f"capture_{capture_id}"

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for table in CAPTURE_QUERY_TABLES:
            cols = capture_query_columns(con, table)
            rows = con.execute(
                f"SELECT {', '.join(cols)} FROM {table} WHERE capture_id = ?", (capture_id,)
            ).fetchall()
            if not rows:
                continue
            csv_buf = io.StringIO()
            writer = csv.writer(csv_buf)
            writer.writerow(cols)
            for r in rows:
                writer.writerow([r[c] for c in cols])
            zf.writestr(f"{table}.csv", csv_buf.getvalue())
    con.close()

    safe_label = re.sub(r'[^\w\-. ]', '_', label)[:80]
    filename = f"capture_{capture_id}_{safe_label}.zip"
    return Response(
        content=buf.getvalue(), media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


SQL_PAGE_SIZE = 200


@app.get("/sql", response_class=HTMLResponse)
def sql_browse(request: Request, q: str = "", table: str = "npc_list", page: int = 1):
    if table not in SQL_TABLES:
        table = "npc_list"
    spec = SQL_TABLES[table]
    con = get_con()
    rows = []
    total = 0
    total_pages = 1
    page = max(1, page)
    if q:
        cols_sql = ", ".join(spec["cols"])
        if q.lstrip("-").isdigit():
            where_sql = f"{spec['id_col']} = ?"
            params = [int(q)]
        elif spec["name_col"]:
            where_sql = f"{spec['name_col']} LIKE ?"
            params = [f"%{q}%"]
        else:
            where_sql = None
            params = []
        if where_sql:
            total = con.execute(f"SELECT COUNT(*) FROM {spec['table']} WHERE {where_sql}", params).fetchone()[0]
            total_pages = max(1, (total + SQL_PAGE_SIZE - 1) // SQL_PAGE_SIZE)
            offset = (page - 1) * SQL_PAGE_SIZE
            sql = f"SELECT {cols_sql} FROM {spec['table']} WHERE {where_sql} LIMIT ? OFFSET ?"
            rows = con.execute(sql, params + [SQL_PAGE_SIZE, offset]).fetchall()
    con.close()
    return templates.TemplateResponse(request, "sql.html", {
        "q": q, "table": table, "tables": list(SQL_TABLES.keys()), "cols": spec["cols"], "rows": rows,
        "page": page, "total": total, "total_pages": total_pages, "entity_col": spec["entity_col"],
    })


def load_zone_events(zone_folder_name: str) -> list[dict]:
    """Reads this zone's cached events.yml (mission_toolkit.py output) into
    [{"entity_id": N, "event_ids": [...]}], generating the export first if not cached yet."""
    events_yml = TOOLS_ROOT / "mission_reports" / zone_folder_name / "events.yml"
    if not events_yml.exists():
        # Real bug fixed here: this used to hardcode explore_event.DEFAULT_FFXI_PATH (this
        # project's own dev machine's path, "C:/ValhallaXI/..."), completely ignoring whatever
        # ffxi_install_path a user actually configured on the Settings page -- confirmed live,
        # this was the only two call sites in the whole app that bypassed settings.get_ffxi_install()
        # instead of reading it like every other route does.
        ffxi_path = settings_mod.get_ffxi_install() or explore_event.DEFAULT_FFXI_PATH
        explore_event.ensure_export(zone_folder_name, ffxi_path)
    if not events_yml.exists():
        return []
    doc = yaml.safe_load(events_yml.read_text(encoding="utf-8"))
    return [
        {"entity_id": b.get("entity_id"), "event_ids": [e["id"] for e in b.get("events", [])]}
        for b in doc.get("blocks", []) if b.get("entity_id")
    ]


@app.get("/events", response_class=HTMLResponse)
def events_browse(request: Request, zone: str = "", q: str = ""):
    con = get_con()
    zones = con.execute("SELECT zoneid, name FROM zones WHERE zoneid > 0 ORDER BY name").fetchall()
    rows = []
    generated_note = None
    if zone:
        events_yml = TOOLS_ROOT / "mission_reports" / zone / "events.yml"
        was_cached = events_yml.exists()
        blocks = load_zone_events(zone)
        if not was_cached and events_yml.exists():
            generated_note = f"Generated a fresh events export for {zone} via mission_toolkit.py."
        zoneid_row = con.execute("SELECT zoneid FROM zones WHERE name = ?", (zone.upper(),)).fetchone()
        zoneid = zoneid_row[0] if zoneid_row else None
        for b in blocks:
            entity_id = b["entity_id"]
            name_row = None
            if zoneid is not None:
                name_row = con.execute(
                    "SELECT name FROM npc_names WHERE zoneid = ? AND npcid = ?", (zoneid, entity_id)
                ).fetchone()
            name = name_row[0] if name_row else None
            if q and q.lower() not in str(entity_id).lower() and (not name or q.lower() not in name.lower()):
                continue
            for eid in b["event_ids"]:
                if eid == 65535:  # LSB/Topaz sentinel for "no event", not a real CSID
                    continue
                rows.append({"entity_id": entity_id, "name": name, "csid": eid})
    con.close()
    return templates.TemplateResponse(request, "events.html", {
        "zone": zone, "q": q, "zones": zones, "rows": rows, "generated_note": generated_note,
    })


@app.get("/events/view", response_class=HTMLResponse)
def events_view(request: Request, zone: str, entity: int, csid: int):
    con = get_con()
    zoneid_row = con.execute("SELECT zoneid FROM zones WHERE name = ?", (zone.upper(),)).fetchone()
    zoneid = zoneid_row[0] if zoneid_row else None
    out_dir = explore_event.ensure_export(zone, settings_mod.get_ffxi_install() or explore_event.DEFAULT_FFXI_PATH)
    result = explore_event_run(out_dir, entity, csid, zoneid)
    checks = []
    if zoneid is not None and result["decompiled"]:
        checks = explore_event.cross_check(con, zoneid, result["decompiled"])
    con.close()
    return templates.TemplateResponse(request, "event_view.html", {
        "zone": zone, "entity": entity, "csid": csid,
        "decompiled": result["decompiled"], "error": result["error"], "checks": checks,
    })


def explore_event_run(out_dir: Path, entity_id: int, csid: int, zoneid: int | None) -> dict:
    import subprocess, sys as _sys
    result = subprocess.run(
        [_sys.executable, str(explore_event.XI_EVENTS_BRIDGE), str(out_dir / "events.yml"),
         str(entity_id), str(csid), str(out_dir / "dialog.yml"), str(zoneid or 0)],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        return {"decompiled": None, "error": (result.stdout + "\n" + result.stderr).strip()}
    return {"decompiled": result.stdout, "error": None}


@app.get("/packets", response_class=HTMLResponse)
def packets_browse(request: Request, q: str = "", direction: str = "s2c"):
    """List-only page now -- decoding a specific opcode lives at its own URL (/packets/decode),
    same fix as /captures and /entity: clicking "use" on a row used to reload this same page and
    snap scroll back to the top of a potentially long opcode list; a real separate destination
    means the browser's back button restores this list's scroll position on its own."""
    opcodes = packet_decode.list_opcodes(q)
    return templates.TemplateResponse(request, "packets.html", {
        "q": q, "direction": direction, "opcodes": opcodes,
    })


@app.get("/packets/decode", response_class=HTMLResponse)
def packets_decode(request: Request, direction: str = "s2c", opcode: str = "", hex_bytes: str = "", q: str = ""):
    decoded = None
    decode_error = None
    schema = None
    opcode_int = None
    if opcode:
        try:
            opcode_int = int(opcode, 0)
        except ValueError:
            decode_error = f"'{opcode}' isn't a valid opcode (expected e.g. 0x034 or 52)."
    if opcode_int is not None:
        # Real field schema for this opcode -- shown as soon as an opcode is picked, whether or
        # not hex has been entered yet, so this doubles as a standing field reference (name/type/
        # offset/lookup) rather than only ever showing something once a decode succeeds.
        schema = packet_decode.get_field_schema(direction, opcode_int)
        if hex_bytes:
            try:
                result = packet_decode.decode(direction, opcode_int, hex_bytes)
                decoded_by_name = {f.name: f for f in result.fields}
                decoded = {
                    "description": result.description,
                    "has_definition": result.has_definition,
                    "fields": [
                        {"name": f.name, "type": f.type, "value": f.display_value,
                         "out_of_range": f.out_of_range, "comment": f.comment}
                        for f in result.fields
                    ],
                }
                # Populate the same schema reference table with real decoded values, rather than
                # showing a second, separate results table -- "select an opcode, see its fields,
                # then watch them fill in once decoded" as one continuous table, not two.
                if schema:
                    for row in schema:
                        f = decoded_by_name.get(row["name"])
                        if f is not None:
                            row["value"] = f.display_value
                            row["out_of_range"] = f.out_of_range
            except Exception as e:
                decode_error = str(e)
    return templates.TemplateResponse(request, "packets_decode.html", {
        "q": q, "direction": direction, "opcode": opcode, "hex_bytes": hex_bytes,
        "decoded": decoded, "decode_error": decode_error, "schema": schema,
    })


@app.get("/packets/bulk", response_class=HTMLResponse)
def packets_bulk_form(request: Request):
    return templates.TemplateResponse(request, "packets_bulk.html", {
        "direction": "s2c", "opcode": "", "log_text": "", "rows": None, "parse_error": None,
    })


@app.post("/packets/bulk", response_class=HTMLResponse)
async def packets_bulk_submit(request: Request):
    """Decode every real packet in one pasted raw PacketLogger/PacketViewer per-opcode log file at
    once -- reuses build_capture_index.parse_packetlogger_log (the exact same real hex-dump-block
    parser the actual capture ingestion pipeline uses), so this gets a chance to catch/inspect a
    log BEFORE committing to a full capture ingest, not a second parser that could drift from it."""
    form = await request.form()
    direction = form.get("direction", "s2c")
    opcode = (form.get("opcode") or "").strip()
    log_text = form.get("log_text") or ""
    rows = None
    parse_error = None
    if opcode and log_text.strip():
        try:
            opcode_norm = f"0x{int(opcode, 0):03X}"
            pairs = build_capture_index.parse_packetlogger_log(log_text, opcode_norm)
            opcode_int = int(opcode, 0)
            rows = []
            for ts, hex_bytes in pairs:
                try:
                    result = packet_decode.decode(direction, opcode_int, hex_bytes)
                    rows.append({
                        "ts": ts, "raw_hex": hex_bytes, "description": result.description,
                        "fields": [{"name": f.name, "value": f.display_value, "out_of_range": f.out_of_range}
                                   for f in result.fields],
                        "decode_error": None,
                    })
                except Exception as e:
                    rows.append({"ts": ts, "raw_hex": hex_bytes, "description": None, "fields": [], "decode_error": str(e)})
            if not rows:
                parse_error = ("No real packet blocks found in this text -- expected the real "
                                "PacketLogger/PacketViewer per-opcode log shape ('[timestamp]' or "
                                "'[timestamp] Packet 0xNNN' header followed by a 16-column hex grid).")
        except Exception as e:
            parse_error = str(e)
    return templates.TemplateResponse(request, "packets_bulk.html", {
        "direction": direction, "opcode": opcode, "log_text": log_text,
        "rows": rows, "parse_error": parse_error,
    })


@app.get("/wiki", response_class=HTMLResponse)
def wiki_browse(request: Request, title: str = ""):
    report = None
    if title:
        con = get_con()
        report = wiki_compile.compile_report(con, title)
        con.close()
    return templates.TemplateResponse(request, "wiki.html", {"title": title, "report": report})


@app.get("/wiki/export", response_class=PlainTextResponse)
def wiki_export(title: str = ""):
    con = get_con()
    report = wiki_compile.compile_report(con, title)
    con.close()
    return PlainTextResponse(wiki_compile.to_markdown(report), media_type="text/markdown")


@app.get("/captures", response_class=HTMLResponse)
def captures_page(request: Request, content_type: str = "", tag: str = "", q: str = ""):
    """List-only page -- detail lives at its own URL (/captures/{id}) specifically so clicking a
    row is a real navigation, not a query-param reload of this same page. That was the actual
    complaint: browser back-navigation restores scroll position on a real URL change, but a
    same-page reload (old ?capture_id=... approach) always snapped back to the top."""
    con = get_con()
    sql = "SELECT * FROM captures WHERE 1=1"
    params = []
    if content_type:
        sql += " AND content_type=?"
        params.append(content_type)
    if tag:
        sql += " AND capture_id IN (SELECT capture_id FROM capture_tags WHERE tag=?)"
        params.append(tag)
    if q:
        sql += " AND (mission_name LIKE ? OR capture_label LIKE ?)"
        params.extend([f"%{q}%", f"%{q}%"])
    sql += " ORDER BY content_type, capture_id"
    rows = []
    for row in con.execute(sql, params).fetchall():
        d = dict(row)
        d["zones"] = json.loads(d["zones"]) if d.get("zones") else []
        d["n_npc"] = con.execute(
            "SELECT COUNT(*) FROM capture_npc_entries WHERE capture_id=?", (d["capture_id"],)
        ).fetchone()[0]
        d["tags"] = build_capture_index.get_capture_tags(con, d["capture_id"])
        rows.append(d)
    content_types = [r[0] for r in con.execute(
        "SELECT DISTINCT content_type FROM captures ORDER BY 1").fetchall()]
    missions = [r[0] for r in con.execute(
        "SELECT DISTINCT mission_name FROM captures WHERE mission_name IS NOT NULL ORDER BY 1").fetchall()]
    con.close()
    return templates.TemplateResponse(request, "captures.html", {
        "rows": rows, "content_type": content_type, "content_types": content_types,
        "tag": tag, "all_tags": build_capture_index.CAPTURE_TAGS,
        "q": q, "missions": missions,
    })


def zoneid_for_zone_db(con, zone_db: str) -> int | None:
    """capture_npc_entries.zone_db is the NPCLogger.db filename stem, spaced ("Ilrusi Atoll");
    zones.name is Topaz's own SCREAMING_SNAKE form ("ILRUSI_ATOLL"). Normalize both to compare."""
    norm = zone_db.upper().replace(" ", "_").replace("'", "")
    row = con.execute("SELECT zoneid FROM zones WHERE REPLACE(name, ' ', '_') = ?", (norm,)).fetchone()
    return row[0] if row else None


@app.get("/zones/{zoneid}/view3d", response_class=HTMLResponse)
def zone_view3d(request: Request, zoneid: int, capture_id: int = 0, entity_id: int = 0,
                 pc: int = 0, zone_db: str = ""):
    """Real 3D viewer over the zone's own visual mesh (build_zone_visual_cache.py), vanilla
    Three.js loaded via CDN (no build step, matching this app's existing no-bundler approach) --
    ported from studying Soverance/Vanalytics' React Three Fiber viewer (MIT), not copy-pasted:
    react-three-fiber/drei have no CDN/UMD build, so the scene setup here is hand-written directly
    against Three.js, informed by Vanalytics' approach (place markers in the real 3D mesh, orbit
    camera, basic lighting) rather than its exact code."""
    con = get_con()
    zone_row = con.execute("SELECT name FROM zones WHERE zoneid=?", (zoneid,)).fetchone()
    zone_name = zone_row[0] if zone_row else f"zone {zoneid}"

    paths = []
    entity_name = None
    if pc and capture_id and zone_db:
        pts = get_pc_path_with_y(con, capture_id, zone_db)
        entity_name = "PC trace"
        if pts:
            paths = [{"name": "PC trace", "color": "#e0c840", "points": pts}]
    elif capture_id and entity_id:
        entry = con.execute(
            "SELECT name FROM capture_npc_entries WHERE capture_id=? AND entity_id=?",
            (capture_id, entity_id)).fetchone()
        entity_name = entry[0] if entry else None
        pts = get_entity_path_with_y(con, capture_id, entity_id)
        if pts:
            paths = [{"name": entity_name or str(entity_id), "color": "#5fb3ac", "points": pts}]
    con.close()

    obj_available = (ZONE_VISUAL_DIR / f"{zoneid}.obj").exists()
    return templates.TemplateResponse(request, "zone_view3d.html", {
        "zoneid": zoneid, "zone_name": zone_name, "capture_id": capture_id, "entity_id": entity_id,
        "entity_name": entity_name, "paths_json": json.dumps(paths), "legend": paths,
        "obj_available": obj_available, "pc": pc, "zone_db": zone_db,
    })


def get_entity_path_with_y(con, capture_id: int, entity_id: int) -> list[dict]:
    """Same real points as build_capture_index.get_entity_path, but with real y (height) put
    back in -- that function drops y for the 2D top-down plot, the 3D view can actually use it."""
    pts = build_capture_index.get_entity_path(con, capture_id, entity_id)
    y_by_step = {}
    rows = con.execute(
        "SELECT step, y FROM capture_npc_path WHERE capture_id=? AND entity_id=? ORDER BY step",
        (capture_id, entity_id)).fetchall()
    for i, (step, y) in enumerate(rows):
        y_by_step[i] = y
    return [{"x": x, "y": y_by_step.get(i, 0) or 0, "z": z} for i, (x, z, _t) in enumerate(pts)]


def get_pc_path_with_y(con, capture_id: int, zone_db: str) -> list[dict]:
    """Same shape as get_entity_path_with_y, for the capturing character's own trace."""
    rows = con.execute(
        "SELECT x, y, z FROM capture_pc_path WHERE capture_id=? AND zone_db=? ORDER BY step",
        (capture_id, zone_db)).fetchall()
    return [{"x": x, "y": y or 0, "z": z} for x, y, z in rows]


@app.post("/zones/{zoneid}/build_visual_cache")
def zone_build_visual_cache(request: Request, zoneid: int, return_to: str = Form("/")):
    """Runs build_zone_visual_cache.build_one synchronously (a real zone parse, ~10-60s depending
    on zone size) and redirects back to whichever 3D view sent the request -- lets a user get an
    uncached zone's mesh without dropping to a terminal, no separate job queue needed for a
    single-user local tool."""
    ffxi_path = settings_mod.get_ffxi_install()
    if not ffxi_path:
        return PlainTextResponse("Could not find FFXI install -- set ffxi_install_path in Settings.", status_code=400)
    con = get_con()
    ok = build_zone_visual_cache.build_one(con, zoneid, ffxi_path)
    con.close()
    if not ok:
        return PlainTextResponse(f"Failed to build visual mesh cache for zoneid {zoneid} -- check server log.", status_code=500)
    return RedirectResponse(url=return_to, status_code=303)


@app.get("/zones/{zoneid}/view3d_all", response_class=HTMLResponse)
def zone_view3d_all(request: Request, zoneid: int, capture_id: int, zone_db: str = ""):
    """Multi-entity version of zone_view3d -- every entity with path data in one capture+zone
    plotted together in the real 3D mesh, each a deterministic distinct color, same real
    coordinate-aligned approach as /captures/plot_all's 2D version (and the same MULTI_PLOT_LIMIT
    cap for legibility)."""
    con = get_con()
    cap = con.execute("SELECT zones FROM captures WHERE capture_id=?", (capture_id,)).fetchone()
    zones = json.loads(cap["zones"]) if cap and cap["zones"] else []
    zone_db = zone_db or (zones[0] if zones else "")

    # The zone-switcher dropdown only resubmits zone_db -- the URL's {zoneid} path segment is
    # stale until we redirect, otherwise the mesh (loaded straight from {{ zoneid }}.obj) stays
    # on whatever zone the page first loaded with while the plotted paths silently switch to the
    # newly selected zone's data, drawing them over the WRONG mesh.
    resolved_zoneid = zoneid_for_zone_db(con, zone_db) if zone_db else None
    if resolved_zoneid and resolved_zoneid != zoneid:
        con.close()
        from urllib.parse import quote
        return RedirectResponse(
            url=f"/zones/{resolved_zoneid}/view3d_all?capture_id={capture_id}&zone_db={quote(zone_db)}",
            status_code=303)

    zone_row = con.execute("SELECT name FROM zones WHERE zoneid=?", (zoneid,)).fetchone()
    zone_name = zone_row[0] if zone_row else f"zone {zoneid}"

    entities = build_capture_index.get_capture_entity_ids_with_path(con, capture_id, zone_db) if zone_db else []
    paths = []
    for i, (eid, name) in enumerate(entities[:MULTI_PLOT_LIMIT]):
        pts = get_entity_path_with_y(con, capture_id, eid)
        if pts:
            r, g, b = distinct_color(i, len(entities))
            paths.append({"name": name or str(eid), "color": f"rgb({r},{g},{b})", "points": pts})
    con.close()

    obj_available = (ZONE_VISUAL_DIR / f"{zoneid}.obj").exists()
    return templates.TemplateResponse(request, "zone_view3d.html", {
        "zoneid": zoneid, "zone_name": zone_name, "capture_id": capture_id, "entity_id": 0,
        "entity_name": None, "paths_json": json.dumps(paths), "legend": paths,
        "obj_available": obj_available, "multi": True, "zone_db": zone_db, "zones": zones,
        "truncated": len(entities) > MULTI_PLOT_LIMIT, "limit": MULTI_PLOT_LIMIT,
    })


def topdown_paths(zoneid: int | None, detail: bool) -> tuple[Path, Path] | None:
    """Resolves which cached top-down PNG/JSON pair to use -- "<zoneid>_detailed.*" (visual mesh,
    denser real terrain but some zones have decorative overlay geometry like lava planes that
    render as solid blocks from directly above) when detail=True and it's actually been built,
    else "<zoneid>.*" (collision mesh, the default -- clean walkable-space outline). Falls back to
    the collision variant if detail was requested but never got a detailed cache built."""
    if zoneid is None:
        return None
    if detail:
        p = TOPDOWN_DIR / f"{zoneid}_detailed.png", TOPDOWN_DIR / f"{zoneid}_detailed.json"
        if p[0].exists() and p[1].exists():
            return p
    p = TOPDOWN_DIR / f"{zoneid}.png", TOPDOWN_DIR / f"{zoneid}.json"
    return p if p[0].exists() and p[1].exists() else None


def topdown_variants(zoneid: int | None) -> dict:
    if zoneid is None:
        return {"collision": False, "detailed": False}
    return {
        "collision": (TOPDOWN_DIR / f"{zoneid}.json").exists(),
        "detailed": (TOPDOWN_DIR / f"{zoneid}_detailed.json").exists(),
    }


@app.get("/captures/plot", response_class=HTMLResponse)
def captures_plot(request: Request, capture_id: int, entity_id: int = 0, pc: int = 0, zone_db: str = "",
                   pad_yalms: float = 200, detail: int = 0):
    con = get_con()
    cap = con.execute("SELECT * FROM captures WHERE capture_id=?", (capture_id,)).fetchone()
    if pc:
        # PC path (the capturing character's own trace) has no real entity_id -- it's keyed by
        # zone_db instead. entry is faked up just enough for the template's existing "who/where"
        # header, which otherwise expects a capture_npc_entries row.
        zones = json.loads(cap["zones"]) if cap and cap["zones"] else []
        zone_db = zone_db or (zones[0] if zones else "")
        entry = {"zone_db": zone_db, "name": None} if zone_db else None
        points = build_capture_index.get_pc_path(con, capture_id, zone_db) if zone_db else []
    else:
        entry = con.execute(
            "SELECT * FROM capture_npc_entries WHERE capture_id=? AND entity_id=?",
            (capture_id, entity_id)).fetchone()
        points = build_capture_index.get_entity_path(con, capture_id, entity_id)

    zoneid = zoneid_for_zone_db(con, entry["zone_db"]) if entry else None
    map_files = []
    if zoneid is not None and MAPS_DIR.exists():
        map_files = sorted(
            p.name for p in MAPS_DIR.glob(f"{zoneid}_*.png")
        )
    con.close()

    svg = None
    if points:
        xs = [p[0] for p in points]
        zs = [p[1] for p in points]
        pad = 20
        size = 640
        minx, maxx = min(xs), max(xs)
        minz, maxz = min(zs), max(zs)
        spanx = max(maxx - minx, 1e-6)
        spanz = max(maxz - minz, 1e-6)
        span = max(spanx, spanz)

        def sx(x):
            return pad + (x - minx) / span * (size - 2 * pad)

        def sy(z):
            return pad + (z - minz) / span * (size - 2 * pad)

        svg_points = " ".join(f"{sx(x):.1f},{sy(z):.1f}" for x, z, _ in points)
        start_x, start_z, _ = points[0]
        end_x, end_z, _ = points[-1]
        svg = {
            "size": size,
            "polyline": svg_points,
            "start": (sx(start_x), sy(start_z)),
            "end": (sx(end_x), sy(end_z)),
            "n_points": len(points),
        }

    variants = topdown_variants(zoneid)
    topdown_available = variants["collision"] or variants["detailed"]

    return templates.TemplateResponse(request, "path_plot.html", {
        "capture_id": capture_id, "entity_id": entity_id, "cap": cap, "entry": entry,
        "svg": svg, "zoneid": zoneid, "map_files": map_files,
        "topdown_available": topdown_available, "pad_yalms": pad_yalms,
        "detail": detail, "variants": variants, "pc": pc, "zone_db": zone_db,
    })


DISPLAY_SIZE = 640


@app.get("/captures/plot.png")
def captures_plot_png(capture_id: int, entity_id: int = 0, pc: int = 0, zone_db: str = "",
                       zoom: int = 1, pad_yalms: float = 200, detail: int = 0):
    """Real path drawn onto the zone's real top-down mesh silhouette, both in the same world-space
    transform (build_zone_topdown.py) -- coordinate-aligned, not a guessed overlay. detail=1 uses
    the denser visual-mesh cache instead of the default collision-mesh one (see topdown_paths).
    zoom=1 (default) crops to the path's own bounding box +/- pad_yalms, since a stitched
    multi-zone map (e.g. a full Ilrusi Atoll + Arrapago Reef mesh) makes the actual Assault-sized
    area a tiny fraction of the whole silhouette otherwise. zoom=0 returns the whole zone.
    pc=1 plots the capturing character's own PathLog trace (capture_pc_path) instead of an NPC's."""
    con = get_con()
    if pc:
        if not zone_db:
            cap = con.execute("SELECT zones FROM captures WHERE capture_id=?", (capture_id,)).fetchone()
            zones = json.loads(cap["zones"]) if cap and cap["zones"] else []
            zone_db = zones[0] if zones else ""
        points = build_capture_index.get_pc_path(con, capture_id, zone_db) if zone_db else []
        zoneid = zoneid_for_zone_db(con, zone_db) if zone_db else None
    else:
        entry = con.execute(
            "SELECT zone_db FROM capture_npc_entries WHERE capture_id=? AND entity_id=?",
            (capture_id, entity_id)).fetchone()
        points = build_capture_index.get_entity_path(con, capture_id, entity_id)
        zoneid = zoneid_for_zone_db(con, entry["zone_db"]) if entry else None
    con.close()

    paths = topdown_paths(zoneid, bool(detail))
    if not paths or not points:
        return Response(status_code=404)
    img_path, transform_path = paths

    transform = json.loads(transform_path.read_text())
    img = Image.open(img_path).convert("RGBA")
    draw = ImageDraw.Draw(img)

    pad = transform["pad"]
    span = transform["span"]
    size = transform["img_size"]
    minx = transform["minx"]
    minz = transform["minz"]
    units_per_px = span / (size - 2 * pad)

    def to_px(cap_x, cap_z):
        # transform.json's world z = -capture_z (build_zone_topdown.py's own convention,
        # matching parse_zone_collision_obj's Wavefront z-negation) -- negate here to match.
        world_z = -cap_z
        return (
            pad + (cap_x - minx) / span * (size - 2 * pad),
            pad + (world_z - minz) / span * (size - 2 * pad),
        )

    px_points = [to_px(x, z) for x, z, _ in points]
    marker_r = 2 if not zoom else max(2, min(5, int(pad_yalms / units_per_px / 20 * 0.34)))
    line_w = 2 if not zoom else max(1, marker_r // 2)
    if len(px_points) > 1:
        draw.line(px_points, fill=(95, 179, 172, 255), width=line_w)
    sx, sy = px_points[0]
    ex, ey = px_points[-1]
    draw.ellipse([sx - marker_r, sy - marker_r, sx + marker_r, sy + marker_r], fill=(63, 158, 91, 255))
    draw.ellipse([ex - marker_r, ey - marker_r, ex + marker_r, ey + marker_r], fill=(224, 128, 128, 255))

    if zoom:
        pad_px = pad_yalms / units_per_px
        crop_x0 = min(p[0] for p in px_points) - pad_px
        crop_y0 = min(p[1] for p in px_points) - pad_px
        crop_x1 = max(p[0] for p in px_points) + pad_px
        crop_y1 = max(p[1] for p in px_points) + pad_px
        # clamp to image bounds, preserving as much of the requested window as fits
        crop_x0 = max(0, min(crop_x0, size - 1))
        crop_y0 = max(0, min(crop_y0, size - 1))
        crop_x1 = max(crop_x0 + 1, min(crop_x1, size))
        crop_y1 = max(crop_y0 + 1, min(crop_y1, size))
        img = img.crop((int(crop_x0), int(crop_y0), int(crop_x1), int(crop_y1)))
        # upscale so the longer edge hits DISPLAY_SIZE, preserving aspect -- a tight path bbox
        # (e.g. a single room) would otherwise render tiny even after cropping
        w, h = img.size
        scale = DISPLAY_SIZE / max(w, h)
        if scale > 1:
            img = img.resize((max(1, int(w * scale)), max(1, int(h * scale))), Image.LANCZOS)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return Response(content=buf.getvalue(), media_type="image/png")


def distinct_color(i: int, n: int) -> tuple[int, int, int]:
    """Evenly-spaced hues around the wheel, fixed high saturation/lightness so every color stays
    legible against the dark mesh silhouette -- deterministic per index, not randomized, so the
    same entity gets the same color across repeat requests (matters once a legend links back)."""
    h = (i / max(n, 1)) % 1.0
    r, g, b = colorsys.hls_to_rgb(h, 0.62, 0.65)
    return int(r * 255), int(g * 255), int(b * 255)


MULTI_PLOT_LIMIT = 40


@app.get("/captures/plot_all", response_class=HTMLResponse)
def captures_plot_all(request: Request, capture_id: int, zone_db: str = "", pad_yalms: float = 200, detail: int = 0):
    con = get_con()
    cap = con.execute("SELECT * FROM captures WHERE capture_id=?", (capture_id,)).fetchone()
    zones = json.loads(cap["zones"]) if cap and cap["zones"] else []
    zone_db = zone_db or (zones[0] if zones else "")

    entities = build_capture_index.get_capture_entity_ids_with_path(con, capture_id, zone_db) if zone_db else []
    zoneid = zoneid_for_zone_db(con, zone_db) if zone_db else None
    variants = topdown_variants(zoneid)
    topdown_available = variants["collision"] or variants["detailed"]
    con.close()

    legend = [
        {"entity_id": eid, "name": name or "?", "color": "rgb(%d,%d,%d)" % distinct_color(i, len(entities))}
        for i, (eid, name) in enumerate(entities[:MULTI_PLOT_LIMIT])
    ]

    return templates.TemplateResponse(request, "path_plot_all.html", {
        "capture_id": capture_id, "cap": cap, "zones": zones, "zone_db": zone_db, "zoneid": zoneid,
        "entities": entities, "legend": legend, "topdown_available": topdown_available,
        "pad_yalms": pad_yalms, "truncated": len(entities) > MULTI_PLOT_LIMIT,
        "limit": MULTI_PLOT_LIMIT, "detail": detail, "variants": variants,
    })


@app.get("/captures/plot_all.png")
def captures_plot_all_png(capture_id: int, zone_db: str, pad_yalms: float = 200, detail: int = 0):
    """Every entity in one capture+zone with real path data, plotted together on the zone's real
    top-down mesh silhouette -- same coordinate-aligned approach as the single-entity plot, each
    entity given its own deterministic color (distinct_color) plus a small legend on the HTML page.
    detail=1 uses the denser visual-mesh cache instead of the default collision-mesh one."""
    con = get_con()
    entities = build_capture_index.get_capture_entity_ids_with_path(con, capture_id, zone_db)
    zoneid = zoneid_for_zone_db(con, zone_db)
    all_paths = []
    for eid, name in entities[:MULTI_PLOT_LIMIT]:
        pts = build_capture_index.get_entity_path(con, capture_id, eid)
        if pts:
            all_paths.append((eid, pts))
    con.close()

    paths = topdown_paths(zoneid, bool(detail))
    if not paths or not all_paths:
        return Response(status_code=404)
    img_path, transform_path = paths

    transform = json.loads(transform_path.read_text())
    img = Image.open(img_path).convert("RGBA")
    draw = ImageDraw.Draw(img)

    pad = transform["pad"]
    span = transform["span"]
    size = transform["img_size"]
    minx = transform["minx"]
    minz = transform["minz"]
    units_per_px = span / (size - 2 * pad)

    def to_px(cap_x, cap_z):
        world_z = -cap_z
        return (
            pad + (cap_x - minx) / span * (size - 2 * pad),
            pad + (world_z - minz) / span * (size - 2 * pad),
        )

    all_px_points = []
    n = len(all_paths)
    marker_r = max(3, min(9, int(pad_yalms / units_per_px / 20)))
    line_w = max(1, marker_r // 2)
    for i, (eid, pts) in enumerate(all_paths):
        color = distinct_color(i, n)
        px_points = [to_px(x, z) for x, z, _ in pts]
        all_px_points.extend(px_points)
        if len(px_points) > 1:
            draw.line(px_points, fill=color + (255,), width=line_w)
        sx, sy = px_points[0]
        draw.ellipse([sx - marker_r, sy - marker_r, sx + marker_r, sy + marker_r], fill=color + (255,))

    pad_px = pad_yalms / units_per_px
    crop_x0 = max(0, min(min(p[0] for p in all_px_points) - pad_px, size - 1))
    crop_y0 = max(0, min(min(p[1] for p in all_px_points) - pad_px, size - 1))
    crop_x1 = max(crop_x0 + 1, min(max(p[0] for p in all_px_points) + pad_px, size))
    crop_y1 = max(crop_y0 + 1, min(max(p[1] for p in all_px_points) + pad_px, size))
    img = img.crop((int(crop_x0), int(crop_y0), int(crop_x1), int(crop_y1)))
    w, h = img.size
    scale = DISPLAY_SIZE / max(w, h)
    if scale > 1:
        img = img.resize((max(1, int(w * scale)), max(1, int(h * scale))), Image.LANCZOS)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return Response(content=buf.getvalue(), media_type="image/png")


@app.get("/captures/new", response_class=HTMLResponse)
def captures_new_form(request: Request):
    """Start a capture from scratch, no source zip/folder at all -- create_manual_capture() gives
    it a real captures row with a synthetic source_path, then /captures/{id}/add is where files
    get dropped onto it one at a time (or a whole zip). Registered BEFORE /captures/{capture_id}
    -- that catch-all's int converter would otherwise try (and fail) to parse "new" as an id."""
    return templates.TemplateResponse(request, "capture_new.html", {"all_tags": build_capture_index.CAPTURE_TAGS})


@app.post("/captures/new", response_class=HTMLResponse)
async def captures_new_submit(request: Request):
    form = await request.form()
    label = (form.get("label") or "").strip()
    content_type = form.get("content_type", "instances")
    mission_name = (form.get("mission_name") or "").strip() or None
    tags = form.getlist("tags")
    if not label:
        return templates.TemplateResponse(request, "capture_new.html",
                                           {"error": "A label is required.", "all_tags": build_capture_index.CAPTURE_TAGS})
    con = get_con()
    capture_id = build_capture_index.create_manual_capture(con, label, content_type, mission_name)
    if tags:
        build_capture_index.set_capture_tags(con, capture_id, tags)
    con.close()
    return RedirectResponse(url=f"/captures/{capture_id}/add", status_code=303)


@app.post("/captures/{capture_id}/tags", response_class=HTMLResponse)
async def captures_tags_save(request: Request, capture_id: int):
    """Retag an already-existing capture -- most of the 84 real captures predate this feature, so
    the editor needs to work on captures created long before /captures/new grew a tags field, not
    just new ones."""
    form = await request.form()
    tags = form.getlist("tags")
    con = get_con()
    build_capture_index.set_capture_tags(con, capture_id, tags)
    con.close()
    return RedirectResponse(url=f"/captures/{capture_id}", status_code=303)


@app.post("/captures/{capture_id}/details", response_class=HTMLResponse)
async def captures_details_save(request: Request, capture_id: int):
    """Edits mission_name/content_type/capturer/video_url on an already-existing capture -- all
    four were previously set-once-at-creation only (mission_name/capturer via real
    manifest.txt/folder-name auto-detect during ingest, or the /captures/new form; content_type
    only at creation too), with no way to fix a wrong auto-detected value afterward. video_url is
    new -- a real external link to a recorded video of the same session (YouTube, a local file
    share, whatever the user actually has), stored as a plain URL/path, not validated as a
    reachable resource here (this app has no way to confirm that, and shouldn't pretend to)."""
    form = await request.form()
    mission_name = (form.get("mission_name") or "").strip() or None
    content_type = form.get("content_type") or "unclassified"
    capturer = (form.get("capturer") or "").strip() or None
    video_url = (form.get("video_url") or "").strip() or None
    con = get_con()
    con.execute(
        "UPDATE captures SET mission_name=?, content_type=?, capturer=?, video_url=? WHERE capture_id=?",
        (mission_name, content_type, capturer, video_url, capture_id))
    con.commit()
    con.close()
    return RedirectResponse(url=f"/captures/{capture_id}", status_code=303)


@app.get("/captures/{capture_id}/delete", response_class=HTMLResponse)
def captures_delete_confirm(request: Request, capture_id: int):
    """Confirm page for a real, irreversible delete -- no soft-delete exists, so this is gated
    behind an explicit second step (real row counts shown) rather than a single click/link, same
    caution as any other destructive action in this tool."""
    con = get_con()
    cap = con.execute("SELECT * FROM captures WHERE capture_id=?", (capture_id,)).fetchone()
    if not cap:
        con.close()
        return HTMLResponse("Capture not found", status_code=404)
    row_counts = {t: con.execute(f"SELECT COUNT(*) FROM {t} WHERE capture_id=?", (capture_id,)).fetchone()[0]
                  for t in build_capture_index.CAPTURE_CHILD_TABLES}
    con.close()
    return templates.TemplateResponse(request, "capture_delete_confirm.html", {
        "cap": cap, "row_counts": row_counts, "total_rows": sum(row_counts.values()),
    })


@app.post("/captures/{capture_id}/delete", response_class=HTMLResponse)
def captures_delete_submit(capture_id: int):
    con = get_con()
    cap = con.execute("SELECT capture_id FROM captures WHERE capture_id=?", (capture_id,)).fetchone()
    if not cap:
        con.close()
        return HTMLResponse("Capture not found", status_code=404)
    build_capture_index.delete_capture(con, capture_id)
    con.close()
    return RedirectResponse(url="/captures", status_code=303)


CAPTURE_SEARCH_PAGE_SIZE = 300


@app.get("/captures/search", response_class=HTMLResponse)
def captures_search(
    request: Request,
    entity: str = "", message_id: str = "", ev_opcodes: list[str] = Query(default=[]),
    pk_category: str = "", pk_opcode: str = "",
    mode: str = "events", page: int = 1,
):
    """Cross-capture search -- the point of ingesting everything per-capture (capture_events,
    capture_raw_packets) is worthless if you can only ever look at one capture at a time. Two
    independent modes sharing one page: 'events' searches capture_events across ALL 84 captures
    (real NPC name / opcode / message id, dialog_text-resolved same as the single-capture
    timeline) -- the 'find every time this NPC said X' use case. 'packets' searches
    capture_raw_packets across all captures by category/opcode -- the 'find every real item-grant
    packet anywhere in the corpus' use case. Kept as two modes rather than one merged query since
    the two tables don't share a schema (same reasoning as capture_eventview vs capture_events on
    the single-capture timeline page). Registered BEFORE /captures/{capture_id}/* -- a plain path
    param route matches any single segment, so /captures/search must come first or it would be
    shadowed (same real trap documented at /captures/plot's own registration-order note)."""
    con = get_con()
    events = []
    packets = []
    total = 0
    total_pages = 1
    page = max(1, page)

    available_ev_opcodes = [dict(r) for r in con.execute(
        "SELECT DISTINCT opcode, opcode_name FROM capture_events ORDER BY opcode").fetchall()]

    if mode == "events" and (entity or message_id or ev_opcodes):
        where_sql = "1=1"
        params = []
        if entity:
            where_sql += " AND e.entity_name LIKE ?"
            params.append(f"%{entity}%")
        if message_id:
            where_sql += " AND e.message_id = ?"
            params.append(int(message_id))
        if ev_opcodes:
            where_sql += f" AND e.opcode IN ({','.join('?' * len(ev_opcodes))})"
            params.extend(ev_opcodes)
        total = con.execute(
            f"SELECT COUNT(*) FROM capture_events e WHERE {where_sql}", params).fetchone()[0]
        total_pages = max(1, (total + CAPTURE_SEARCH_PAGE_SIZE - 1) // CAPTURE_SEARCH_PAGE_SIZE)
        offset = (page - 1) * CAPTURE_SEARCH_PAGE_SIZE
        sql = f"""SELECT e.*, c.capture_label FROM capture_events e
                 JOIN captures c ON c.capture_id = e.capture_id WHERE {where_sql}
                 ORDER BY e.capture_id, e.seq LIMIT ? OFFSET ?"""
        rows = con.execute(sql, params + [CAPTURE_SEARCH_PAGE_SIZE, offset]).fetchall()

        zoneid_cache: dict[str, int | None] = {}
        for r in rows:
            d = dict(r)
            zone_db = d.get("zone_db")
            if zone_db and zone_db not in zoneid_cache:
                zoneid_cache[zone_db] = zoneid_for_zone_db(con, zone_db)
            zoneid = zoneid_cache.get(zone_db) if zone_db else None
            d["dialog_text"] = None
            if d.get("message_id") is not None and zoneid is not None:
                trow = con.execute(
                    "SELECT text FROM dialog_text WHERE zoneid=? AND idx=?", (zoneid, d["message_id"])
                ).fetchone()
                d["dialog_text"] = trow[0] if trow else None
            events.append(d)

    if mode == "packets" and (pk_category or pk_opcode):
        # category filtering needs each distinct opcode's real description classified, same as
        # the single-capture packets page -- resolved here in Python (not SQL) since
        # categorize_opcode is logic over packet_decode's real opcode catalog, not a DB column.
        where = "1=1"
        params: list = []
        if pk_opcode:
            where = "p.opcode = ?"
            params = [pk_opcode.upper()]
        elif pk_category:
            all_opcodes = [r[0] for r in con.execute(
                "SELECT DISTINCT opcode FROM capture_raw_packets").fetchall()]
            wanted = []
            for op in all_opcodes:
                try:
                    op_int = int(op, 0)
                except ValueError:
                    continue
                try:
                    desc = packet_decode.decode("s2c", op_int, "").description
                except Exception:
                    desc = op
                if packet_decode.categorize_opcode(desc or op) == pk_category:
                    wanted.append(op)
            if wanted:
                where = f"p.opcode IN ({','.join('?' * len(wanted))})"
                params = wanted
            else:
                where = "0"

        total = con.execute(
            f"SELECT COUNT(*) FROM capture_raw_packets p WHERE {where}", params).fetchone()[0]
        total_pages = max(1, (total + CAPTURE_SEARCH_PAGE_SIZE - 1) // CAPTURE_SEARCH_PAGE_SIZE)
        offset = (page - 1) * CAPTURE_SEARCH_PAGE_SIZE
        sql = f"""SELECT p.capture_id, p.seq, p.ts, p.direction, p.opcode, p.raw_hex, c.capture_label
                  FROM capture_raw_packets p JOIN captures c ON c.capture_id = p.capture_id
                  WHERE {where} ORDER BY p.capture_id, p.seq LIMIT ? OFFSET ?"""
        rows = con.execute(sql, params + [CAPTURE_SEARCH_PAGE_SIZE, offset]).fetchall()
        for r in rows:
            d = dict(r)
            pd_direction = "s2c" if d["direction"] == "incoming" else "c2s"
            try:
                op_int = int(d["opcode"], 0)
                result = packet_decode.decode(pd_direction, op_int, d["raw_hex"])
                d["description"] = result.description
                d["fields"] = [
                    {"name": f.name, "value": f.display_value} for f in result.fields
                ]
            except Exception:
                d["description"] = None
                d["fields"] = None
            packets.append(d)

    categories = packet_decode.list_categories()
    con.close()
    # Pager needs to resubmit the current search's own filters (mode + whichever are set) plus a
    # new page number -- this page has two independent filter sets (events vs packets) that don't
    # share param names, so rather than re-deriving each combo in the template, the current
    # request's own query params (minus "page") are passed through as hidden inputs.
    qs_pairs = [(k, v) for k, v in request.query_params.multi_items() if k != "page"]
    if not qs_pairs:
        qs_pairs = [("mode", mode)]
    return templates.TemplateResponse(request, "capture_search.html", {
        "mode": mode, "entity": entity, "message_id": message_id,
        "ev_opcodes": ev_opcodes, "available_ev_opcodes": available_ev_opcodes,
        "pk_category": pk_category, "pk_opcode": pk_opcode, "categories": categories,
        "events": events, "packets": packets,
        "page": page, "total": total, "total_pages": total_pages, "qs_pairs": qs_pairs,
    })


@app.get("/captures/{capture_id}/add", response_class=HTMLResponse)
def captures_add_form(request: Request, capture_id: int, saved: str = ""):
    con = get_con()
    cap = con.execute("SELECT * FROM captures WHERE capture_id=?", (capture_id,)).fetchone()
    if not cap:
        con.close()
        return HTMLResponse("Capture not found", status_code=404)
    files = con.execute(
        "SELECT filename, format_detected, row_count, error, ingested_at FROM capture_source_files "
        "WHERE capture_id=? ORDER BY ingested_at DESC", (capture_id,)
    ).fetchall()
    con.close()
    return templates.TemplateResponse(request, "capture_add.html", {
        "cap": cap, "files": files, "saved": bool(saved), "last_results": None,
    })


@app.post("/captures/{capture_id}/add", response_class=HTMLResponse)
async def captures_add_submit(request: Request, capture_id: int):
    """Accepts one or more dropped files, and/or a whole picked folder, in one submit. A .zip (or
    a folder pick, which the template's JS reconstructs on the server as a real directory tree via
    each file's webkitRelativePath) gets the SAME full bundle-format dispatch ingest() uses
    (ingest_from_source) -- real folder structure drives detection there either way. Anything else
    is content-sniffed file by file (ingest_single_file), since a bare dropped file carries no
    folder context to key off of."""
    con = get_con()
    cap = con.execute("SELECT * FROM captures WHERE capture_id=?", (capture_id,)).fetchone()
    if not cap:
        con.close()
        return HTMLResponse("Capture not found", status_code=404)

    form = await request.form()
    uploads = form.getlist("files")
    results = []

    # A folder pick (see capture_add.html's fetch-based submit) sends each file's real
    # webkitRelativePath as its filename, e.g. "Zone Name/17002517.csv" -- collect those
    # separately so they can be reconstructed into a real directory on disk and ingested via
    # the SAME Source/ingest_from_source path a .zip upload uses (full folder-context fidelity,
    # so PathLog CSVs etc. work exactly like they do from a zip), instead of the bare
    # single-file path below (which has no folder context to key off of).
    folder_entries = []  # list of (relative_path: str, data: bytes)
    plain_uploads = []
    for uf in uploads:
        if not getattr(uf, "filename", None):
            continue
        raw_name = uf.filename.replace("\\", "/")
        if "/" in raw_name:
            data = await uf.read()
            if not data:
                continue
            # Reject path traversal / absolute paths -- these filenames are client-controlled.
            parts = [p for p in raw_name.split("/") if p not in ("", ".", "..")]
            if not parts:
                continue
            folder_entries.append(("/".join(parts), data))
        else:
            plain_uploads.append(uf)

    if folder_entries:
        tmp_dir = Path(tempfile.mkdtemp(prefix=f"capture_folder_{capture_id}_"))
        label = f"folder upload ({len(folder_entries)} files)"
        try:
            for rel_path, data in folder_entries:
                dest = tmp_dir / rel_path
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(data)
            src = build_capture_index.Source(tmp_dir)
            try:
                file_results = []
                counts = build_capture_index.ingest_from_source(con, capture_id, src, file_results=file_results)
                build_capture_index.recompute_zones(con, capture_id)
                total_rows = sum(counts.values())
                n_failed = sum(1 for r in file_results if r["error"])
                summary_error = f"{n_failed} of {len(file_results)} file(s) failed -- see below" if n_failed else None
                con.execute("""INSERT OR REPLACE INTO capture_source_files
                    (capture_id, filename, format_detected, ingested_at, row_count, error)
                    VALUES (?,?,?,datetime('now'),?,?)""",
                    (capture_id, label, "folder_bundle", total_rows, summary_error))
                results.append({"filename": label, "format": "folder_bundle", "rows": total_rows, "error": summary_error})
                for r in file_results:
                    con.execute("""INSERT OR REPLACE INTO capture_source_files
                        (capture_id, filename, format_detected, ingested_at, row_count, error)
                        VALUES (?,?,?,datetime('now'),?,?)""",
                        (capture_id, r["filename"], None, r["rows"], r["error"]))
                    results.append({"filename": r["filename"], "format": None, "rows": r["rows"], "error": r["error"]})
                con.commit()
            finally:
                src.close()
        except build_capture_index.UnsupportedArchiveError as ex:
            con.execute("""INSERT OR REPLACE INTO capture_source_files
                (capture_id, filename, format_detected, ingested_at, row_count, error)
                VALUES (?,?,NULL,datetime('now'),0,?)""",
                (capture_id, label, str(ex)))
            con.commit()
            results.append({"filename": label, "format": None, "rows": 0, "error": str(ex)})
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    for uf in plain_uploads:
        data = await uf.read()
        if not data:
            continue
        fname_lower = uf.filename.lower()
        archive_suffix = Path(fname_lower).suffix
        # .zip/.7z get the full bundle-dispatch treatment (ingest_from_source, real folder
        # structure preserved); anything else that's still a KNOWN archive type (.rar/.tar/.gz/...)
        # is caught here too, specifically so it gets Source's real "why this can't be read"
        # message instead of being routed to ingest_single_file (which would just report a
        # confusing "unrecognized log format" for what is actually a whole unopened archive).
        if archive_suffix in (".zip", ".7z") or archive_suffix in build_capture_index.KNOWN_UNSUPPORTED_ARCHIVES:
            tmp_dir = Path(tempfile.gettempdir()) / f"capture_upload_{capture_id}"
            tmp_dir.mkdir(exist_ok=True)
            tmp_archive = tmp_dir / uf.filename
            tmp_archive.write_bytes(data)
            src = None
            try:
                src = build_capture_index.Source(tmp_archive)
                file_results = []
                counts = build_capture_index.ingest_from_source(con, capture_id, src, file_results=file_results)
                build_capture_index.recompute_zones(con, capture_id)
                total_rows = sum(counts.values())
                n_failed = sum(1 for r in file_results if r["error"])
                summary_error = f"{n_failed} of {len(file_results)} file(s) failed -- see below" if n_failed else None
                con.execute("""INSERT OR REPLACE INTO capture_source_files
                    (capture_id, filename, format_detected, ingested_at, row_count, error)
                    VALUES (?,?,?,datetime('now'),?,?)""",
                    (capture_id, uf.filename, "zip_bundle", total_rows, summary_error))
                results.append({"filename": uf.filename, "format": "zip_bundle",
                                 "rows": total_rows, "error": summary_error})
                for r in file_results:
                    con.execute("""INSERT OR REPLACE INTO capture_source_files
                        (capture_id, filename, format_detected, ingested_at, row_count, error)
                        VALUES (?,?,?,datetime('now'),?,?)""",
                        (capture_id, r["filename"], None, r["rows"], r["error"]))
                    results.append({"filename": r["filename"], "format": None, "rows": r["rows"], "error": r["error"]})
                con.commit()
            except build_capture_index.UnsupportedArchiveError as ex:
                con.execute("""INSERT OR REPLACE INTO capture_source_files
                    (capture_id, filename, format_detected, ingested_at, row_count, error)
                    VALUES (?,?,NULL,datetime('now'),0,?)""",
                    (capture_id, uf.filename, str(ex)))
                con.commit()
                results.append({"filename": uf.filename, "format": None, "rows": 0, "error": str(ex)})
            finally:
                if src is not None:
                    src.close()
                tmp_archive.unlink(missing_ok=True)
        else:
            results.append(build_capture_index.ingest_single_file(con, capture_id, uf.filename, data))
    con.close()

    con = get_con()
    files = con.execute(
        "SELECT filename, format_detected, row_count, error, ingested_at FROM capture_source_files "
        "WHERE capture_id=? ORDER BY ingested_at DESC", (capture_id,)
    ).fetchall()
    cap = con.execute("SELECT * FROM captures WHERE capture_id=?", (capture_id,)).fetchone()
    con.close()
    return templates.TemplateResponse(request, "capture_add.html", {
        "cap": cap, "files": files, "saved": False, "last_results": results,
    })


@app.get("/captures/{capture_id}", response_class=HTMLResponse)
def captures_detail(request: Request, capture_id: int, content_type: str = "", q: str = ""):
    """Dedicated detail page, with prev/next cycling through the SAME filtered list the user
    came from (content_type/q carried through as query params) -- directly answers "let me
    cycle through them" instead of bouncing back to the list every time. Registered LAST among
    the /captures/* routes: a plain path param route matches any single segment, so it has to
    come after /captures/plot, /captures/plot.png, /captures/plot_all, /captures/plot_all.png or
    it would shadow all of them (FastAPI matches route templates in registration order)."""
    con = get_con()
    row = con.execute("SELECT * FROM captures WHERE capture_id=?", (capture_id,)).fetchone()
    if not row:
        con.close()
        return HTMLResponse("Capture not found", status_code=404)

    detail = dict(row)
    detail["zones"] = json.loads(detail["zones"]) if detail.get("zones") else []
    detail["addons"] = json.loads(detail["addons"]) if detail.get("addons") else []
    detail["npc_entries"] = con.execute(
        """SELECT entity_id, name, model_id, x, y, z, hpp, zone_db
           FROM capture_npc_entries WHERE capture_id=? ORDER BY name LIMIT 200""",
        (capture_id,)).fetchall()
    detail["n_history"] = con.execute(
        "SELECT COUNT(*) FROM capture_npc_history WHERE capture_id=?", (capture_id,)
    ).fetchone()[0]
    detail["n_path"] = con.execute(
        "SELECT COUNT(*) FROM capture_npc_path WHERE capture_id=?", (capture_id,)
    ).fetchone()[0]
    detail["n_actions"] = con.execute(
        "SELECT COUNT(*) FROM capture_actions WHERE capture_id=?", (capture_id,)
    ).fetchone()[0]
    detail["n_events"] = con.execute(
        "SELECT COUNT(*) FROM capture_events WHERE capture_id=?", (capture_id,)
    ).fetchone()[0]
    detail["n_ki_events"] = con.execute(
        "SELECT COUNT(*) FROM capture_ki_events WHERE capture_id=?", (capture_id,)
    ).fetchone()[0]
    detail["n_raw_packets"] = con.execute(
        "SELECT COUNT(*) FROM capture_raw_packets WHERE capture_id=?", (capture_id,)
    ).fetchone()[0]
    detail["pc_path_zones"] = build_capture_index.get_pc_path_zones(con, capture_id)
    detail["tags"] = build_capture_index.get_capture_tags(con, capture_id)
    detail["hp_events"] = con.execute(
        "SELECT mob_name, hp_low, hp_high FROM capture_hp_events WHERE capture_id=? ORDER BY seq",
        (capture_id,)).fetchall()

    filtered_sql = "SELECT capture_id FROM captures WHERE 1=1"
    params = []
    if content_type:
        filtered_sql += " AND content_type=?"
        params.append(content_type)
    if q:
        filtered_sql += " AND (mission_name LIKE ? OR capture_label LIKE ?)"
        params.extend([f"%{q}%", f"%{q}%"])
    filtered_sql += " ORDER BY content_type, capture_id"
    filtered_ids = [r[0] for r in con.execute(filtered_sql, params).fetchall()]
    con.close()

    prev_id = next_id = None
    position = None
    if capture_id in filtered_ids:
        idx = filtered_ids.index(capture_id)
        position = f"{idx + 1} of {len(filtered_ids)}"
        if idx > 0:
            prev_id = filtered_ids[idx - 1]
        if idx < len(filtered_ids) - 1:
            next_id = filtered_ids[idx + 1]

    return templates.TemplateResponse(request, "capture_detail.html", {
        "detail": detail, "content_type": content_type, "q": q,
        "prev_id": prev_id, "next_id": next_id, "position": position,
        "all_tags": build_capture_index.CAPTURE_TAGS,
    })


@app.get("/captures/{capture_id}/timeline", response_class=HTMLResponse)
def captures_timeline(
    request: Request, capture_id: int,
    entity: str = "", opcodes: list[str] = Query(default=[]), direction: str = "",
    ev_gp: str = "", show_raw: int = -1, show_items: int = 1, item_containers: str = "session",
):
    """Real 'call and response' browser for one capture -- surfaces capture_events (per-capture
    real seq order: NPC Chat -> CS Event+Params -> Event Option, exactly the sequence a live
    interaction produced) with message_id resolved live against dialog_text (zone-matched via
    zoneid_for_zone_db) so raw numeric ids read as real dialogue. capture_ki_events and
    capture_eventview are shown as separate sections rather than merged into one timeline --
    each table has its OWN independent seq counter (not a shared timestamp/ordinal with
    capture_events), so interleaving them would silently fabricate an order that isn't real.

    2026-09-04: real bug fixed -- capture_events only ever gets populated by the OLDER idview
    format (confirmed: 82 of 84 real captures, the modern 'Thris Nov2025' PacketLogger/EventView
    set, have ZERO capture_events rows). For those, the real dialogue data lives entirely in
    capture_eventview (e.g. capture 102: 0 events, 150 real eventview rows, 29 of them
    GP_SERV_COMMAND_TALKNUMWORK -- real dialog message numbers, dialog_text-resolvable same as
    capture_events). Previously capture_eventview was hidden by default and mislabeled as pure
    'noise' -- for the majority of captures it's actually the ONLY narrative data there is. Now
    defaults to visible whenever capture_events is empty for this capture (show_raw=-1 means
    "auto", resolved below) and its own message_number is dialog_text-resolved too."""
    con = get_con()
    cap = con.execute("SELECT * FROM captures WHERE capture_id=?", (capture_id,)).fetchone()
    if not cap:
        con.close()
        return HTMLResponse("Capture not found", status_code=404)

    # Checkbox list of real opcodes THIS capture actually has (not a hardcoded/guessed set) --
    # capture_events only ever has a handful of distinct opcodes total (confirmed 2026-09-04:
    # just 4 across the entire 84-capture corpus -- CS Event/CS Event+Params/NPC Chat/Event
    # Option), unlike capture_raw_packets' 318-opcode space where free text + category made more
    # sense. A checkbox list is strictly better here since the whole option space is this small.
    available_opcodes = [dict(r) for r in con.execute(
        "SELECT DISTINCT opcode, opcode_name FROM capture_events WHERE capture_id=? ORDER BY opcode",
        (capture_id,)).fetchall()]

    # 2026-09-04: real "why is this empty" distinction, per user request -- an unfiltered total
    # alongside the (possibly filtered) row list for every tab, so a 0-row tab can honestly say
    # "no source data exists for this capture" vs "no rows match your filter" instead of leaving
    # the viewer to guess whether it's bad data, an over-aggressive filter, or genuinely absent.
    events_total = con.execute(
        "SELECT COUNT(*) FROM capture_events WHERE capture_id=?", (capture_id,)).fetchone()[0]

    sql = "SELECT * FROM capture_events WHERE capture_id=?"
    params = [capture_id]
    if entity:
        sql += " AND entity_name LIKE ?"
        params.append(f"%{entity}%")
    if opcodes:
        sql += f" AND opcode IN ({','.join('?' * len(opcodes))})"
        params.extend(opcodes)
    if direction:
        sql += " AND direction = ?"
        params.append(direction)
    sql += " ORDER BY seq"
    event_rows = con.execute(sql, params).fetchall()

    zoneid_cache: dict[str, int | None] = {}
    events = []
    for r in event_rows:
        d = dict(r)
        zone_db = d.get("zone_db")
        if zone_db and zone_db not in zoneid_cache:
            zoneid_cache[zone_db] = zoneid_for_zone_db(con, zone_db)
        zoneid = zoneid_cache.get(zone_db) if zone_db else None
        d["dialog_text"] = None
        if d.get("message_id") is not None and zoneid is not None:
            trow = con.execute(
                "SELECT text FROM dialog_text WHERE zoneid=? AND idx=?", (zoneid, d["message_id"])
            ).fetchone()
            d["dialog_text"] = trow[0] if trow else None
        events.append(d)

    ki_events = con.execute(
        "SELECT * FROM capture_ki_events WHERE capture_id=? ORDER BY seq", (capture_id,)
    ).fetchall()

    eventview_total = con.execute(
        "SELECT COUNT(*) FROM capture_eventview WHERE capture_id=?", (capture_id,)).fetchone()[0]

    # 2026-09-04: real bug fixed -- eventview used to only be queried when show_raw was truthy
    # (a leftover from before this page had tabs, when it was a collapsed "show more" toggle).
    # Every OTHER tab on this page now loads unconditionally (tabs are pure CSS/JS visibility, not
    # separate page loads) -- eventview being the one exception meant its tab could show "no data"
    # purely because it was never fetched, not because the capture actually had none. Now always
    # queried, same as every other tab, capped at 500 rows like before.
    ev_sql = "SELECT * FROM capture_eventview WHERE capture_id=?"
    ev_params = [capture_id]
    if ev_gp:
        ev_sql += " AND (gp_command LIKE ? OR packet_class LIKE ?)"
        ev_params.extend([f"%{ev_gp}%", f"%{ev_gp}%"])
    ev_sql += " ORDER BY seq LIMIT 500"
    ev_rows = con.execute(ev_sql, ev_params).fetchall()
    eventview = []
    for r in ev_rows:
        d = dict(r)
        zone_db = d.get("zone_db")
        if zone_db and zone_db not in zoneid_cache:
            zoneid_cache[zone_db] = zoneid_for_zone_db(con, zone_db)
        zoneid = zoneid_cache.get(zone_db) if zone_db else None
        d["dialog_text"] = None
        # message_number is the real dialog_text idx (mes_num is a different, larger raw
        # client-side message id -- confirmed 2026-09-04 against capture 2: message_number
        # 7507/7522/7582 all resolved real dialog_text rows, mes_num 40275/40290/40350 did
        # not, same real distinction dialog_view/EventView already draw between the two).
        if d.get("message_number") is not None and zoneid is not None:
            trow = con.execute(
                "SELECT text FROM dialog_text WHERE zoneid=? AND idx=?", (zoneid, d["message_number"])
            ).fetchone()
            d["dialog_text"] = trow[0] if trow else None
        eventview.append(d)

    # 2026-09-06: real bug fixed -- this used to pull EVERY opcode packet_decode.categorize_opcode
    # buckets under its broad "item_shop" category (ITEM_MAX/Inventory Count/Inventory Finish/
    # Item List/Synth Result/Delivery Box/Auction/Scenario Item/Currencies), most of which are
    # full-inventory-sync dumps sent on every zone/login (Inventory Count+Finish+List alone were
    # 2,177 rows on a single real capture) or entirely unrelated traffic (Synth Result, Auction
    # House) -- exactly the "junk data" the Items Obtained tab was reporting. The one real signal
    # for "an item was granted/changed" is 0x020 GP_SERV_COMMAND_ITEM_ATTR alone (confirmed against
    # LandSandBoat's charutils.cpp: it's the packet pushed on every real inventory add/remove/move,
    # where the broader sync opcodes above are one-shot dumps with no per-event meaning). Its own
    # field definition in packetlyzer_db.xml was ALSO corrupted (two conflicting field layouts
    # concatenated into one packet entry, confirmed by decoding real captures: item_id always read
    # back 0, quantity read back garbage like 4294901760) -- fixed there too (see that file's own
    # 2026-09-06 comment), so ItemNo/ItemNum now decode to real item ids/quantities instead.
    ITEM_OBTAINED_OPCODE = "0X020"
    raw_packets_total = con.execute(
        "SELECT COUNT(*) FROM capture_raw_packets WHERE capture_id=?", (capture_id,)).fetchone()[0]

    # 2026-09-06: real bug fixed -- 0x020 fires on ANY change to ANY of a character's real
    # containers (LandSandBoat's item_container.h CONTAINER_ID enum), not just the main inventory:
    # Mog Safe/Storage/Locker/Satchel/Sack/Case, eight separate Wardrobes, a second Mog Safe, the
    # Recycle Bin. A capturer browsing their Mog House between missions generates just as many
    # 0x020 rows as anything actually obtained during play -- confirmed live on a real capture:
    # 761 of 986 rows (77%) were non-inventory containers. "session" (default) keeps only
    # LOC_INVENTORY (0, the main bag) and LOC_TEMPITEMS (3, the real Assault/Nyzul temp-item slot
    # this tab was originally built for) -- the two containers that can actually change during a
    # mission itself. "all" shows every container, e.g. to review a between-missions storage run.
    CONTAINER_NAMES = {
        0: "Inventory", 1: "Mog Safe", 2: "Storage", 3: "Temp Items", 4: "Mog Locker",
        5: "Mog Satchel", 6: "Mog Sack", 7: "Mog Case", 8: "Wardrobe", 9: "Mog Safe 2",
        10: "Wardrobe 2", 11: "Wardrobe 3", 12: "Wardrobe 4", 13: "Wardrobe 5",
        14: "Wardrobe 6", 15: "Wardrobe 7", 16: "Wardrobe 8", 17: "Recycle Bin",
    }
    SESSION_CONTAINERS = {0, 3}

    # 2026-09-06: real bug fixed -- even restricted to Inventory/Temp Items, a lot of "Items
    # Obtained" rows are still not real grants. LandSandBoat's charutils.cpp::SendInventory() is
    # called ONLY from the client's zone-in "game OK" handshake (0x00c_gameok.cpp) and loops every
    # slot of a container, pushing a real 0x020 for every item the character ALREADY owns -- a
    # full resync, not a change. Confirmed on this capture: rows 164-178 (and several later
    # clusters of up to 34 rows) all share the exact same real timestamp, one per already-owned
    # item -- the zone-in inventory dump the user noticed. A genuine treasure-pool win or reward
    # is pushed as a single isolated 0x020 at its own moment, never bundled with a dozen others at
    # the same instant. "acquired" (tightest) keeps only rows whose real timestamp is NOT shared
    # with any other Inventory/Temp-Items row -- i.e. excludes every same-timestamp resync burst.
    # This is a heuristic, not certainty: two genuinely distinct real events landing in the same
    # rounded-to-the-second timestamp would also get excluded, though nothing in this project's
    # real capture data has shown that happening yet.
    items = []
    items_matching_total = 0
    if show_items:
        rows = con.execute(
            "SELECT * FROM capture_raw_packets WHERE capture_id=? AND opcode=? ORDER BY seq",
            (capture_id, ITEM_OBTAINED_OPCODE)).fetchall()
        decoded = []
        for r in rows:
            d = dict(r)
            pd_direction = "s2c" if d["direction"] == "incoming" else "c2s"
            try:
                result = packet_decode.decode(pd_direction, 0x020, d["raw_hex"])
                fields = {f.name: f.raw_value for f in result.fields}
                bag = fields.get("Category")
                scope = SESSION_CONTAINERS if item_containers != "all" else None
                if scope is not None and bag not in scope:
                    continue
                d["description"] = result.description
                d["fields"] = [{"name": f.name, "value": f.display_value} for f in result.fields]
                item_id = fields.get("ItemNo")
                d["item_id"] = item_id
                d["quantity"] = fields.get("ItemNum")
                d["slot"] = fields.get("ItemIndex")
                d["bag"] = bag
                d["bag_name"] = CONTAINER_NAMES.get(bag, bag)
                d["item_name"] = None
                if item_id is not None:
                    name_row = con.execute(
                        "SELECT name FROM items_ours WHERE itemid=?", (item_id,)).fetchone()
                    if not name_row:
                        name_row = con.execute(
                            "SELECT name FROM items_external WHERE id=?", (item_id,)).fetchone()
                    d["item_name"] = name_row[0] if name_row else None
            except Exception:
                d["description"] = None
                d["fields"] = None
                d["item_id"] = d["quantity"] = d["slot"] = d["bag"] = d["bag_name"] = d["item_name"] = None
            decoded.append(d)

        if item_containers == "acquired":
            ts_counts = Counter(d["ts"] for d in decoded if d["bag"] in SESSION_CONTAINERS)
            decoded = [d for d in decoded if d["bag"] in SESSION_CONTAINERS and ts_counts[d["ts"]] == 1]

        items_matching_total = len(decoded)
        items = decoded[:300]

    directions = [r[0] for r in con.execute(
        "SELECT DISTINCT direction FROM capture_events WHERE capture_id=? ORDER BY 1", (capture_id,)
    ).fetchall()]

    # 2026-09-04: real Battle tab -- capture_actions (ActionView.db, real named ability/mobskill/
    # spell usage with animation/message ids, e.g. "Khimaira 14X used Tenebrous Mist"). Only 27 of
    # 84 real captures have ActionView.db (same "Thris Nov2025" NPCLogger-format dependency as
    # capture_actions/capture_hp_events elsewhere) -- genuinely absent for the rest, not filtered.
    actions = []
    for r in con.execute(
            "SELECT * FROM capture_actions WHERE capture_id=? ORDER BY ts", (capture_id,)).fetchall():
        d = dict(r)
        # ts is a real unix timestamp (ActionView.db's own column) -- formatted here so it reads
        # like every other timestamp column on this page instead of a bare epoch integer.
        try:
            d["ts_display"] = datetime.fromtimestamp(d["ts"]).strftime("%Y-%m-%d %H:%M:%S") if d.get("ts") else ""
        except (ValueError, OSError, OverflowError):
            d["ts_display"] = str(d.get("ts") or "")
        actions.append(d)

    # Which tab a fresh page load should open on -- events if it has real rows (the richer,
    # already-structured data), otherwise whichever tab actually has something for this capture,
    # ranked roughly by real richness, so a first-time viewer never lands on an empty tab.
    if events:
        default_tab = "events"
    elif eventview:
        default_tab = "raw"
    elif actions:
        default_tab = "battle"
    elif items:
        default_tab = "items"
    else:
        default_tab = "ki"

    con.close()
    return templates.TemplateResponse(request, "capture_timeline.html", {
        "cap": cap, "capture_id": capture_id,
        "events": events, "ki_events": ki_events, "eventview": eventview, "items": items,
        "actions": actions,
        "events_total": events_total, "eventview_total": eventview_total,
        "raw_packets_total": raw_packets_total,
        "show_items": show_items, "item_containers": item_containers,
        "items_matching_total": items_matching_total, "default_tab": default_tab,
        "entity": entity, "opcodes": opcodes, "available_opcodes": available_opcodes,
        "direction": direction, "directions": directions,
        "ev_gp": ev_gp, "show_raw": show_raw,
    })


@app.get("/captures/{capture_id}/packets", response_class=HTMLResponse)
def captures_raw_packets(
    request: Request, capture_id: int,
    category: str = "", opcode: str = "", direction: str = "",
    page: int = 1,
):
    """Real per-capture raw packet browser -- capture_raw_packets (build_capture_index.py's
    ingest_packetlogger) covers every opcode PacketLogger observed, not just the dialog/event
    ones capture_events/capture_eventview already surface -- item grants, shop transactions,
    battle actions, etc. Decoding happens HERE, per page, not at ingest time (a capture can hold
    tens of thousands of raw packets; decoding all of them up front for rows nobody looks at
    would be wasted work) -- see ingest_packetlogger's own docstring for why raw_hex is all that's
    stored. category comes from packet_decode.categorize_opcode's real, data-derived taxonomy."""
    PAGE_SIZE = 50
    con = get_con()
    cap = con.execute("SELECT * FROM captures WHERE capture_id=?", (capture_id,)).fetchone()
    if not cap:
        con.close()
        return HTMLResponse("Capture not found", status_code=404)

    # Distinct (direction, opcode) present in this capture, each tagged with its real
    # description + category, so the filter dropdowns only ever offer opcodes that actually
    # occur here (not all 318 known ones).
    present = con.execute(
        "SELECT DISTINCT direction, opcode FROM capture_raw_packets WHERE capture_id=? ORDER BY opcode",
        (capture_id,)).fetchall()
    opcode_catalog = {}
    for d, op in present:
        try:
            op_int = int(op, 0)
        except ValueError:
            continue
        pd_direction = "s2c" if d == "incoming" else "c2s"
        desc = None
        try:
            res = packet_decode.decode(pd_direction, op_int, "")
            desc = res.description
        except Exception:
            desc = None
        opcode_catalog[op] = {
            "opcode": op, "description": desc or op,
            "category": packet_decode.categorize_opcode(desc or op),
        }
    categories = sorted({v["category"] for v in opcode_catalog.values()})

    sql = "SELECT * FROM capture_raw_packets WHERE capture_id=?"
    params = [capture_id]
    if direction:
        sql += " AND direction=?"
        params.append(direction)
    if opcode:
        sql += " AND opcode=?"
        params.append(opcode.upper())
    if category:
        matching_opcodes = [op for op, v in opcode_catalog.items() if v["category"] == category]
        if matching_opcodes:
            sql += f" AND opcode IN ({','.join('?' * len(matching_opcodes))})"
            params.extend(matching_opcodes)
        else:
            sql += " AND 0"
    count_sql = sql.replace("SELECT *", "SELECT COUNT(*)")
    total = con.execute(count_sql, params).fetchone()[0]

    sql += " ORDER BY seq LIMIT ? OFFSET ?"
    params2 = params + [PAGE_SIZE, (max(page, 1) - 1) * PAGE_SIZE]
    rows = con.execute(sql, params2).fetchall()
    con.close()

    decoded_rows = []
    for r in rows:
        d = dict(r)
        pd_direction = "s2c" if d["direction"] == "incoming" else "c2s"
        d["pd_direction"] = pd_direction
        try:
            op_int = int(d["opcode"], 0)
            result = packet_decode.decode(pd_direction, op_int, d["raw_hex"])
            d["description"] = result.description
            d["fields"] = [
                {"name": f.name, "type": f.type, "value": f.display_value, "out_of_range": f.out_of_range}
                for f in result.fields
            ]
        except Exception as e:
            d["description"] = None
            d["fields"] = None
            d["decode_error"] = str(e)
        decoded_rows.append(d)

    total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    return templates.TemplateResponse(request, "capture_packets.html", {
        "cap": cap, "capture_id": capture_id,
        "rows": decoded_rows, "total": total, "page": page, "total_pages": total_pages,
        "category": category, "opcode": opcode, "direction": direction,
        "categories": categories, "opcode_catalog": sorted(opcode_catalog.values(), key=lambda v: v["opcode"]),
    })


def _list_backups() -> list[dict]:
    if not build_database.DB_BACKUPS_DIR.is_dir():
        return []
    rows = []
    for path in sorted(build_database.DB_BACKUPS_DIR.glob("ffxi_zone_database-*.db"), reverse=True):
        stat = path.stat()
        rows.append({
            "name": path.name,
            "size_mb": round(stat.st_size / (1024 * 1024), 1),
            "mtime": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
        })
    return rows


@app.get("/settings", response_class=HTMLResponse)
def settings_page(request: Request, saved: str = "", backup: str = "", ok: str = ""):
    con = get_con()
    values = settings_mod.get_all(con)
    con.close()
    return templates.TemplateResponse(request, "settings.html", {
        "values": values, "saved": bool(saved), "backups": _list_backups(),
        "backup_result": backup, "backup_ok": bool(int(ok)) if ok else None,
        "llm_key_configured": llm_client.has_api_key(),
    })


@app.post("/theme/toggle")
def theme_toggle(request: Request):
    """Flips light<->dark from the header's own sun/moon button -- moved here from the Settings
    form since it's a real one-click toggle now, not a dropdown needing a Save click. Redirects
    back to wherever the click happened (Referer), falling back to the homepage, so toggling
    theme never navigates you away from the page you were reading."""
    con = get_con()
    new_theme = "dark" if settings_mod.get(con, "theme") != "dark" else "light"
    settings_mod.set_many(con, {"theme": new_theme})
    con.close()
    return RedirectResponse(url=request.headers.get("referer", "/"), status_code=303)


@app.post("/settings", response_class=HTMLResponse)
async def settings_save(request: Request):
    form = await request.form()
    con = get_con()
    port_raw = form.get("port", "").strip()
    port_value = port_raw if port_raw.isdigit() and 1 <= int(port_raw) <= 65535 else settings_mod.DEFAULTS["port"]
    retention_raw = form.get("backup_retention_count", "").strip()
    retention_value = retention_raw if retention_raw.isdigit() else settings_mod.DEFAULTS["backup_retention_count"]
    settings_mod.set_many(con, {
        # theme deliberately not set here -- it's managed exclusively by the header's own
        # sun/moon toggle (/theme/toggle) now, not this form; including it here would silently
        # reset it to "light" on every Settings save (form.get() with no theme field present).
        "topaz_server_path": form.get("topaz_server_path", "").strip(),
        "dsp_server_path": form.get("dsp_server_path", "").strip(),
        "backport_root": form.get("backport_root", "").strip(),
        "ffxi_install_path": form.get("ffxi_install_path", "").strip(),
        "xi_model_viewer_url": form.get("xi_model_viewer_url", "").strip(),
        "port": port_value,
        "backup_retention_count": retention_value,
        "llm_base_url": form.get("llm_base_url", "").strip() or settings_mod.DEFAULTS["llm_base_url"],
        "llm_default_model": form.get("llm_default_model", "").strip() or settings_mod.DEFAULTS["llm_default_model"],
    })
    con.close()

    # API key deliberately handled separately from set_many() above -- it never lives in the
    # settings table (see settings.py's own comment on llm_base_url). A blank submission means
    # "leave the existing key alone," not "clear it" -- there's no way to tell "field left blank on
    # purpose" from "field left blank because the browser never shows the real value back," so
    # clearing must be an explicit separate action, not a side effect of an empty text field.
    new_key = form.get("llm_api_key", "").strip()
    if new_key:
        llm_client.save_api_key(new_key)

    return RedirectResponse(url="/settings?saved=1", status_code=303)


@app.post("/backup/create")
def backup_create():
    """Real "Backup now" button -- always makes a fresh copy (min_interval_seconds=0) regardless
    of the 5-minute coalescing /rebuild/{source} uses, since a user clicking this explicitly wants
    one right now, not "whichever one already exists from the last few minutes."""
    build_database.backup_database_file(min_interval_seconds=0)
    return RedirectResponse(url="/settings?backup=created&ok=1", status_code=303)


@app.get("/backup/delete/{name}/confirm", response_class=HTMLResponse)
def backup_delete_confirm(request: Request, name: str):
    """Confirm page for deleting one backup -- same explicit-second-step pattern as
    /captures/{id}/delete, /backup/restore/{name}/confirm, and /rebuild/{source}/confirm."""
    backup_path = build_database.DB_BACKUPS_DIR / name
    if not backup_path.is_file() or backup_path.parent != build_database.DB_BACKUPS_DIR:
        return HTMLResponse("Backup file not found", status_code=404)
    stat = backup_path.stat()
    backup = {
        "name": name,
        "size_mb": round(stat.st_size / (1024 * 1024), 1),
        "mtime": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
    }
    return templates.TemplateResponse(request, "backup_delete_confirm.html", {"backup": backup})


@app.post("/backup/delete")
def backup_delete(name: str = Form(...)):
    """Deletes one backup file -- never touches the live database, but gated behind its own
    confirm page (backup_delete_confirm.html) same as every other destructive action here."""
    backup_path = build_database.DB_BACKUPS_DIR / name
    if not backup_path.is_file() or backup_path.parent != build_database.DB_BACKUPS_DIR:
        return RedirectResponse(url="/settings?backup=Unknown+backup+file&ok=0", status_code=303)
    backup_path.unlink()
    return RedirectResponse(url=f"/settings?backup=Deleted+{name}&ok=1", status_code=303)


@app.get("/backup/restore/{name}/confirm", response_class=HTMLResponse)
def backup_restore_confirm(request: Request, name: str):
    """Confirm page for a real, disruptive action (replaces the live database and restarts the
    toolkit) -- same explicit-second-step pattern as /captures/{id}/delete's own confirm page,
    rather than a single click or a JS confirm() dialog alone."""
    backup_path = build_database.DB_BACKUPS_DIR / name
    if not backup_path.is_file() or backup_path.parent != build_database.DB_BACKUPS_DIR:
        return HTMLResponse("Backup file not found", status_code=404)
    stat = backup_path.stat()
    backup = {
        "name": name,
        "size_mb": round(stat.st_size / (1024 * 1024), 1),
        "mtime": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
    }
    return templates.TemplateResponse(request, "backup_restore_confirm.html", {"backup": backup})


@app.post("/backup/restore")
def backup_restore(request: Request, name: str = Form(...)):
    """Restores a previous backup over the live database. Takes its own safety backup of the
    CURRENT state first (so a restore is itself undoable -- the exact guarantee this whole backup
    system exists to provide, see build_database.backup_database_file's own docstring for the
    incident that motivated it), then removes any WAL/SHM sidecar files tied to the OLD db file
    before copying the backup in, since this app never holds a connection open across requests
    (get_con() opens/closes per-request) -- a stale WAL file referencing the pre-restore data
    could otherwise get silently replayed against the restored file on the next connection."""
    backup_path = build_database.DB_BACKUPS_DIR / name
    if not backup_path.is_file() or backup_path.parent != build_database.DB_BACKUPS_DIR:
        return RedirectResponse(url="/settings?backup=Unknown+backup+file&ok=0", status_code=303)
    build_database.backup_database_file(min_interval_seconds=0)
    for suffix in ("-wal", "-shm"):
        sidecar = DB_PATH.with_name(DB_PATH.name + suffix)
        if sidecar.exists():
            sidecar.unlink()
    import shutil as _shutil
    _shutil.copy2(backup_path, DB_PATH)
    _relaunch_and_exit()
    return templates.TemplateResponse(request, "shutdown.html", {"mode": "restart"})


def _relaunch_and_exit():
    """Relaunches the toolkit on the same port, then exits this process -- shared by /restart and
    /backup/restore (a restored db file should never be read by a process that might still have
    stale WAL/cache state from before the restore). Spawns a detached relauncher (its own console,
    CREATE_NEW_CONSOLE, so it keeps running after this process exits) that waits 2s for the port
    to free up, then runs start.bat -- reusing start.bat's own xi_tinkerer/database checks rather
    than re-implementing them here.

    Confirmed live this session: a one-line `cmd /c "timeout ... && start.bat"` relied on a cwd
    that wasn't reliably inherited through this cmd/timeout/CREATE_NEW_CONSOLE chain (start.bat
    itself works fine -- the failure was purely "'start.bat' is not recognized", a PATH-lookup
    problem from cmd's own quoting rules, not a logic bug). Writing a tiny real relauncher .bat
    with the full absolute path baked in, then spawning THAT, sidesteps cmd's /c quoting entirely
    instead of fighting it."""
    relauncher = TOOLS_ROOT / "mission_reports" / "_relaunch.bat"
    relauncher.parent.mkdir(parents=True, exist_ok=True)
    relauncher.write_text(
        f'@echo off\r\ntimeout /t 2 /nobreak >nul\r\ncall "{TOOLS_ROOT / "start.bat"}"\r\n',
        encoding="utf-8",
    )
    subprocess.Popen(
        ["cmd", "/c", str(relauncher)],
        creationflags=subprocess.CREATE_NEW_CONSOLE,
    )
    threading.Timer(0.5, lambda: os._exit(0)).start()


@app.post("/shutdown", response_class=HTMLResponse)
def shutdown_server(request: Request):
    """Stops the toolkit process cleanly. os._exit (not sys.exit) is deliberate -- this is a
    single-user local dev tool with nothing to flush on shutdown (SQLite connections are already
    opened/closed per-request, never held open across requests), so a hard exit is safe and
    avoids uvicorn's own graceful-shutdown machinery, which isn't reachable from inside a request
    handler without holding a reference to the running Server object. The 0.5s delay lets this
    response actually reach the browser before the process dies."""
    threading.Timer(0.5, lambda: os._exit(0)).start()
    return templates.TemplateResponse(request, "shutdown.html", {"mode": "shutdown"})


@app.post("/restart", response_class=HTMLResponse)
def restart_server(request: Request):
    """Relaunches the toolkit on the same port -- real fix for the Paths section's own note that
    a Settings change "takes effect the next time gui_server.py is restarted, not the next
    request."."""
    _relaunch_and_exit()
    return templates.TemplateResponse(request, "shutdown.html", {"mode": "restart"})


if __name__ == "__main__":
    import uvicorn
    _con = get_con()
    _port = int(settings_mod.get(_con, "port") or settings_mod.DEFAULTS["port"])
    _con.close()
    uvicorn.run("gui_server:app", host="127.0.0.1", port=_port, reload=False)
