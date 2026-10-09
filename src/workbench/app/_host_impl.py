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
import argparse
import base64
import colorsys
import csv
import gzip
from collections import Counter
import io
import json
import os
import hashlib
import re
import subprocess
import sqlite3
import shutil
import tempfile
import threading
import zipfile
import uuid
from datetime import datetime
from pathlib import Path

from urllib.parse import quote
from fastapi import FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, PlainTextResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates

import yaml
from PIL import Image, ImageDraw

from workbench.captures.ingestion import build_index as build_capture_index
from workbench.devtools.indexing import build_database
from workbench.devtools.reference.dialog import build_index as build_dialog_index
from workbench.devtools.indexing import build_npc_index
from workbench.devtools.indexing import build_sql_index
from workbench.devtools.spatial import build_visual_cache as build_zone_visual_cache
from workbench.devtools.entities import profile as entity_profile
from workbench.devtools.server import explore_event
from workbench.devtools.features import trace as feature_trace
from workbench.core.services.feature_trace_catalog import present_relationships
from workbench.core.services.feature_trace_dossier import build_dossier
from workbench.core.services.feature_trace_binding_drilldown import binding_lookup as feature_trace_binding_lookup, behavior_engine_drilldown as feature_trace_behavior_engine_drilldown
from workbench.core.services.scripted_behavior_visualizer import (
    find_lsb_behavior_sources,
    find_behavior_sources_multi,
    inspect_lsb_behavior,
)
from workbench.core.services import timeline_alignment, packet_correlation
from workbench.core.services import capture_integrity, capture_spatial, capture_related_evidence
from workbench.captures import paths as capture_paths
from workbench.core.services.server_catalog_identity import sync_server_catalog_entities
from workbench.runtime.interaction_reconstruction import reconstruct_interaction_candidates
from workbench.analyzers.server import lua_events
from workbench.editors.character import gui as character_editor_gui
character_editor_router = character_editor_gui.router
from workbench.devtools.features import checker as feature_checker
from workbench.core.services.feature_trace_closure import build_feature_trace_closure
from workbench.client.dat import global_tables as ingest_global_tables
from workbench.runtime import addon_tools
from workbench.runtime import external_tools as install_external_tools
from workbench.devtools.indexing import build_lsb_index
from workbench.captures.video import ocr as youtube_chat_ocr
from workbench.packages.migration import lua_convert as backport_lua_convert
from workbench.packages.migration import sql_convert as backport_sql_convert
from workbench.validation.packages import binding_index as backport_binding_index
from workbench.validation.packages import binding_audit as backport_binding_audit
from workbench.validation.packages import lua_sanity as backport_lua_sanity_check
from workbench.packages.migration import orchestrator as backport_package
from workbench.migrations.legacy_package_service import run_legacy_package_workflow
from workbench.devtools.indexing import build_dsp_index
from workbench.devtools.indexing import build_topaz_index
from workbench.devtools.research.legacy_llm import client as llm_client
from workbench.devtools.research.legacy_llm import log as llm_log
from workbench.devtools.research.legacy_llm import db_tools as llm_db_tools
from workbench.devtools.reference import scrape_bg_wiki
from workbench.devtools.entities import lookup as lookup_entity
from workbench.packets import decode as packet_decode
from workbench.runtime import settings_store as settings_mod
from workbench.runtime.paths import REPO_ROOT
from workbench.devtools.reference import wiki_compile
from workbench.devtools.reference import wiki_evidence
from workbench.devtools.reference import wiki_jobs
from workbench.devtools.reference import wiki_claim_compare
from workbench.devtools.reference import wiki_document
from workbench.core.services import wiki_evidence_graph
from workbench.gui_shell import build_shell_context
from workbench.adapters.servers import LogicalRecord, adapter_for
from workbench.migrations.live_target_validation import DBAPITargetReader, persist_live_validation, validate_live_records
from workbench.migrations.package_review import package_review_summary_dict
from workbench.core.schema import Artifact, DependencyEdge, MigrationAction
from workbench.migrations.package_plan import build_package_plan
from workbench.migrations.package_manifest import build_package_manifest
from workbench.migrations.package_assembly import assemble_migration_package
from workbench.migrations.package_scope import (
    build_dependency_scope,
    save_scope_decision,
    set_scope_review_status,
)

TOOLS_ROOT = REPO_ROOT
DB_PATH = TOOLS_ROOT / "ffxi_zone_database.db"
WORKBENCH_DB = TOOLS_ROOT / "workbench.db"
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
app.include_router(character_editor_router)
from workbench.client.animlab.router import router as animlab_router
app.include_router(animlab_router)
# Live Client replay is explicitly read-only; no process discovery or write routes.
from workbench.runtime.live_client.registry import ReplayRegistry
from workbench.runtime.live_client.registry_api import create_registry_router
from workbench.runtime.live_client.replay_console import create_replay_console_router
live_client_replay_registry = ReplayRegistry()
# Only the explicitly configured offline JSONL recording is loaded.
from workbench.runtime.live_client.bootstrap import register_configured_replay
# Settings persist across restarts; explicit environment overrides remain optional.
from workbench.runtime.live_client.configuration import effective_replay_configuration
_live_client_settings_con = sqlite3.connect(str(settings_mod.DB_PATH))
try:
    _live_client_settings = settings_mod.get_all(_live_client_settings_con)
finally:
    _live_client_settings_con.close()
from workbench.runtime.live_client.startup import initialize_live_client
live_client_startup_error = initialize_live_client(
    live_client_replay_registry, _live_client_settings, os.environ)
if live_client_startup_error:
    print("[Live Client] " + live_client_startup_error)
app.include_router(create_registry_router(live_client_replay_registry))
def render_live_client_console(request: Request, style: str, body: str):
    # Both fragments come exclusively from the repository-owned console renderer.
    return templates.TemplateResponse(request, "live_client_console.html", {
        "request": request, "console_style": style, "console_body": body,
        "startup_error": live_client_startup_error,
    })

app.include_router(create_replay_console_router(render_live_client_console))
from workbench.runtime.live_client.setup_api import create_recording_upload_router
app.include_router(create_recording_upload_router(REPO_ROOT / "data" / "live_client_recordings", live_client_replay_registry))
from workbench.runtime.live_client.waypoint_library import WaypointLibrary
from workbench.runtime.live_client.waypoint_library_api import create_waypoint_library_router
app.include_router(create_waypoint_library_router(
    WaypointLibrary(REPO_ROOT / "data" / "live_client_waypoints" / "library.db"), live_client_replay_registry))

@app.post("/live-client/inspect-recording")
async def live_client_inspect_recording(request: Request):
    # Local admin-only setup surface: deny cross-origin attempts before accessing local paths.
    origin = request.headers.get("origin")
    if not origin or origin != str(request.base_url).rstrip("/"):
        raise HTTPException(status_code=403, detail="same-origin request required")
    body = await request.json()
    from workbench.runtime.live_client.inspection import inspect_recording
    try:
        return inspect_recording(body.get("path", ""))
    except (ValueError, OSError) as exc:
        raise HTTPException(status_code=422, detail=str(exc))

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
# Zone visual-mesh OBJs (build_zone_visual_cache.py) are real but large (tens of MB of ASCII
# text per zone) -- gzip compresses that ratio very well over the wire, worth it app-wide.
app.add_middleware(GZipMiddleware, minimum_size=1000)
if MAPS_DIR.exists():
    app.mount("/maps", StaticFiles(directory=str(MAPS_DIR)), name="maps")
STATIC_DIR = TOOLS_ROOT / "gui" / "static"
STATIC_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
BRANDING_DIR = STATIC_DIR / "branding"
BRANDING_DIR.mkdir(parents=True, exist_ok=True)
BRAND_ICON_MAX_BYTES = 2 * 1024 * 1024
BRAND_ICON_FORMATS = {
    "PNG": ".png",
    "JPEG": ".jpg",
    "WEBP": ".webp",
    "GIF": ".gif",
}
OCR_RUNS_DIR = TOOLS_ROOT / "mission_reports_v2" / "_ocr_runs"
OCR_RUNS_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/ocr_runs", StaticFiles(directory=str(OCR_RUNS_DIR)), name="ocr_runs")
KEY_EVIDENCE_ROOT = TOOLS_ROOT / "mission_reports_v2" / "_key_evidence"
KEY_EVIDENCE_ROOT.mkdir(parents=True, exist_ok=True)
KEY_EVIDENCE_MAX_BYTES = 20 * 1024 * 1024
KEY_EVIDENCE_IMAGE_TYPES = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/webp": ".webp",
    "image/bmp": ".bmp",
}


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
    sync_server_catalog_entities(con, WORKBENCH_DB)
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
    sync_server_catalog_entities(con, WORKBENCH_DB)
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
    sync_server_catalog_entities(con, WORKBENCH_DB)
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
    sync_server_catalog_entities(con, WORKBENCH_DB)
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


def shell_context(request: Request) -> dict:
    """Shared read-only navigation/context model for every template extending base.html."""
    con = get_con()
    try:
        current_settings = settings_mod.get_all(con)
    finally:
        con.close()
    return build_shell_context(
        path=request.url.path,
        method=request.method,
        settings=current_settings,
        default_topaz_root=settings_mod.DEFAULT_TOPAZ_ROOT,
        default_backport_root=settings_mod.DEFAULT_BACKPORT_ROOT,
        detected_client_path=settings_mod.get_ffxi_install(),
        workspace_slug=request.query_params.get("workspace"),
        shell_override=request.query_params.get("shell"),
    )


templates.env.globals["shell_context"] = shell_context


def _rq_exclude(con, col="capture_id"):
    """' AND col NOT IN (<quarantined captures>)' for cross-capture statistics (see review_queue.exclude_sql)."""
    from workbench.captures import review_queue as rq
    return rq.exclude_sql(con, col)


def review_pending() -> int:
    """Number of pending capture exceptions (drives the warning badge); never raises."""
    try:
        from workbench.captures import review_queue as _rq
        con = get_con()
        try:
            return _rq.pending_count(con)
        finally:
            con.close()
    except Exception:
        return 0


templates.env.globals["review_pending"] = review_pending


def capture_review_items(capture_id) -> list:
    """Pending exceptions for one capture (detail-page banner); never raises."""
    try:
        from workbench.captures import review_queue as _rq
        con = get_con()
        try:
            return [dict(r, label=_rq.KINDS.get(r["kind"], {}).get("label", r["kind"]),
                         blocking=_rq.KINDS.get(r["kind"], {}).get("blocking", False))
                    for r in _rq.items(con, "pending", capture_id=int(capture_id))]
        finally:
            con.close()
    except Exception:
        return []


templates.env.globals["capture_review_items"] = capture_review_items

# The packaged Character Editor router owns its own Jinja2Templates; base.html needs the globals above.
character_editor_gui.templates.env.globals.update(templates.env.globals)


@app.get("/help", response_class=HTMLResponse)
def help_page(request: Request):
    return templates.TemplateResponse(request, "help.html", {})


@app.get("/captures/help", response_class=HTMLResponse)
def capture_help_page(request: Request):
    """Static capture ingestion support matrix and known-gap reference."""
    return templates.TemplateResponse(request, "capture_help.html", {})


@app.get("/captures/review", response_class=HTMLResponse)
def capture_review_queue(request: Request, status: str = "pending", kind: str = "", msg: str = ""):
    """Exception queue: captures with missing/unverified data. Blocking kinds are quarantined from derived
    pipelines until decided; the raw data stays browsable everywhere."""
    from workbench.captures import review_queue as rq
    con = get_con()
    try:
        allrows = rq.items(con, "all")
        zones = [r[0] for r in con.execute("SELECT name FROM zones ORDER BY name")]
        labels = {r[0]: r[1] for r in con.execute("SELECT capture_id, capture_label FROM captures")}
    finally:
        con.close()
    counts = {k: sum(1 for r in allrows if r["status"] == k) for k in ("pending", "resolved", "dismissed", "auto_resolved")}
    kind_counts = {k: sum(1 for r in allrows if r["kind"] == k and r["status"] == "pending") for k in rq.KINDS}
    shown = [r for r in allrows if (status == "all" or r["status"] == status) and (not kind or r["kind"] == kind)]
    for r in shown:
        r["capture_label"] = labels.get(r["capture_id"], "")
        if isinstance(r["detail"].get("candidates"), list):      # items stored before post details were added
            r["detail"]["candidates"] = [c if isinstance(c, dict) else {"title": c} for c in r["detail"]["candidates"]]
    return templates.TemplateResponse(request, "capture_review.html", {
        "rows": shown, "zones": zones, "counts": counts, "status": status, "kind": kind,
        "kinds": rq.KINDS, "kind_counts": kind_counts, "msg": msg})


@app.get("/captures/zone-review")
def capture_zone_review_legacy():
    return RedirectResponse(url="/captures/review?kind=zone", status_code=301)


@app.post("/captures/review/{review_id}")
def capture_review_decide(review_id: int, action: str = Form(...), value: str = Form(""), note: str = Form(""),
                          status: str = Form("pending"), kind: str = Form(""), uploader: str = Form(""),
                          post_date: str = Form(""), video_url: str = Form(""), capture_type: str = Form("")):
    from workbench.captures import review_queue as rq
    from urllib.parse import quote
    con = get_con()
    try:
        v = value.strip()
        it = con.execute("SELECT kind FROM review_queue WHERE review_id=?", (review_id,)).fetchone()
        if it and it[0] == "zone":
            v = v.upper().replace(" ", "_")
        if action == "enter":                      # manual source info typed on the review page
            import json as _json
            action, v = "resolve", _json.dumps({"uploader": uploader, "post_date": post_date,
                                                "video_url": video_url, "capture_type": capture_type})
        rq.decide(con, review_id, action, v or None, note.strip() or None)
        msg = "Review #%d %s." % (review_id, "resolved" if action == "resolve" else "dismissed")
    except (ValueError, KeyError) as e:
        msg = "Not saved: %s" % e
    finally:
        con.close()
    return RedirectResponse(url="/captures/review?status=%s&kind=%s&msg=%s" % (quote(status), quote(kind), quote(msg)), status_code=303)


@app.get("/captures/metadata-template.csv")
def capture_metadata_template(scope: str = "pending"):
    """CSV sheet to fill in capture source info (uploader, date, video, type) and re-import."""
    from workbench.captures import source_info as si
    con = get_con()
    try:
        body = si.template_csv(con, "blank" if scope == "blank" else "pending")
    finally:
        con.close()
    return Response(body, media_type="text/csv", headers={
        "Content-Disposition": 'attachment; filename="capture_source_info_%s.csv"' % ("blank" if scope == "blank" else "pending")})


@app.get("/captures/metadata-import", response_class=HTMLResponse)
def capture_metadata_import_page(request: Request):
    from workbench.captures import source_info as si
    con = get_con()
    try:
        types = si.allowed_types(con)
        npend = con.execute("SELECT COUNT(*) FROM review_queue WHERE kind='manifest_link' AND status='pending'").fetchone()[0]
    finally:
        con.close()
    return templates.TemplateResponse(request, "capture_metadata_import.html", {
        "types": types, "columns": si.COLUMNS, "npend": npend, "rep": None})


@app.post("/captures/metadata-import", response_class=HTMLResponse)
async def capture_metadata_import(request: Request, sheet: UploadFile = File(...), mode: str = Form("validate"),
                                  overwrite: str = Form("")):
    from workbench.captures import source_info as si
    text = (await sheet.read()).decode("utf-8-sig", errors="replace")
    con = get_con()
    try:
        rep = si.import_csv(con, text, dry_run=(mode != "apply"), overwrite=bool(overwrite))
        types = si.allowed_types(con)
        npend = con.execute("SELECT COUNT(*) FROM review_queue WHERE kind='manifest_link' AND status='pending'").fetchone()[0]
    finally:
        con.close()
    return templates.TemplateResponse(request, "capture_metadata_import.html", {
        "types": types, "columns": si.COLUMNS, "npend": npend, "rep": rep, "applied_mode": mode == "apply"})


@app.get("/captures/bulk-ingest", response_class=HTMLResponse)
def capture_bulk_ingest_page(request: Request, error: str = ""):
    from workbench.captures import bulk_ingest as bi
    return templates.TemplateResponse(request, "capture_bulk_ingest.html", {
        "plan": None, "error": error, "running": bi.current_job(), "jobs": bi.recent_jobs()})


@app.get("/captures/bulk-ingest/browse")
def capture_bulk_ingest_browse(path: str = ""):
    from workbench.captures import bulk_ingest as bi
    try:
        return bi.browse(path)
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)


@app.post("/captures/bulk-ingest/scan", response_class=HTMLResponse)
def capture_bulk_ingest_scan(request: Request, root: str = Form(""), mode: str = Form("archives"),
                             content_type: str = Form("instances"), recursive: str = Form("")):
    from workbench.captures import bulk_ingest as bi
    con = get_con()
    plan, error = None, ""
    try:
        plan = bi.scan(con, root, mode, content_type.strip() or "instances", bool(recursive))
    except (ValueError, OSError) as e:
        error = str(e)
    finally:
        con.close()
    return templates.TemplateResponse(request, "capture_bulk_ingest.html", {
        "plan": plan, "error": error, "running": bi.current_job(), "jobs": bi.recent_jobs()})


@app.post("/captures/bulk-ingest/run")
async def capture_bulk_ingest_run(token: str = Form(...), override: str = Form(""), overwrite_sheet: str = Form(""),
                                  sheet: UploadFile = File(None)):
    from workbench.captures import bulk_ingest as bi
    from urllib.parse import quote
    text = None
    if sheet is not None and sheet.filename:
        text = (await sheet.read()).decode("utf-8-sig", errors="replace")
    try:
        job = bi.start(token, bool(override), text, bool(overwrite_sheet))
    except (ValueError, PermissionError, RuntimeError) as e:
        return RedirectResponse("/captures/bulk-ingest?error=" + quote(str(e)), status_code=303)
    return RedirectResponse("/captures/bulk-ingest/job/" + job["id"], status_code=303)


@app.get("/captures/bulk-ingest/job/{job_id}", response_class=HTMLResponse)
def capture_bulk_ingest_job(request: Request, job_id: str):
    from workbench.captures import bulk_ingest as bi
    job = bi.get_job(job_id)
    if not job:
        raise HTTPException(404, "unknown job (jobs are kept in memory; finished jobs are also saved under bulk_ingest_jobs/)")
    return templates.TemplateResponse(request, "capture_bulk_job.html", {"job": job, "summary": bi.summary(job)})


@app.post("/captures/bulk-ingest/job/{job_id}/cancel")
def capture_bulk_ingest_cancel(job_id: str):
    from workbench.captures import bulk_ingest as bi
    bi.cancel(job_id)
    return RedirectResponse("/captures/bulk-ingest/job/" + job_id, status_code=303)


@app.get("/captures/{capture_id}/review-flags")
def capture_review_flags(capture_id: int):
    from workbench.captures import review_queue as rq
    con = get_con()
    try:
        return JSONResponse([{k: r[k] for k in ("review_id", "kind", "status", "key")} for r in rq.items(con, "pending", capture_id=capture_id)])
    finally:
        con.close()


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
def install_tool(tool: str, back: str = "/"):
    """Auto-downloads one of the optional external tools/data straight from its real GitHub
    source (install_external_tools.py) instead of the user needing to find, download, and place
    it by hand. Same synchronous-request pattern as /rebuild/{source} above -- FFXI-DATS is a
    real ~200MB download, so this button can take a minute or so.

    A tool name starting with "addon-" (e.g. "addon-bg-wiki-dump") is routed to addon_tools.py's
    own install_addon() instead -- a LOCAL package (see addons/*.zip) rather than a network fetch,
    same real (ok, message) return shape so this one route can drive both without the template/
    button needing to know which kind a given row is.

    `back` lets a caller other than the home page (e.g. /ocr's Prerequisites section) point the
    redirect back at itself instead of always landing on "/" -- must be a same-app relative path,
    query-string forwarded via its own param names (installed/ok/detail) so home.html's
    rebuilt/rebuilt_ok/rebuilt_detail handling isn't disturbed."""
    from urllib.parse import quote
    if tool.startswith(ADDON_PREFIX):
        ok, message = addon_tools.install_addon(tool[len(ADDON_PREFIX):])
    elif tool in install_external_tools.INSTALLERS:
        ok, message = install_external_tools.INSTALLERS[tool]()
    else:
        return RedirectResponse(url="/?rebuilt=&ok=0&detail=Unknown+tool", status_code=303)
    if not back.startswith("/") or back.startswith("//"):
        back = "/"
    if back == "/ocr":
        return RedirectResponse(
            url=f"/ocr?installed={tool}&ok={1 if ok else 0}&detail={quote(message)}", status_code=303
        )
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


@app.get("/items")
def items_search(q: str = "", status: str = "all"):
    """Retired: the LSB-vs-external catalogue table now lives in the Item Browser (Reference filter)."""
    from urllib.parse import urlencode
    qs = {k: v for k, v in (("q", q), ("ref", "" if status == "all" else status)) if v}
    return RedirectResponse(url="/itembrowser" + ("?" + urlencode(qs) if qs else ""), status_code=301)


@app.get("/items/{itemid}")
def item_detail(itemid: int):
    """Retired: per-item detail and the catalogue/Topaz comparison are in the Item Browser panel."""
    return RedirectResponse(url=f"/itembrowser#{itemid}", status_code=301)


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
def bindings_index(request: Request, q: str = "", status: str = "", page: int = 1, trace_q: str = ""):
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
        "status_labels": STATUS_LABELS, "index_missing": index_missing, "trace_q": trace_q,
    })


@app.get("/backport/sql-convert", response_class=HTMLResponse)
def sql_convert_form(request: Request):
    """Paste-INSERT-statements-in, get-DSP-shaped-INSERTs-out page, plus a real id-collision check
    AND a real content-duplication check (added 2026-09-15, see data/dsp_sql_schema_map.json's
    mob_groups warning) against DSP's already-indexed data (dsp_* tables from build_dsp_index.py)
    -- not just a raw dump diff. Same backport_enabled() gate as the Lua converter/ID Drift."""
    return templates.TemplateResponse(request, "backport_sql_convert.html", {
        "source": "", "table": "npc_list", "converted": "", "warnings": [], "collisions": None,
        "duplication": None,
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
    duplication = None
    if result.converted_ids:
        con = get_con()
        try:
            collisions = backport_sql_convert.check_id_collisions(
                con, table, result.converted_ids, schema_map, id_to_name=result.id_to_name,
            )
            if table in backport_sql_convert.CONTENT_KEY_COLUMNS:
                duplication = backport_sql_convert.check_content_duplication(con, table, rows, schema_map)
        finally:
            con.close()

    return templates.TemplateResponse(request, "backport_sql_convert.html", {
        "source": source, "table": table, "converted": result.converted_sql,
        "warnings": result.warnings, "collisions": collisions, "duplication": duplication, "ran": True,
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

    result=run_legacy_package_workflow(
        package_dir,
        dsp_root,
        target=target,
        zone_table=zone_table,
        id_shape=id_shape,
        id_file_hint=id_file_hint,
        verify_only=verify_only,
    )
    if result.get("status")=="ERROR":
        ctx["error"]=result.get("error")
        return templates.TemplateResponse(request, "backport_package.html", ctx)

    ctx["report"]={
        key:result[key]
        for key in (
            "lua_result","sql_result","binding_result","sanity_result",
            "collision_results","duplication_results","overall_clean",
            "report_path","report_md","schema_map",
        )
    }
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

    schema_map = backport_sql_convert.load_schema_map()
    lua_result = None
    sql_result = None
    if not verify_only:
        if lua_src.is_dir():
            lua_result = backport_package.convert_lua_tree(
                lua_src, lua_dst, target, zone_table, id_shape, id_file_hint)
        sql_result = backport_package.convert_sql_tree(sql_src, sql_dst, schema_map)
    elif not lua_dst.is_dir():
        ctx["error"] = f"Verify-only needs an existing {lua_dst} -- run a real conversion first."
        return templates.TemplateResponse(request, "backport_package.html", ctx)

    binding_result = backport_binding_audit.audit_package(lua_dst, dsp_root, flavor) if lua_dst.is_dir() else \
        {"confirmed": [], "missing": []}
    sanity_result = backport_lua_sanity_check.check_package(lua_dst) if lua_dst.is_dir() else \
        {"syntax_errors": [], "undeclared_globals": []}

    collision_results = {}
    duplication_results = {}
    if sql_result and sql_result["ids_by_table"]:
        collision_results = backport_package.run_id_collision_checks(
            sql_result["ids_by_table"], sql_result["id_to_name_by_table"], schema_map)
        duplication_results = backport_package.run_content_duplication_checks(
            sql_result.get("rows_by_table", {}), schema_map)

    report_md = backport_package.build_report(
        package_dir, target, dsp_root, flavor, lua_result, sql_result,
        binding_result, sanity_result, collision_results, duplication_results, schema_map)
    (package_dir / "BACKPORT_REPORT.md").write_text(report_md, encoding="utf-8", newline="\n")

    overall_clean = (
        (lua_result is None or lua_result["total_flags"] == 0)
        and not binding_result["missing"]
        and not sanity_result["syntax_errors"]
        and not sanity_result["undeclared_globals"]
        and not any(r.get("name_mismatch") for r in collision_results.values())
        and not any(r.get("duplicates") for r in duplication_results.values())
    )

    ctx["report"] = {
        "lua_result": lua_result, "sql_result": sql_result, "binding_result": binding_result,
        "sanity_result": sanity_result, "collision_results": collision_results,
        "duplication_results": duplication_results,
        "overall_clean": overall_clean, "report_path": str(package_dir / "BACKPORT_REPORT.md"),
        "report_md": report_md, "schema_map": schema_map,
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
if you're unsure of a column name -- it ALSO returns any known real relationship to other tables,
e.g. calling it on mob_groups tells you dropid links to mob_droplist.dropid, so use it before
guessing at a join column or giving up on a multi-table question):
- dsp_mob_pools (poolid, name, norm_name, familyid, modelid) -- one row per mob TYPE (not spawn).
- dsp_mob_groups (zoneid, groupid, poolid, name, respawntime, minLevel, maxLevel, dropid) -- one
  row per spawned mob GROUP; links a zone+pool to its level range and real drop table.
- dsp_mob_skills (mob_skill_id, mob_anim_id, name, norm_name, aoe, distance, ...) -- one row per
  mob skill definition, matched by `name` (e.g. WHERE name = 'firespit').
- dsp_mob_spawn_points (mobid, mobname, norm_name, groupid, pos_x/y/z, pos_rot) -- one row per
  actual spawned mob instance in the world; groupid links to mob_groups.groupid.
- dsp_npc_list (npcid, name, norm_name, zoneid, pos_x/y/z, entityFlags) -- non-mob NPCs.
- dsp_item_basic (itemid, name, norm_name, stackSize, ...) -- items.
- dsp_mob_droplist (dropid, dropType, groupId, groupRate, itemId, itemRate) -- drop tables;
  itemId links to item_basic.itemid.
- zones (zoneid, name, geometry_mapid, geometry_rom_path) -- the ONE shared, unprefixed table
  (every other table above has real dsp_/lsb_/topaz_/sql_ copies; zones does not).
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


def _behavior_roots(server: str = "") -> dict:
    """Configured script trees for the Behavior Inspector, in priority order.

    The toolkit administers whichever server the user configured (Topaz, DSP or LandSandBoat),
    not just LSB. The active Zone Plot server is searched first, then LSB, then the remaining
    tree; trees that aren't configured or don't exist on disk are left out. `server` narrows to
    one tree ("topaz" | "dsp" | "lsb").
    """
    candidates = {
        "topaz": settings_mod.get_topaz_root(),
        "dsp": settings_mod.get_dsp_root(),
        "lsb": build_lsb_index.LSB_ROOT,
    }
    try:
        active = zone_plot.get_server()
    except Exception:
        active = "topaz"
    order = [active] + [k for k in ("lsb", "topaz", "dsp") if k != active]
    roots = {
        k: Path(candidates[k]) for k in order
        if candidates.get(k) and (Path(candidates[k]) / "scripts" / "zones").is_dir()
    }
    if server:
        roots = {k: v for k, v in roots.items() if k == server}
    return roots


def _entity_behavior_summary(profile: dict) -> dict:
    """Try each configured server tree in priority order and keep the first that resolves."""
    roots = _behavior_roots()
    if not roots:
        return _entity_behavior_summary_for_root(profile, "lsb", build_lsb_index.LSB_ROOT)
    first = None
    for name, root in roots.items():
        out = _entity_behavior_summary_for_root(profile, name, root)
        if out.get("available"):
            return out
        first = first or out
    return first


def _entity_behavior_summary_for_root(profile: dict, server: str, root: Path) -> dict:
    """Project the existing Behavior Inspector into a bounded Entity summary.

    Source resolution is against the configured LSB tree. Entity Profile's raw lua_hits may come
    from another indexed server tree, so never assume the same relative path exists in LSB.
    """
    out = {
        "available": False,
        "server": server,
        "source": None,
        "error": None,
        "hooks": [],
        "api_calls": [],
        "effects": [],
        "events": [],
        "states": [],
        "transitions": [],
        "shared_helpers": [],
        "callback_ownership": [],
        "scheduled_callbacks": [],
        "summary": {},
        "contexts": 0,
    }
    if not root.is_dir():
        out["error"] = f"{server} source root is not available."
        return out

    zone = str(profile.get("zone_folder") or "")
    script_guess = str(profile.get("script_name_guess") or "")
    candidates = []

    # Reuse an already-known path only when it really exists in the LSB checkout.
    existing = profile.get("behavior_source")
    if existing:
        candidate = root / str(existing).replace("\\", "/")
        if candidate.is_file():
            candidates.append({
                "path": str(existing).replace("\\", "/"),
                "zone": zone,
                "name": candidate.stem,
                "role": "entity",
            })

    if not candidates:
        query = script_guess or str(profile.get("name") or "")
        matches = find_lsb_behavior_sources(root, query, limit=100) if query else []
        exact = [
            row for row in matches
            if (not zone or row.get("zone") == zone)
            and (
                not script_guess
                or str(row.get("name") or "").replace("_", "").lower()
                   == script_guess.replace("_", "").lower()
            )
        ]
        candidates = exact or [
            row for row in matches if not zone or row.get("zone") == zone
        ]

    if not candidates:
        out["error"] = f"No matching {server} behavior source was resolved for this entity."
        return out

    chosen = sorted(candidates, key=lambda row: (
        0 if row.get("role") in {"npc", "mob", "entity"} else 1,
        str(row.get("path") or ""),
    ))[0]
    try:
        result = inspect_lsb_behavior(root, chosen["path"])
    except Exception as exc:
        out["error"] = f"{type(exc).__name__}: {exc}"
        return out

    graph = result["graph"]
    nodes = graph.get("nodes") or []
    out["available"] = True
    out["source"] = result["source"]
    out["summary"] = graph.get("summary") or {}
    out["contexts"] = len(result.get("contexts") or [])
    out["hooks"] = sorted(
        {node["label"] for node in nodes if node.get("kind") == "hook"}
    )

    api_seen = set()
    for node in nodes:
        meta = node.get("meta") or {}
        if node.get("kind") != "effect" or meta.get("effect") != "API_CALL":
            continue
        call_meta = meta.get("metadata") or {}
        qualified = call_meta.get("qualified_name") or node.get("label")
        key = (meta.get("hook"), qualified, call_meta.get("line"))
        if key in api_seen:
            continue
        api_seen.add(key)
        out["api_calls"].append({
            "qualified_name": qualified,
            "function": call_meta.get("function"),
            "receiver": call_meta.get("receiver"),
            "hook": meta.get("hook"),
            "line": call_meta.get("line"),
            "source_line": call_meta.get("source_line"),
        })
    out["api_calls"] = out["api_calls"][:24]

    effect_seen = set()
    omitted = {"API_CALL", "EXECUTE_CALLBACK"}
    for node in nodes:
        meta = node.get("meta") or {}
        effect = meta.get("effect")
        if node.get("kind") != "effect" or not effect or effect in omitted:
            continue
        key = (meta.get("hook"), effect, str(meta.get("target")), str(meta.get("value")))
        if key in effect_seen:
            continue
        effect_seen.add(key)
        out["effects"].append({
            "effect": effect,
            "target": meta.get("target"),
            "value": meta.get("value"),
            "hook": meta.get("hook"),
            "category": meta.get("category"),
            "source_lines": meta.get("source_lines"),
        })
    out["effects"] = out["effects"][:24]

    out["events"] = list(graph.get("events") or [])[:16]
    out["states"] = list(graph.get("states") or [])[:16]
    out["transitions"] = list(graph.get("transitions") or [])[:16]
    out["shared_helpers"] = [
        {
            "qualified_name": row.get("qualified_name"),
            "status": row.get("status"),
        }
        for row in (result.get("shared_helpers") or [])[:16]
    ]

    # Consolidate callback/hook ownership from the already-parsed Behavior Inspector graph.
    # This is presentation-only: source spans and counts come directly from graph nodes.
    owners = {}
    def owner_for(hook):
        key = hook or "source"
        return owners.setdefault(key, {
            "hook": key,
            "source_path": (result.get("source") or {}).get("path"),
            "start_line": None,
            "end_line": None,
            "rule_count": 0,
            "effect_count": 0,
            "api_call_count": 0,
            "event_ids": set(),
            "scheduled_callbacks": 0,
        })
    for node in nodes:
        meta = node.get("meta") or {}
        if node.get("kind") == "rule":
            owner = owner_for(meta.get("hook"))
            owner["rule_count"] += 1
            span = meta.get("source_lines") or ()
            if len(span) >= 2 and span[0] is not None and span[1] is not None:
                owner["start_line"] = span[0] if owner["start_line"] is None else min(owner["start_line"], span[0])
                owner["end_line"] = span[1] if owner["end_line"] is None else max(owner["end_line"], span[1])
        elif node.get("kind") == "callback":
            owner = owner_for(meta.get("hook"))
            owner["scheduled_callbacks"] += 1
            out["scheduled_callbacks"].append({
                "hook": meta.get("hook"),
                "callback_type": meta.get("callback_type"),
                "callback_event": meta.get("callback_event"),
                "delay": meta.get("callback_delay_source"),
                "source_path": meta.get("source_path"),
                "source_lines": meta.get("source_lines"),
            })
    for row in out["effects"]:
        owner_for(row.get("hook"))["effect_count"] += 1
    for row in out["api_calls"]:
        owner_for(row.get("hook"))["api_call_count"] += 1
    for event in out["events"]:
        event_id = event.get("event_id")
        for hook in (
            list(event.get("start_hooks") or [])
            + list(event.get("update_guard_hooks") or [])
            + list(event.get("finish_guard_hooks") or [])
        ):
            if event_id is not None:
                owner_for(hook)["event_ids"].add(event_id)
    out["callback_ownership"] = [
        {
            **row,
            "event_ids": sorted(row["event_ids"], key=lambda value: str(value)),
        }
        for _hook, row in sorted(owners.items())
    ][:24]
    out["scheduled_callbacks"] = out["scheduled_callbacks"][:24]
    return out


def _entity_relationship_summary(profile: dict, catalog_con: sqlite3.Connection) -> dict:
    """Return only depth-1 canonical graph relationships for the Entity dossier."""
    out = {
        "available": False,
        "node_id": None,
        "incoming": [],
        "outgoing": [],
        "provider_relationships": [],
        "error": None,
    }
    graph_con = _workbench_graph_connection()
    if graph_con is None:
        out["error"] = "Canonical Workbench graph is not available."
        return out
    try:
        npcid = str(profile.get("npcid"))
        tables = {
            row[0] for row in graph_con.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        node_id = None
        if "entity_identifiers" in tables:
            rows = graph_con.execute(
                """SELECT entity_id,identifier_type
                   FROM entity_identifiers
                   WHERE identifier_value=?
                   ORDER BY CASE identifier_type
                     WHEN 'npcid' THEN 0
                     WHEN 'entity_id' THEN 1
                     WHEN 'id' THEN 2
                     ELSE 9 END, entity_id
                   LIMIT 10""",
                (npcid,),
            ).fetchall()
            if rows:
                node_id = rows[0][0]

        if node_id is None:
            matches = feature_trace.search_nodes(graph_con, npcid, catalog_con)
            exact = [
                row for row in matches
                if str(row.get("numeric_id", "")) == npcid
                or str(row.get("node_id", "")) == npcid
            ]
            if exact:
                node_id = exact[0]["node_id"]

        if node_id is None:
            out["error"] = "No canonical graph node is currently mapped to this entity ID."
            return out

        traced = feature_trace.trace(
            graph_con, node_id, 1, "both", catalog_con,
            include_runtime_edges=False, max_nodes=250,
        )
        out["available"] = True
        out["node_id"] = node_id
        out["provider_relationships"] = traced.get("provider_relationships") or []

        def neighbor_info(edge):
            incoming = edge["target_node"] == node_id
            neighbor = edge["source_node"] if incoming else edge["target_node"]
            info = feature_trace.node_info(graph_con, neighbor, catalog_con)
            rep = (info.get("representations") or [{}])[0]
            return {
                "relationship_id": edge.get("relationship_id"),
                "relationship": edge.get("relationship"),
                "confidence": edge.get("confidence"),
                "status": edge.get("status"),
                "evidence_id": edge.get("evidence_id"),
                "node_id": neighbor,
                "display_name": rep.get("display_name") or neighbor,
                "node_type": rep.get("node_type") or "UNKNOWN",
                "table": rep.get("table"),
                "incoming": incoming,
            }

        for edge in traced.get("edges") or []:
            row = neighbor_info(edge)
            if row["incoming"]:
                out["incoming"].append(row)
            else:
                out["outgoing"].append(row)

        key = lambda row: (
            str(row.get("relationship") or ""),
            str(row.get("display_name") or "").casefold(),
            str(row.get("node_id") or ""),
        )
        out["incoming"] = sorted(out["incoming"], key=key)[:80]
        out["outgoing"] = sorted(out["outgoing"], key=key)[:80]
        return out
    except Exception as exc:
        out["error"] = f"{type(exc).__name__}: {exc}"
        return out
    finally:
        graph_con.close()


@app.get("/entity/{npcid}", response_class=HTMLResponse)
def entity_detail(request: Request, npcid: int, q: str = "", page: int = 1):
    """Dedicated profile page. When reached from a name search, prev/next cycles through that
    search's current page of results (q/page carried as query params) -- the same "cycle through
    them" pattern as /captures/{id}. Registered as a plain path param, so like /captures/{id} it
    must come after any other more specific /entity/* route (none currently exist, but keep this
    at the bottom of the /entity routes if one is ever added)."""
    con = get_con()
    profile = entity_profile.build_profile(con, npcid)
    profile["behavior_summary"] = (
        _entity_behavior_summary(profile) if not profile.get("error") else {}
    )
    if ((profile.get("behavior_summary") or {}).get("source") or {}).get("path"):
        # Prefer the verified LSB path for UI handoff. Keep raw server-source lua_hits separately.
        profile["behavior_source"] = profile["behavior_summary"]["source"]["path"]
        profile["behavior_server"] = profile["behavior_summary"].get("server") or ""
    profile["relationship_summary"] = (
        _entity_relationship_summary(profile, con) if not profile.get("error") else {}
    )
    profile["feature_trace_path"] = {}
    if not profile.get("error"):
        graph_con = _workbench_graph_connection()
        if graph_con is not None:
            try:
                path = feature_trace.entity_implementation_path(graph_con, con, str(npcid))
                if path:
                    profile["feature_trace_path"] = {
                        "available": True,
                        "mapping_status": path.get("mapping_status"),
                        "canonical_root": path.get("canonical_root"),
                        "canonical_mapped": bool(path.get("canonical_mapped")),
                        "representation_count": path.get("representation_count", 0),
                        "branch_count": len(path.get("branches") or []),
                        "provider_counts": path.get("provider_counts") or [],
                        "native_link_count": path.get("native_link_count", 0),
                        "direct_relationship_count": (path.get("canonical") or {}).get("direct_relationship_count", 0),
                        "direct_evidence_count": (path.get("canonical") or {}).get("direct_evidence_count", 0),
                        "coverage_cues": path.get("coverage_cues") or [],
                        "href": f"/features/trace?q={npcid}&depth=3&direction=both",
                    }
            except Exception as exc:
                profile["feature_trace_path"] = {
                    "available": False,
                    "error": f"{type(exc).__name__}: {exc}",
                    "href": f"/features/trace?q={npcid}&depth=3&direction=both",
                }
            finally:
                graph_con.close()

    # Add client-event dossier status to runtime-observed CSIDs without forcing a new client
    # export merely because Entity Profile was opened. If Events/CSID already has this zone
    # exported, reuse its fingerprinted health cache.
    profile["event_wiring"] = []
    if not profile.get("error") and profile.get("zone_folder"):
        event_dir = TOOLS_ROOT / "mission_reports" / profile["zone_folder"]
        health = {}
        if (event_dir / "events.yml").exists():
            try:
                health = explore_event.scan_event_health(event_dir, profile.get("zoneid"))
            except Exception:
                health = {}
        rows_by_key = health.get("rows") or {}

        observed_by_id = {}
        for observed in profile.get("capture_events") or []:
            event_hex = observed.get("event_hex")
            if not event_hex:
                continue
            try:
                event_id = int(str(event_hex), 0)
            except ValueError:
                continue
            bucket = observed_by_id.setdefault(event_id, {
                "count": 0, "message_ids": set(),
            })
            bucket["count"] += int(observed.get("count") or 0)
            if observed.get("message_id") is not None:
                bucket["message_ids"].add(int(observed["message_id"]))

        event_ids = set(observed_by_id)
        prefix = f"{int(npcid)}:"
        for key in rows_by_key:
            if key.startswith(prefix):
                try:
                    event_ids.add(int(key.split(":", 1)[1]))
                except ValueError:
                    pass

        for event_id in sorted(event_ids):
            health_row = rows_by_key.get(f"{int(npcid)}:{event_id}", {})
            observed = observed_by_id.get(event_id, {"count": 0, "message_ids": set()})
            client_messages = [int(v) for v in health_row.get("message_ids") or []]
            runtime_messages = sorted(observed["message_ids"])
            profile["event_wiring"].append({
                "event_id": event_id,
                "event_hex": f"0x{event_id:04X}",
                "client_defined": bool(health_row),
                "runtime_observed": bool(observed["count"]),
                "count": observed["count"],
                "runtime_message_ids": runtime_messages,
                "decompile_status": health_row.get("status", "not_scanned"),
                "decompile_detail": health_row.get("detail"),
                "message_ids": client_messages,
                "href": (
                    f"/events/view?zone={quote(profile['zone_folder'], safe='')}"
                    f"&entity={npcid}&csid={event_id}"
                ),
            })

    entity_profile.synthesize_implementation_actions(profile)

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


def _parse_dialog_id_query(value: str) -> int | None:
    value = (value or "").strip()
    if not value:
        return None
    try:
        if value.lower().startswith("0x"):
            return int(value, 16)
        if value.isdigit():
            return int(value, 10)
    except ValueError:
        return None
    return None


def _dialog_event_refs(zone_name: str, zoneid: int | None) -> dict[int, list[dict]]:
    """Read cached client-CSID message references without triggering a fresh event export.

    Dialog browsing must stay cheap. If the Events/CSID tool has already produced events.yml for
    this zone, refresh/use its fingerprinted health cache; otherwise simply report no cached refs.
    """
    if not zone_name or zoneid is None:
        return {}
    out_dir = TOOLS_ROOT / "mission_reports" / zone_name
    if not (out_dir / "events.yml").exists():
        return {}
    try:
        health = explore_event.scan_event_health(out_dir, zoneid)
    except Exception:
        return {}
    refs = {}
    for message_id, rows in (health.get("message_refs") or {}).items():
        try:
            refs[int(message_id)] = list(rows)
        except (TypeError, ValueError):
            continue
    return refs


def _enrich_dialog_rows(con: sqlite3.Connection, rows: list[dict], zone_name: str, zoneid: int | None) -> list[dict]:
    event_refs = _dialog_event_refs(zone_name, zoneid) if zoneid is not None else {}
    tables = {row[0] for row in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    has_drift = "dialog_drift_report" in tables
    has_capture_events = "capture_events" in tables and "captures" in tables

    for item in rows:
        zid = int(item["zoneid"])
        idx = int(item["idx"])

        item["id_hex"] = f"0x{idx:04X}"
        item["drift_rows"] = []
        if has_drift:
            item["drift_rows"] = [
                dict(row) for row in con.execute(
                    """SELECT constant_name,wired_id,commented_text,real_text,status,zone_content_tags
                       FROM dialog_drift_report WHERE zoneid=? AND wired_id=?
                       ORDER BY constant_name""",
                    (zid, idx),
                ).fetchall()
            ]

        item["prev_dialog"] = None
        item["next_dialog"] = None
        prev_row = con.execute(
            "SELECT idx,text FROM dialog_text WHERE zoneid=? AND idx<? ORDER BY idx DESC LIMIT 1",
            (zid, idx),
        ).fetchone()
        next_row = con.execute(
            "SELECT idx,text FROM dialog_text WHERE zoneid=? AND idx>? ORDER BY idx ASC LIMIT 1",
            (zid, idx),
        ).fetchone()
        if prev_row:
            item["prev_dialog"] = {"idx": prev_row["idx"], "text": prev_row["text"]}
        if next_row:
            item["next_dialog"] = {"idx": next_row["idx"], "text": next_row["text"]}

        item["runtime_count"] = 0
        item["runtime_rows"] = []
        if has_capture_events:
            item["runtime_count"] = con.execute(
                "SELECT COUNT(*) FROM capture_events WHERE message_id=? AND "
                "(zone_db=? OR replace(lower(zone_db),' ','_')=replace(lower(?),' ','_'))"
                + _rq_exclude(con),
                (idx, item["zone"], item["zone"]),
            ).fetchone()[0]
            item["runtime_rows"] = [
                dict(row) for row in con.execute(
                    """SELECT e.capture_id,c.capture_label,e.seq,e.entity_id,e.entity_name,
                              e.event_hex,e.option,e.direction,e.opcode,e.opcode_name
                       FROM capture_events e
                       LEFT JOIN captures c ON c.capture_id=e.capture_id
                       WHERE e.message_id=?
                         AND (e.zone_db=? OR replace(lower(e.zone_db),' ','_')=replace(lower(?),' ','_'))"""
                    + _rq_exclude(con, "e.capture_id") + """
                       ORDER BY e.capture_id,e.seq LIMIT 5""",
                    (idx, item["zone"], item["zone"]),
                ).fetchall()
            ]

        item["event_refs"] = event_refs.get(idx, []) if zid == zoneid else []

    return rows


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
            results.append({"zoneid": zoneid, "zone": zone.upper(), "idx": r["idx"], "text": r["text"]})
    if q:
        q_dialog_id = _parse_dialog_id_query(q)
        if q_dialog_id is not None:
            # Exact dialog id lookup. Accept decimal or 0x-prefixed hex. Across all zones unless
            # a zone is picked, since the same numeric id can mean different text per zone.
            count_sql = "SELECT COUNT(*) FROM dialog_text WHERE idx = ?"
            sql = "SELECT zoneid, idx, text FROM dialog_text WHERE idx = ?"
            params = [q_dialog_id]
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
                # FTS5 treats punctuation/quotes/operators as query syntax. For ad-hoc dialog
                # research a literal fallback is more useful than an empty result set.
                like_sql = "SELECT zoneid,idx,text FROM dialog_text WHERE text LIKE ?"
                like_count = "SELECT COUNT(*) FROM dialog_text WHERE text LIKE ?"
                like_params = [f"%{q}%"]
                if zoneid is not None:
                    like_sql += " AND zoneid=?"
                    like_count += " AND zoneid=?"
                    like_params.append(zoneid)
                total = con.execute(like_count, like_params).fetchone()[0]
                rows = con.execute(
                    like_sql + " ORDER BY zoneid,idx LIMIT ? OFFSET ?",
                    like_params + [DIALOG_PAGE_SIZE, offset],
                ).fetchall()
        for r in rows:
            zname = con.execute("SELECT name FROM zones WHERE zoneid = ?", (r["zoneid"],)).fetchone()
            results.append({"zoneid": r["zoneid"], "zone": zname[0] if zname else "?", "idx": r["idx"], "text": r["text"]})

    total_pages = max(1, (total + DIALOG_PAGE_SIZE - 1) // DIALOG_PAGE_SIZE)
    results = _enrich_dialog_rows(con, results, zone.upper() if zone else "", zoneid)
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


def _workbench_graph_connection() -> sqlite3.Connection | None:
    """Open the canonical Workbench graph only when it already exists.

    GUI inspection must never create an empty graph database merely because a page was opened.
    """
    if not WORKBENCH_DB.is_file():
        return None
    con = sqlite3.connect(WORKBENCH_DB)
    con.row_factory = sqlite3.Row
    required = {"features", "entity_relationships", "capability_requirements"}
    tables = {row[0] for row in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if not required.issubset(tables):
        con.close()
        return None
    return con


def _package_project_root() -> Path:
    return settings_mod.get_backport_root().resolve()


def _package_candidates(limit: int = 250) -> list[dict]:
    root = _package_project_root()
    rows = []
    if not root.is_dir():
        return rows
    for manifest_path in root.rglob("WORKBENCH_PACKAGE_MANIFEST.json"):
        package_root = manifest_path.parent
        try:
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        migration = payload.get("migration") or {}
        try:
            relative = package_root.relative_to(root).as_posix()
        except ValueError:
            continue
        rows.append({
            "relative_path": relative or ".",
            "package_name": package_root.name,
            "migration_id": migration.get("migration_id"),
            "feature_id": migration.get("feature_id"),
            "source_family": migration.get("source_family"),
            "target_family": migration.get("target_family"),
            "manifest_status": migration.get("status") or "UNKNOWN",
            "step_count": len((payload.get("execution") or {}).get("steps") or []),
            "manifest_mtime": manifest_path.stat().st_mtime,
        })
        if len(rows) >= limit:
            break
    rows.sort(key=lambda row: (-row["manifest_mtime"], row["relative_path"]))
    return rows


def _resolve_package_root(relative_path: str) -> Path:
    project_root = _package_project_root()
    candidate = (project_root / relative_path).resolve()
    try:
        candidate.relative_to(project_root)
    except ValueError as exc:
        raise ValueError("Package path must stay inside the configured project root.") from exc
    if not (candidate / "WORKBENCH_PACKAGE_MANIFEST.json").is_file():
        raise ValueError("Selected folder is not an assembled Workbench package.")
    return candidate


def _package_migrations() -> list[dict]:
    con = _workbench_graph_connection()
    if con is None:
        return []
    try:
        rows = con.execute(
            "SELECT m.migration_id, m.feature_id, m.source_snapshot_id, m.target_snapshot_id, "
            "m.status, m.metadata_json, COUNT(a.action_id) AS action_count "
            "FROM migrations m LEFT JOIN migration_actions a ON a.migration_id=m.migration_id "
            "GROUP BY m.migration_id ORDER BY m.migration_id"
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        con.close()


def _safe_package_destination(relative_name: str) -> Path:
    project_root = _package_project_root()
    name = relative_name.strip().replace("\\", "/")
    if not name:
        raise ValueError("Package destination is required.")
    rel = Path(name)
    if rel.is_absolute() or ".." in rel.parts:
        raise ValueError("Package destination must be a relative path inside the configured project root.")
    candidate = (project_root / rel).resolve()
    try:
        candidate.relative_to(project_root)
    except ValueError as exc:
        raise ValueError("Package destination must stay inside the configured project root.") from exc
    return candidate


@app.get("/packages/scope", response_class=HTMLResponse)
def packages_scope_review(
    request: Request,
    migration_id: str = "",
    q: str = "",
    decision: str = "",
    depth: int = 6,
):
    migrations = _package_migrations()
    scope = None
    error = None
    con = _workbench_graph_connection()
    try:
        if migration_id.strip():
            if con is None:
                raise ValueError("Canonical Workbench graph is not available.")
            scope = build_dependency_scope(
                con,
                migration_id.strip(),
                max_depth=max(0, min(depth, 12)),
            )
            if q.strip() or decision.strip():
                query = q.strip().lower()
                wanted = decision.strip().upper()
                filtered = []
                for item in scope["items"]:
                    if query and query not in (
                        str(item.get("node_id") or "") + " "
                        + str(item.get("display_name") or "") + " "
                        + str(item.get("artifact_path") or "") + " "
                        + " ".join(item.get("tags") or ())
                    ).lower():
                        continue
                    if wanted and item.get("effective_decision") != wanted:
                        continue
                    filtered.append(item)
                scope = {**scope, "items": filtered}
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
    finally:
        if con is not None:
            con.close()
    return templates.TemplateResponse(request, "packages_scope.html", {
        "request": request,
        "migrations": migrations,
        "migration_id": migration_id,
        "q": q,
        "decision": decision,
        "depth": depth,
        "scope": scope,
        "error": error,
    })


@app.post("/packages/scope/decision", response_class=HTMLResponse)
def packages_scope_decision(
    migration_id: str = Form(...),
    node_id: str = Form(...),
    decision: str = Form(...),
    reason: str = Form(""),
    tags: str = Form(""),
):
    con = _workbench_graph_connection()
    try:
        if con is None:
            raise ValueError("Canonical Workbench graph is not available.")
        save_scope_decision(
            con,
            migration_id.strip(),
            node_id.strip(),
            decision,
            reason=reason,
            tags=[tag.strip() for tag in tags.split(",") if tag.strip()],
        )
        set_scope_review_status(con, migration_id.strip(), "DRAFT")
    finally:
        if con is not None:
            con.close()
    return RedirectResponse(
        f"/packages/scope?migration_id={quote(migration_id.strip(), safe='')}",
        status_code=303,
    )


@app.post("/packages/scope/review", response_class=HTMLResponse)
def packages_scope_mark_reviewed(
    migration_id: str = Form(...),
    notes: str = Form(""),
):
    con = _workbench_graph_connection()
    try:
        if con is None:
            raise ValueError("Canonical Workbench graph is not available.")
        scope = build_dependency_scope(con, migration_id.strip())
        if scope["closure_status"] in {"BLOCKED", "MANUAL_REQUIRED"}:
            raise ValueError(
                f"Scope cannot be marked reviewed while closure status is {scope['closure_status']}."
            )
        set_scope_review_status(
            con,
            migration_id.strip(),
            "REVIEWED",
            notes=notes.strip() or None,
            scope_hash=scope["scope_hash"],
        )
    finally:
        if con is not None:
            con.close()
    return RedirectResponse(
        f"/packages/scope?migration_id={quote(migration_id.strip(), safe='')}",
        status_code=303,
    )


@app.get("/packages/create", response_class=HTMLResponse)
def packages_create_page(request: Request):
    return templates.TemplateResponse(request, "packages_create.html", {
        "request": request,
        "migrations": _package_migrations(),
        "form": {
            "migration_id": "",
            "source_root": "",
            "source_family": "LSB",
            "target_family": "DSP",
            "package_path": "packages/",
        },
        "result": None,
        "error": None,
    })


@app.post("/packages/create", response_class=HTMLResponse)
def packages_create_run(
    request: Request,
    migration_id: str = Form(...),
    source_root: str = Form(...),
    source_family: str = Form(...),
    target_family: str = Form(...),
    package_path: str = Form(...),
):
    form = {
        "migration_id": migration_id,
        "source_root": source_root,
        "source_family": source_family,
        "target_family": target_family,
        "package_path": package_path,
    }
    result = None
    error = None
    con = _workbench_graph_connection()
    try:
        if con is None:
            raise ValueError("Canonical Workbench graph is not available.")
        migration = con.execute(
            "SELECT migration_id, feature_id, source_snapshot_id, target_snapshot_id, status, metadata_json "
            "FROM migrations WHERE migration_id=?",
            (migration_id.strip(),),
        ).fetchone()
        if migration is None:
            raise ValueError("Selected migration was not found.")

        scope = build_dependency_scope(con, migration_id.strip())
        if scope["review"]["status"] != "REVIEWED" or scope["package_gate"] not in {"READY", "MANUAL_REQUIRED"}:
            raise ValueError(
                "Dependency scope is not ready for package creation: "
                f"{scope['package_gate']} (review={scope['review']['status']}). "
                "Review /packages/scope first."
            )
        scope_by_node = {item["node_id"]: item for item in scope["items"]}

        action_rows = con.execute(
            "SELECT action_id, migration_id, action, artifact_id, status, reason, metadata_json "
            "FROM migration_actions WHERE migration_id=? ORDER BY action_id",
            (migration_id.strip(),),
        ).fetchall()
        if not action_rows:
            raise ValueError("Selected migration has no MigrationAction records.")

        actions = []
        artifact_ids = set()
        for row in action_rows:
            metadata = json.loads(row["metadata_json"] or "{}")
            action = MigrationAction(
                action_id=row["action_id"],
                migration_id=row["migration_id"],
                action=row["action"],
                artifact_id=row["artifact_id"],
                status=row["status"],
                reason=row["reason"],
                metadata=metadata if isinstance(metadata, dict) else {},
            )
            scope_item = scope_by_node.get(action.artifact_id) if action.artifact_id else None
            effective = scope_item.get("effective_decision") if scope_item else "INCLUDE"
            if effective in {"EXCLUDE", "TARGET_EQUIVALENT", "NOT_REQUIRED"}:
                action = MigrationAction(
                    action_id=action.action_id,
                    migration_id=action.migration_id,
                    action="NOT_REQUIRED",
                    artifact_id=action.artifact_id,
                    status="COMPATIBLE",
                    reason=(
                        f"Scope decision {effective}: "
                        + str(scope_item.get("reason") or "reviewed exclusion")
                    ),
                    metadata={**action.metadata, "scope_decision": effective},
                )
            actions.append(action)
            if action.artifact_id:
                artifact_ids.add(action.artifact_id)

        existing_action_artifacts = {a.artifact_id for a in actions if a.artifact_id}
        for item in scope["items"]:
            if (
                item.get("effective_decision") == "INCLUDE"
                and item.get("node_kind") == "ARTIFACT"
                and item.get("node_id") not in existing_action_artifacts
            ):
                artifact_id = item["node_id"]
                actions.append(MigrationAction(
                    action_id=f"scope-include:{migration_id.strip()}:{artifact_id}",
                    migration_id=migration_id.strip(),
                    action="MANUAL_REVIEW",
                    artifact_id=artifact_id,
                    status="MANUAL_REQUIRED",
                    reason="User included transitive dependency during package scope review.",
                    metadata={
                        "scope_decision": "INCLUDE",
                        "discovery_path": item.get("discovery_path") or [],
                        "relationship": item.get("relationship"),
                    },
                ))
                artifact_ids.add(artifact_id)
                existing_action_artifacts.add(artifact_id)

        artifacts = []
        for artifact_id in sorted(artifact_ids):
            row = con.execute(
                "SELECT artifact_id, artifact_type, path, source_snapshot_id, target_snapshot_id, "
                "feature_id, metadata_json FROM artifacts WHERE artifact_id=?",
                (artifact_id,),
            ).fetchone()
            if row is None:
                continue
            metadata = json.loads(row["metadata_json"] or "{}")
            artifacts.append(Artifact(
                artifact_id=row["artifact_id"],
                artifact_type=row["artifact_type"],
                path=row["path"],
                source_snapshot_id=row["source_snapshot_id"],
                target_snapshot_id=row["target_snapshot_id"],
                feature_id=row["feature_id"],
                metadata=metadata if isinstance(metadata, dict) else {},
            ))

        dependencies = []
        if artifact_ids:
            placeholders = ",".join("?" for _ in artifact_ids)
            params = tuple(sorted(artifact_ids)) * 2
            rows = con.execute(
                "SELECT relationship_id, source_node, target_node, relationship, evidence_id, "
                "confidence, status, metadata_json, source_snapshot_id "
                f"FROM entity_relationships WHERE source_node IN ({placeholders}) "
                f"AND target_node IN ({placeholders})",
                params,
            ).fetchall()
            for row in rows:
                dependencies.append(DependencyEdge(
                    edge_id=row["relationship_id"],
                    source_node=row["source_node"],
                    target_node=row["target_node"],
                    relationship=row["relationship"],
                    evidence_id=row["evidence_id"],
                    confidence=row["confidence"],
                    status=row["status"],
                    notes=row["metadata_json"],
                    source_snapshot_id=row["source_snapshot_id"],
                ))

        source_path = Path(source_root).expanduser().resolve()
        if not source_path.is_dir():
            raise ValueError("Source root does not exist or is not a directory.")

        package_root = _safe_package_destination(package_path)
        if package_root.exists() and any(package_root.iterdir()):
            raise ValueError("Package destination already exists and is not empty; creation does not overwrite existing packages.")

        plan = build_package_plan(actions, dependencies)
        manifest = build_package_manifest(
            plan,
            artifacts,
            feature_id=migration["feature_id"],
            source_snapshot_id=migration["source_snapshot_id"],
            target_snapshot_id=migration["target_snapshot_id"],
            source_family=source_family.strip(),
            target_family=target_family.strip(),
        )
        manifest["schema"] = 3
        manifest["dependency_scope"] = {
            "schema": scope["schema"],
            "closure_status": scope["closure_status"],
            "package_gate": scope["package_gate"],
            "review": scope["review"],
            "counts": scope["counts"],
            "discovered_count": scope["discovered_count"],
            "items": scope["items"],
        }
        assembly = assemble_migration_package(
            manifest,
            source_path,
            package_root,
            overwrite=False,
        )
        relative = package_root.relative_to(_package_project_root()).as_posix()
        result = {
            "status": assembly.status,
            "package_path": relative,
            "plan_status": plan.status,
            "validation_status": assembly.validation_status,
            "copied": list(assembly.source_result.copied),
            "missing": list(assembly.source_result.missing),
            "skipped": list(assembly.source_result.skipped),
            "execution_step_count": len(manifest.get("execution", {}).get("steps", [])),
            "excluded_action_count": len(manifest.get("excluded_actions", [])),
        }
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
    finally:
        if con is not None:
            con.close()

    return templates.TemplateResponse(request, "packages_create.html", {
        "request": request,
        "migrations": _package_migrations(),
        "form": form,
        "result": result,
        "error": error,
    })


@app.get("/packages", response_class=HTMLResponse)
def packages_library(request: Request, q: str = ""):
    project_root = _package_project_root()
    packages = _package_candidates()
    if q.strip():
        term = q.strip().lower()
        packages = [
            row for row in packages
            if term in str(row.get("relative_path") or "").lower()
            or term in str(row.get("migration_id") or "").lower()
            or term in str(row.get("feature_id") or "").lower()
        ]
    return templates.TemplateResponse(request, "packages_library.html", {
        "request": request,
        "q": q,
        "project_root": str(project_root),
        "packages": packages,
    })


@app.get("/packages/review", response_class=HTMLResponse)
def packages_review(
    request: Request,
    package: str = "",
    target_root: str = "",
):
    candidates = _package_candidates()
    review = None
    manifest = {}
    validation = {}
    error = None
    selected_package = package.strip()
    configured_target = settings_mod.get_dsp_root()
    selected_target = target_root.strip() or (str(configured_target) if configured_target else "")
    if selected_package:
        try:
            package_root = _resolve_package_root(selected_package)
            if not selected_target:
                raise ValueError(
                    "Target root is required for patch-lifecycle drift/readiness checks. "
                    "Configure a DSP server path or provide a target root."
                )
            target_path = Path(selected_target).expanduser().resolve()
            if not target_path.exists():
                raise ValueError("Target root does not exist.")
            review = package_review_summary_dict(package_root, target_path)
            manifest_path = package_root / "WORKBENCH_PACKAGE_MANIFEST.json"
            validation_path = package_root / "WORKBENCH_VALIDATION_PACKAGE.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            if validation_path.is_file():
                validation = json.loads(validation_path.read_text(encoding="utf-8"))
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
    return templates.TemplateResponse(request, "packages_review.html", {
        "request": request,
        "packages": candidates,
        "package": selected_package,
        "target_root": selected_target,
        "review": review,
        "manifest": manifest,
        "validation": validation,
        "error": error,
    })


@app.get("/validation", response_class=HTMLResponse)
def validation_dashboard(request: Request):
    con = _workbench_graph_connection()
    runs = []
    status_counts = {}
    result_counts = {}
    total_results = 0
    error = None
    if con is None:
        error = "Canonical Workbench graph is not available. Build/import workbench.db before browsing validation history."
    else:
        rows = con.execute(
            "SELECT run_id, name, source_snapshot_id, target_snapshot_id, feature_id, status, "
            "started_at, finished_at, metadata_json "
            "FROM validation_runs ORDER BY COALESCE(finished_at, started_at, '') DESC, run_id DESC LIMIT 25"
        ).fetchall()
        runs = [dict(row) for row in rows]
        for row in con.execute("SELECT status, COUNT(*) AS n FROM validation_runs GROUP BY status ORDER BY status"):
            status_counts[row["status"] or "UNKNOWN"] = row["n"]
        for row in con.execute("SELECT status, COUNT(*) AS n FROM validation_results GROUP BY status ORDER BY status"):
            result_counts[row["status"] or "UNKNOWN"] = row["n"]
        total_results = sum(result_counts.values())
        con.close()
    return templates.TemplateResponse(request, "validation_dashboard.html", {
        "request": request,
        "runs": runs,
        "status_counts": status_counts,
        "result_counts": result_counts,
        "total_results": total_results,
        "error": error,
    })


@app.get("/validation/runs", response_class=HTMLResponse)
def validation_runs_page(request: Request, q: str = "", status: str = ""):
    con = _workbench_graph_connection()
    runs = []
    statuses = []
    error = None
    if con is None:
        error = "Canonical Workbench graph is not available. Build/import workbench.db before browsing validation history."
    else:
        statuses = [row[0] for row in con.execute(
            "SELECT DISTINCT status FROM validation_runs WHERE status IS NOT NULL ORDER BY status"
        ).fetchall()]
        clauses = []
        params = []
        if q.strip():
            clauses.append("(run_id LIKE ? OR name LIKE ? OR feature_id LIKE ?)")
            pattern = f"%{q.strip()}%"
            params.extend([pattern, pattern, pattern])
        if status.strip():
            clauses.append("status=?")
            params.append(status.strip())
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        rows = con.execute(
            "SELECT vr.run_id, vr.name, vr.source_snapshot_id, vr.target_snapshot_id, vr.feature_id, "
            "vr.status, vr.started_at, vr.finished_at, vr.metadata_json, "
            "COUNT(res.validation_id) AS result_count "
            "FROM validation_runs vr LEFT JOIN validation_results res ON res.run_id=vr.run_id"
            + where +
            " GROUP BY vr.run_id ORDER BY COALESCE(vr.finished_at, vr.started_at, '') DESC, vr.run_id DESC",
            params,
        ).fetchall()
        runs = [dict(row) for row in rows]
        con.close()
    return templates.TemplateResponse(request, "validation_runs.html", {
        "request": request,
        "q": q,
        "status": status,
        "statuses": statuses,
        "runs": runs,
        "error": error,
    })


@app.get("/validation/runs/{run_id}", response_class=HTMLResponse)
def validation_run_detail(request: Request, run_id: str):
    con = _workbench_graph_connection()
    run = None
    results = []
    error = None
    if con is None:
        error = "Canonical Workbench graph is not available. Build/import workbench.db before browsing validation history."
    else:
        row = con.execute(
            "SELECT run_id, name, source_snapshot_id, target_snapshot_id, feature_id, status, "
            "started_at, finished_at, metadata_json FROM validation_runs WHERE run_id=?",
            (run_id,),
        ).fetchone()
        if row is not None:
            run = dict(row)
            results = [dict(result) for result in con.execute(
                "SELECT validation_id, run_id, validation_type, subject_id, status, evidence_id, "
                "source, target, notes_json FROM validation_results WHERE run_id=? "
                "ORDER BY validation_type, validation_id",
                (run_id,),
            ).fetchall()]
        con.close()
    return templates.TemplateResponse(request, "validation_run_detail.html", {
        "request": request,
        "run": run,
        "results": results,
        "error": error,
        "run_id": run_id,
    })


def _live_validation_record(row: dict) -> LogicalRecord:
    logical_type = str(row["logical_type"])
    return LogicalRecord(
        logical_type=logical_type,
        identity=tuple((str(k), v) for k, v in row.get("identity", [])),
        fields=dict(row.get("fields") or {}),
        source_family=str(row.get("source_family") or "UNKNOWN"),
        source_table=str(row.get("source_table") or logical_type),
        notes=tuple(str(x) for x in row.get("notes", [])),
    )


def _live_validation_payload(raw: str) -> tuple[str, list[LogicalRecord], dict]:
    payload = json.loads(raw)
    logical_type = payload.get("logical_type")
    rows = payload.get("records")
    if not isinstance(logical_type, str) or not logical_type:
        raise ValueError("Expected JSON requires a non-empty logical_type.")
    if not isinstance(rows, list):
        raise ValueError("Expected JSON requires records[].")
    records = [_live_validation_record(row) for row in rows]
    if any(record.logical_type != logical_type for record in records):
        raise ValueError("Every record.logical_type must match payload logical_type.")
    return logical_type, records, payload


@app.get("/validation/live-target", response_class=HTMLResponse)
def validation_live_target_page(request: Request):
    example = {
        "logical_type": "item_basic",
        "records": [{
            "logical_type": "item_basic",
            "identity": [["itemid", 0]],
            "fields": {"itemid": 0},
            "source_family": "UNKNOWN",
            "source_table": "item_basic",
        }],
    }
    return templates.TemplateResponse(request, "validation_live_target.html", {
        "request": request,
        "form": {
            "target_family": "DSP",
            "target_root": "",
            "backend": "sqlite",
            "sqlite_db": "",
            "host": "127.0.0.1",
            "port": "3306",
            "user": "",
            "database": "",
            "password_env": "FFXI_DB_PASSWORD",
            "target_snapshot_id": "",
            "source_snapshot_id": "",
            "feature_id": "",
            "run_id": "",
            "persist": False,
            "expected_json": json.dumps(example, indent=2),
        },
        "result": None,
        "error": None,
    })


@app.post("/validation/live-target", response_class=HTMLResponse)
def validation_live_target_run(
    request: Request,
    target_family: str = Form(...),
    target_root: str = Form(""),
    backend: str = Form("sqlite"),
    sqlite_db: str = Form(""),
    host: str = Form("127.0.0.1"),
    port: int = Form(3306),
    user: str = Form(""),
    database: str = Form(""),
    password_env: str = Form("FFXI_DB_PASSWORD"),
    target_snapshot_id: str = Form(""),
    source_snapshot_id: str = Form(""),
    feature_id: str = Form(""),
    run_id: str = Form(""),
    expected_json: str = Form(...),
    persist: str | None = Form(None),
):
    form = {
        "target_family": target_family,
        "target_root": target_root,
        "backend": backend,
        "sqlite_db": sqlite_db,
        "host": host,
        "port": str(port),
        "user": user,
        "database": database,
        "password_env": password_env,
        "target_snapshot_id": target_snapshot_id,
        "source_snapshot_id": source_snapshot_id,
        "feature_id": feature_id,
        "run_id": run_id,
        "persist": persist is not None,
        "expected_json": expected_json,
    }
    result = None
    error = None
    connection = None
    try:
        logical_type, records, input_payload = _live_validation_payload(expected_json)
        adapter = adapter_for(target_family, Path(target_root or "."))
        backend_name = backend.strip().lower()
        if backend_name == "sqlite":
            if not sqlite_db.strip():
                raise ValueError("SQLite database path is required.")
            db_path = Path(sqlite_db).expanduser().resolve()
            connection = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
            paramstyle = "qmark"
            connection_label = f"sqlite:{db_path}"
        elif backend_name in {"mysql", "mariadb"}:
            if not database.strip() or not user.strip():
                raise ValueError("Database name and user are required for MySQL/MariaDB.")
            env_name = password_env.strip() or "FFXI_DB_PASSWORD"
            password = os.environ.get(env_name)
            if password is None:
                raise ValueError(f"Environment variable {env_name} is not set.")
            try:
                import mysql.connector
            except ImportError as exc:
                raise RuntimeError("mysql-connector-python is required for MySQL/MariaDB live validation.") from exc
            connection = mysql.connector.connect(
                host=host.strip() or "127.0.0.1",
                port=port,
                user=user.strip(),
                password=password,
                database=database.strip(),
            )
            paramstyle = "format"
            connection_label = f"mysql:{adapter.family}"
        else:
            raise ValueError("Backend must be sqlite or mysql/mariadb.")

        reader = DBAPITargetReader(connection, paramstyle=paramstyle)
        result = validate_live_records(
            adapter,
            reader,
            logical_type,
            records,
            target_snapshot_id=target_snapshot_id.strip() or input_payload.get("target_snapshot_id"),
        )
        result = {
            **result,
            "target_family": adapter.family,
            "target_adapter_id": adapter.adapter_id,
            "connection_backend": backend_name,
            "credentials_persisted": False,
        }
        if persist is not None:
            selected_run_id = run_id.strip() or f"run:live-target:{logical_type}"
            result["canonical_validation"] = persist_live_validation(
                result,
                WORKBENCH_DB,
                run_id=selected_run_id,
                feature_id=feature_id.strip() or None,
                source_snapshot_id=source_snapshot_id.strip() or input_payload.get("source_snapshot_id"),
                target_snapshot_id=target_snapshot_id.strip() or input_payload.get("target_snapshot_id"),
                source="GUI normalized payload",
                target=connection_label,
            )
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
    finally:
        if connection is not None:
            try:
                connection.close()
            except Exception:
                pass

    return templates.TemplateResponse(request, "validation_live_target.html", {
        "request": request,
        "form": form,
        "result": result,
        "error": error,
    })


@app.get("/behavior", response_class=HTMLResponse)
def behavior_visualizer_page(
    request: Request,
    q: str = "",
    source: str = "",
    server: str = "",
):
    """Inspect scripted behavior in whichever server tree is configured (Topaz, DSP or LSB)
    without promoting same-zone context to dependency truth."""
    matches=[]
    result=None
    error=None
    roots=_behavior_roots()
    if not roots:
        error=("No server script tree is available. Configure a Topaz or DSP path on the Settings "
               "page, or install the LandSandBoat checkout.")
    elif source.strip():
        pick=server if server in roots else next(iter(roots))
        try:
            result=inspect_lsb_behavior(roots[pick],source.strip())
            server=pick
        except FileNotFoundError:
            # Path isn't in the requested/primary tree; try the others before giving up.
            for name,root in roots.items():
                if name == pick:
                    continue
                try:
                    result=inspect_lsb_behavior(root,source.strip())
                    server=name
                    break
                except Exception:
                    continue
            if result is None:
                error=f"{source.strip()} was not found in any configured server tree ({', '.join(roots)})."
        except Exception as exc:
            error=f"{type(exc).__name__}: {exc}"
    elif q.strip():
        matches=find_behavior_sources_multi(_behavior_roots(server),q.strip(),limit=100)
        if len(matches)==1:
            try:
                result=inspect_lsb_behavior(roots[matches[0]["server"]],matches[0]["path"])
                source=matches[0]["path"]
                server=matches[0]["server"]
            except Exception as exc:
                error=f"{type(exc).__name__}: {exc}"
        elif not matches:
            error=f"No match for '{q.strip()}' in: {', '.join(roots)} (searched file names, then script contents)."
    return templates.TemplateResponse(request,"behavior_visualizer.html",{
        "request":request,
        "q":q,
        "source":source,
        "server":server,
        "servers":list(roots),
        "matches":matches,
        "result":result,
        "error":error,
    })


@app.get("/behavior/graph.json")
def behavior_visualizer_graph(source: str, server: str = ""):
    roots=_behavior_roots()
    if not roots:
        return JSONResponse({"error":"No server script tree is available."},status_code=404)
    pick=server if server in roots else next(iter(roots))
    try:
        result=inspect_lsb_behavior(roots[pick],source.strip())
        return JSONResponse({
            "server":pick,
            "source":result["source"],
            "graph":result["graph"],
            "contexts":result["contexts"],
            "notes":result["notes"],
        })
    except Exception as exc:
        return JSONResponse({"error":f"{type(exc).__name__}: {exc}"},status_code=400)


_FEATURE_TRACE_PROVIDER_SERVER = {
    "landsandboat": "lsb",
    "topaz": "topaz",
    "dsp": "dsp",
}


def _feature_trace_norm_source_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").casefold())


def _feature_trace_branch_source_drilldown(implementation_path: dict | None) -> None:
    """Attach bounded, read-only Lua source previews to exact server branches.

    Source text remains in configured server checkouts. We resolve only one exact normalized
    entity/script name inside the branch's provider tree; ambiguous matches stay unresolved.
    """
    if not implementation_path:
        return
    roots = _behavior_roots()
    numeric_id = implementation_path.get("numeric_id")
    for branch_row in implementation_path.get("branches") or []:
        provider = branch_row.get("provider")
        server = _FEATURE_TRACE_PROVIDER_SERVER.get(provider)
        source_root = roots.get(server) if server else None
        display_name = str((branch_row.get("root") or {}).get("display_name") or "").strip()
        drill = {
            "status": "UNAVAILABLE",
            "server": server,
            "query": display_name,
            "behavior_href": (
                f"/behavior?q={quote(display_name, safe='')}&server={quote(server or '', safe='')}"
                if display_name else None
            ),
            "source": None,
            "excerpt": None,
            "events": [],
            "hooks": [],
            "summary": {},
        }
        branch_row["source_drilldown"] = drill
        if not source_root or not display_name:
            continue
        try:
            matches = find_behavior_sources_multi({server: source_root}, display_name, limit=50)
        except Exception:
            drill["status"] = "SEARCH_ERROR"
            continue
        exact = [
            row for row in matches
            if _feature_trace_norm_source_name(row.get("name")) == _feature_trace_norm_source_name(display_name)
        ]
        if len(exact) != 1:
            drill["status"] = "AMBIGUOUS" if len(exact) > 1 else "SEARCH_ONLY"
            candidates = exact if exact else matches
            drill["candidate_count"] = len(candidates)
            drill["candidates"] = [
                {
                    "name": row.get("name"),
                    "path": row.get("path"),
                    "zone": row.get("zone"),
                    "role": row.get("role"),
                    "match": row.get("match"),
                    "href": (
                        f"/behavior?source={quote(str(row.get('path') or ''), safe='')}"
                        f"&server={quote(server or '', safe='')}"
                    ),
                }
                for row in candidates[:8]
                if row.get("path")
            ]
            drill["match_basis"] = (
                "multiple exact-normalized script/entity names"
                if exact else "fuzzy/content Behavior Inspector matches only"
            )
            continue
        chosen = exact[0]
        try:
            inspected = inspect_lsb_behavior(source_root, chosen["path"])
        except Exception as exc:
            drill["status"] = "INSPECT_ERROR"
            drill["error"] = f"{type(exc).__name__}: {exc}"
            continue

        relative_path = str((inspected.get("source") or {}).get("path") or chosen["path"]).replace("\\", "/")
        candidate = (Path(source_root) / relative_path).resolve()
        root_resolved = Path(source_root).resolve()
        excerpt = None
        if candidate.is_file() and (candidate == root_resolved or root_resolved in candidate.parents):
            try:
                lines = candidate.read_text(encoding="utf-8", errors="replace").splitlines()
                preview_lines = lines[:40]
                excerpt = {
                    "start_line": 1,
                    "end_line": len(preview_lines),
                    "text": "\n".join(preview_lines),
                    "truncated": len(lines) > len(preview_lines),
                    "total_lines": len(lines),
                }
            except OSError:
                excerpt = None

        graph_data = inspected.get("graph") or {}
        engine = feature_trace_behavior_engine_drilldown(
            inspected,server=server,source_root=source_root
        )
        events = []
        zone = (inspected.get("source") or {}).get("zone") or chosen.get("zone")
        for event in (graph_data.get("events") or [])[:20]:
            event_id = event.get("event_id")
            if event_id is None:
                continue
            events.append({
                "event_id": event_id,
                "href": (
                    f"/events/view?zone={quote(str(zone or ''), safe='')}"
                    f"&entity={numeric_id}&csid={event_id}"
                    if zone and numeric_id is not None else None
                ),
                "start_hooks": list(event.get("start_hooks") or []),
                "update_hooks": list(event.get("update_guard_hooks") or []),
                "finish_hooks": list(event.get("finish_guard_hooks") or []),
            })
        drill.update({
            "status": "RESOLVED",
            "match_basis": "one exact-normalized script/entity name in the provider tree",
            "source": {
                "path": relative_path,
                "zone": zone,
                "subject": (inspected.get("source") or {}).get("subject") or display_name,
                "role": chosen.get("role"),
            },
            "behavior_href": f"/behavior?source={quote(relative_path, safe='')}&server={quote(server, safe='')}",
            "graph_href": f"/behavior/graph.json?source={quote(relative_path, safe='')}&server={quote(server, safe='')}",
            "excerpt": excerpt,
            "events": events,
            "hooks": sorted({
                node.get("label") for node in (graph_data.get("nodes") or [])
                if node.get("kind") == "hook" and node.get("label")
            }),
            "summary": graph_data.get("summary") or {},
            "engine": engine,
        })


@app.get("/features/trace", response_class=HTMLResponse)
def feature_trace_page(
    request: Request,
    q: str = "",
    depth: int = 3,
    direction: str = "both",
):
    depth = max(0, min(depth, 8))
    if direction not in {"out", "in", "both"}:
        direction = "both"
    result = None
    matches = []
    implementation_path = None
    query_diagnostics = None
    error = None
    con = _workbench_graph_connection()
    catalog_con = get_con()
    if con is None:
        error = "Canonical Workbench graph is not available. Build/import workbench.db before tracing features."
    elif q.strip():
        query = q.strip()
        query_diagnostics = feature_trace.entity_query_diagnostics(con, catalog_con, query)
        implementation_path = feature_trace.entity_implementation_path(con, catalog_con, query)
        _feature_trace_branch_source_drilldown(implementation_path)
        exact = feature_trace.node_info(con, query, catalog_con)
        if exact["known"]:
            result = feature_trace.trace(con, query, depth, direction, catalog_con)
        elif implementation_path and implementation_path.get("canonical_root"):
            result = feature_trace.trace(
                con, implementation_path["canonical_root"], depth, direction, catalog_con
            )
        else:
            matches = feature_trace.search_nodes(con, query, catalog_con)
            if len(matches) == 1:
                result = feature_trace.trace(con, matches[0]["node_id"], depth, direction, catalog_con)
            elif implementation_path:
                # Exact entity IDs often have multiple source representations by design.
                # Keep those in the Implementation Path instead of presenting them as unresolved ambiguity.
                entity_nodes = {
                    branch["root"]["node_id"] for branch in implementation_path.get("branches", [])
                }
                matches = [row for row in matches if row.get("node_id") not in entity_nodes]
        if implementation_path and result:
            implementation_path["trace_summary"] = {
                "root": result.get("root"),
                "semantic_node_count": len(result.get("nodes") or []),
                "semantic_relationship_count": len(result.get("edges") or []),
                "runtime_observation_count": result.get("runtime_observation_count", 0),
                "runtime_capture_count": result.get("runtime_capture_count", 0),
                "runtime_group_count": result.get("runtime_group_count", 0),
                "truncated": bool(result.get("truncated")),
            }
            runtime_capture_ids=sorted({
                int(capture.get("capture_id"))
                for group in (result.get("runtime_hierarchy") or {}).get("groups", [])
                for capture in group.get("capture_groups", [])
                if str(capture.get("capture_id") or "").isdigit()
            })
            existing_hrefs={row.get("href") for row in implementation_path.get("handoffs") or []}
            for capture_id in runtime_capture_ids:
                href=f"/captures/{capture_id}"
                if href not in existing_hrefs:
                    implementation_path.setdefault("handoffs",[]).append({
                        "kind":"RUNTIME_CAPTURE",
                        "label":f"Runtime Capture #{capture_id}",
                        "href":href,
                        "basis":"Capture contributes a runtime observation in the current bounded trace.",
                    })
            implementation_path["runtime_capture_ids"]=runtime_capture_ids
            if not result.get("runtime_observation_count"):
                implementation_path.setdefault("coverage_cues",[]).append({
                    "code":"NO_RUNTIME_OBSERVATIONS_IN_TRACE",
                    "level":"COVERAGE",
                    "label":"No runtime observations are present in this trace window",
                    "detail":f"No runtime edge was returned within depth {result.get('max_depth')}.",
                    "basis":"Bounded Feature Trace result only; this is not proof the entity was never observed.",
                })
        con.close()
    elif con is not None:
        con.close()
    catalog_con.close()
    relationship_sections = present_relationships(result["edges"]) if result else []
    dossier = build_dossier(result) if result else None
    return templates.TemplateResponse(request, "feature_trace.html", {
        "request": request,
        "q": q,
        "depth": depth,
        "direction": direction,
        "result": result,
        "matches": matches,
        "error": error,
        "relationship_sections": relationship_sections,
        "dossier": dossier,
        "implementation_path": implementation_path,
        "query_diagnostics": query_diagnostics,
    })


@app.get("/features/trace/binding.json")
def feature_trace_binding_detail(server: str = "", method: str = ""):
    """Read-only binding registration/implementation lookup for Feature Trace drill-down."""
    method=method.strip()
    if not method:
        return JSONResponse({"error":"method is required"},status_code=400)
    roots=_behavior_roots()
    if server not in roots:
        return JSONResponse({
            "error":"server must name a configured behavior tree",
            "configured_servers":list(roots),
        },status_code=404)
    root=Path(roots[server])
    return JSONResponse({
        "server":server,
        "method":method,
        "binding":feature_trace_binding_lookup(server,root,method),
    })


@app.get("/features/trace/path.json")
def feature_trace_path_detail(q: str = ""):
    """Return bounded entity resolution/Implementation Path diagnostics for troubleshooting."""
    query=q.strip()
    if not query:
        return JSONResponse({"error":"q is required"},status_code=400)
    con=_workbench_graph_connection()
    catalog_con=get_con()
    if con is None:
        catalog_con.close()
        return JSONResponse({"error":"Canonical Workbench graph is not available."},status_code=404)
    try:
        diagnostics=feature_trace.entity_query_diagnostics(con,catalog_con,query)
        path=feature_trace.entity_implementation_path(con,catalog_con,query)
        _feature_trace_branch_source_drilldown(path)
        return JSONResponse({
            "query":query,
            "diagnostics":diagnostics,
            "implementation_path":path,
        })
    finally:
        con.close()
        catalog_con.close()


@app.get("/features/trace/runtime.json")
def feature_trace_runtime_detail(
    root: str,
    depth: int = 3,
    direction: str = "both",
    opcode: str | None = None,
    capture_id: str | None = None,
    offset: int = 0,
    limit: int = 100,
):
    """Bounded final-level runtime observation drill-down for Feature Trace."""
    depth=max(0,min(depth,8))
    direction=direction if direction in {"out","in","both"} else "both"
    con=_workbench_graph_connection()
    catalog_con=get_con()
    if con is None:
        catalog_con.close()
        return JSONResponse({"error":"Canonical Workbench graph is not available."},status_code=404)
    try:
        page=feature_trace.runtime_observation_page(con,root,depth,direction,catalog_con,opcode,capture_id,offset,limit)
        for observation in page.get("observations", []):
            for locator in observation.get("capture_provenance", []):
                locator["href"] = None
                if locator.get("normalized_table") == "capture_raw_packets":
                    try:
                        key = json.loads(str(locator.get("normalized_row_key") or "{}"))
                        seq = int(key["seq"])
                        locator["href"] = f"/captures/{locator['capture_id']}/packets/{seq}"
                    except (ValueError, TypeError, KeyError, json.JSONDecodeError):
                        pass
                if not locator["href"]:
                    locator["href"] = (
                        f"/captures/{locator['capture_id']}/source-locator"
                        f"?filename={quote(str(locator['filename']), safe='')}"
                        f"&target_table={quote(str(locator['normalized_table']), safe='')}"
                        f"&row_key={quote(str(locator['normalized_row_key']), safe='')}"
                    )
        return JSONResponse(page)
    finally:
        con.close()
        catalog_con.close()


@app.get("/features/trace/closure.json")
def feature_trace_closure(root: str = ""):
    """Return a generic obtainability/access closure projection for Feature Trace.

    Runtime reference bundles are loaded into the same canonical graph tables as imported
    data.  The closure service itself only reads canonical graph relationships; it has no
    scenario-specific rules.
    """
    con = _workbench_graph_connection()
    if con is None:
        return JSONResponse({"error": "Canonical Workbench graph is not available."}, status_code=404)
    try:
        return JSONResponse(build_feature_trace_closure(con, root))
    except Exception as exc:
        return JSONResponse({"error": f"{type(exc).__name__}: {exc}"}, status_code=400)
    finally:
        con.close()


@app.get("/features/check", response_class=HTMLResponse)
def feature_check_page(request: Request, q: str = ""):
    result = None
    matches = []
    error = None
    con = _workbench_graph_connection()
    if con is None:
        error = "Canonical Workbench graph is not available. Build/import workbench.db before checking features."
    elif q.strip():
        query = q.strip()
        feature = feature_checker.resolve_feature(con, query)
        if feature is not None:
            result = feature_checker.check_feature(con, feature)
        else:
            rows = con.execute(
                "SELECT feature_id, name, feature_type, status FROM features "
                "WHERE feature_id LIKE ? OR name LIKE ? ORDER BY feature_id LIMIT 100",
                (f"%{query}%", f"%{query}%"),
            ).fetchall()
            matches = [dict(row) for row in rows]
        con.close()
    elif con is not None:
        con.close()
    return templates.TemplateResponse(request, "feature_checker.html", {
        "request": request,
        "q": q,
        "result": result,
        "matches": matches,
        "error": error,
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
def keyitems(request: Request, q: str = "", page: int = 1, readiness: str = "all"):
    if readiness not in {"all", "clean", "drifted", "wrong_name", "missing"}:
        readiness = "all"
    con = get_con()
    rows = []
    total = 0
    total_pages = 1
    if q:
        page = max(1, page)
        offset = (page - 1) * KEYITEMS_PAGE_SIZE
        if readiness != "all":
            # Exact full-catalog filtering is applied before pagination.
            # Preserve cross-lineage identity guards from the normal page path.
            candidates = con.execute(
                "SELECT keyitem_id, name, plural, description FROM key_items WHERE name LIKE ? ORDER BY name",
                (f"%{q}%",),
            ).fetchall()
            candidates = [row for row in candidates if ingest_global_tables.resolve_keyitem_readiness(
                con, row["keyitem_id"], row["name"])["status"] == readiness]
            total = len(candidates)
            total_pages = max(1, (total + KEYITEMS_PAGE_SIZE - 1) // KEYITEMS_PAGE_SIZE)
            page = min(page, total_pages)
            offset = (page - 1) * KEYITEMS_PAGE_SIZE
            ki_rows = candidates[offset:offset + KEYITEMS_PAGE_SIZE]
        else:
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
            item_readiness = ingest_global_tables.resolve_keyitem_readiness(con, r["keyitem_id"], r["name"])
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
                   WHERE LOWER(keyitem_name) = LOWER(?)""" + _rq_exclude(con) + " ORDER BY capture_id",
                (r["name"],),
            ).fetchall()
            rows.append({
                "keyitem_id": r["keyitem_id"], "name": r["name"], "plural": r["plural"],
                "description": r["description"], "readiness": item_readiness,
                "topaz_readiness": topaz_readiness,
                "capture_events": capture_events,
            })
    con.close()
    return templates.TemplateResponse(request, "keyitems.html", {
        "q": q, "rows": rows, "page": page, "total": total, "total_pages": total_pages,
        "readiness_filter": readiness,
    })


@app.get("/keyitems/lua-references.json")
def keyitems_lua_references(keyitem_id: int, lineage: str = "lsb"):
    """Read-only source citations for a selected client catalog key item."""
    from fastapi import HTTPException
    from workbench.devtools.features.key_item_references import discover_key_item_references

    if lineage not in {"lsb", "topaz"}:
        raise HTTPException(status_code=400, detail="This index currently supports only LSB and Topaz reference identities")
    con = get_con()
    try:
        item = con.execute("SELECT name FROM key_items WHERE keyitem_id = ? LIMIT 2",
                           (keyitem_id,)).fetchall()
        if len(item) != 1:
            raise HTTPException(status_code=404, detail="Key item ID not uniquely present in client catalog")
        table = "keyitems_ours" if lineage == "lsb" else "topaz_keyitems"
        ready = ingest_global_tables.resolve_keyitem_readiness(
            con, keyitem_id, item[0]["name"], table=table)
    finally:
        con.close()

    status = ready.get("status")
    match = ready.get("id_match") if status == "clean" else (
        ready.get("name_match") if status == "drifted" else None
    )
    symbol = match[1] if isinstance(match, (list, tuple)) else match
    if status not in {"clean", "drifted"} or not symbol:
        return {"keyitem_id": keyitem_id, "lineage": lineage, "readiness": status,
                "references": [], "scanned_files": 0, "matched_scripts": 0,
                "truncated": False,
                "message": "A verified enum identity is unavailable for this server lineage."}

    from workbench.devtools.indexing import build_lsb_index
    root = {"lsb": build_lsb_index.LSB_ROOT,
            "topaz": settings_mod.get_topaz_root()}[lineage]
    if not root:
        return {"keyitem_id": keyitem_id, "lineage": lineage, "readiness": status,
                "symbol": symbol, "references": [], "scanned_files": 0,
                "matched_scripts": 0, "truncated": False,
                "message": "No server source checkout configured for this lineage."}
    result = discover_key_item_references(root, str(symbol), lineage=lineage,
                                          max_matches=200, max_files=25000)
    result.update({"keyitem_id": keyitem_id, "readiness": status})
    return result


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
    "capture_npc_entries": {
        "label": "Entity snapshots", "group": "Entities & Spatial",
        "description": "Observed NPC/mob entity state, identity, model/look, position and runtime flags.",
        "id_col": "entity_id", "name_col": "name",
        "display_cols": ("capture_id", "zone_db", "entity_id", "name", "model_id", "x", "y", "z", "dir", "hpp"),
    },
    "capture_npc_history": {
        "label": "Entity history", "group": "Entities & Spatial",
        "description": "Runtime entity state/history deltas captured over time.",
        "id_col": "entity_id", "name_col": None,
        "display_cols": ("capture_id", "zone_db", "entity_id", "seq", "ts"),
    },
    "capture_npc_path": {
        "label": "NPC / mob paths", "group": "Entities & Spatial",
        "description": "Observed NPC/mob position tracks and path points.",
        "id_col": "entity_id", "name_col": None,
        "display_cols": ("capture_id", "zone_db", "entity_id", "step", "ts", "x", "y", "z"),
    },
    "capture_pc_path": {
        "label": "Player paths", "group": "Entities & Spatial",
        "description": "Capturing player's observed movement path.",
        "id_col": None, "name_col": None,
        "display_cols": ("capture_id", "zone_db", "step", "ts", "x", "y", "z"),
    },
    "capture_actions": {
        "label": "Battle actions", "group": "Battle & Actions",
        "description": "Canonical action observations including actor, target, action name/category and effects.",
        "id_col": "actor", "name_col": "name",
        "display_cols": ("capture_id", "zone_db", "ts", "actor", "name", "target", "category", "animation", "message"),
    },
    "capture_hp_events": {
        "label": "HP events", "group": "Battle & Actions",
        "description": "Observed HP changes and mob HP state transitions.",
        "id_col": None, "name_col": "mob_name",
        "display_cols": ("capture_id", "zone_db", "ts", "mob_name", "hpp", "delta"),
    },
    "capture_attack_delay": {
        "label": "Attack delay", "group": "Battle & Actions",
        "description": "Attack-delay timing observations from supported capture tools.",
        "id_col": None, "name_col": "mob_name",
        "display_cols": ("capture_id", "zone_db", "ts", "mob_name", "delay"),
    },
    "capture_level_range": {
        "label": "Level range", "group": "Battle & Actions",
        "description": "Observed entity level/range evidence.",
        "id_col": "entity_id", "name_col": "name",
        "display_cols": ("capture_id", "zone_db", "ts", "entity_id", "name", "level", "range"),
    },
    "capture_events": {
        "label": "Events / CSIDs", "group": "Events & Dialogue",
        "description": "Canonical event observations with entity, CSID, option, message and event packet identity.",
        "id_col": "entity_id", "name_col": "entity_name",
        "display_cols": ("capture_id", "zone_db", "seq", "ts", "direction", "opcode", "entity_id", "entity_name", "event_hex", "option", "message_id"),
    },
    "capture_eventview": {
        "label": "EventView observations", "group": "Events & Dialogue",
        "description": "EventView-derived event observations retained separately from canonical event rows.",
        "id_col": "entity_id", "name_col": None,
        "display_cols": ("capture_id", "zone_db", "ts", "entity_id", "event_id", "params", "option", "message"),
    },
    "capture_caplog_chat": {
        "label": "Chat / text", "group": "Events & Dialogue",
        "description": "Canonical chat/text observations from CapLog, PacketDB CHATLOG and supported text sources.",
        "id_col": None, "name_col": "text",
        "display_cols": ("capture_id", "zone_db", "ts", "direction", "text"),
    },
    "capture_chat_observations": {
        "label": "Canonical chat observations", "group": "Events & Dialogue",
        "description": "Normalized chat/text observations with source format/native identity and zone context.",
        "id_col": None, "name_col": "text",
        "display_cols": ("capture_id", "seq", "ts", "direction", "zone_db", "text", "source_format"),
    },
    "capture_ki_events": {
        "label": "Key item events", "group": "Items & Progression",
        "description": "Observed key-item grants/removals and progression evidence.",
        "id_col": "keyitem_id", "name_col": "keyitem_name",
        "display_cols": ("capture_id", "zone_db", "ts", "keyitem_id", "keyitem_name", "action"),
    },
    "capture_structured_records": {
        "label": "Structured observations", "group": "Items & Progression",
        "description": "Canonical auxiliary observations such as vendor stock, pricing, crafting, weather, conquest, POI, spawn and mission records.",
        "id_col": "item_id", "name_col": "item_name",
        "display_cols": ("capture_id", "family", "record_type", "ts", "zone", "entity_id", "entity_name", "item_id", "item_name", "price", "source_file"),
    },
    "capture_raw_packets": {
        "label": "Raw packets", "group": "Protocol & Raw Evidence",
        "description": "Canonical raw packet bytes with source provenance. Use Packet Viewer for field/byte drill-down.",
        "id_col": None, "name_col": "opcode",
        "display_cols": ("capture_id", "seq", "ts", "direction", "opcode", "packet_size", "source_format", "source_file"),
    },
    "capture_network_flows": {
        "label": "Network flows", "group": "Protocol & Raw Evidence",
        "description": "PCAP/PCAPNG TCP/transport flow summaries and endpoint evidence.",
        "id_col": None, "name_col": "transport",
        "display_cols": ("capture_id", "source_file", "flow_id", "transport", "endpoint_a_ip", "endpoint_a_port", "endpoint_b_ip", "endpoint_b_port", "frame_count", "payload_frame_count"),
    },
    "capture_network_ranges": {
        "label": "Network byte ranges", "group": "Protocol & Raw Evidence",
        "description": "Canonical contiguous stream ranges with sequence boundaries and anomaly metadata.",
        "id_col": None, "name_col": "direction",
        "display_cols": ("capture_id", "source_file", "flow_id", "direction", "range_index", "seq_start", "seq_end", "first_ts", "last_ts"),
    },
    "capture_network_messages": {
        "label": "Network messages", "group": "Protocol & Raw Evidence",
        "description": "Framed/decoded network messages from validated transport classifiers.",
        "id_col": "command", "name_col": "command_name",
        "display_cols": ("capture_id", "source_file", "flow_id", "protocol_family", "direction", "command", "command_name", "validation_status"),
    },
    "capture_video_observations": {
        "label": "Video / OCR observations", "group": "Protocol & Raw Evidence",
        "description": "Timestamped packet/event observations recovered from video and screenshot OCR evidence.",
        "id_col": None, "name_col": "raw_text",
        "display_cols": ("capture_id", "video_ts", "observation_type", "direction", "opcode", "gp_command", "packet_class", "ocr_confidence"),
    },
    "capture_source_files": {
        "label": "Source files", "group": "Provenance & Integrity",
        "description": "Every source file ingestion attempt, detected format, row count and parser error.",
        "id_col": None, "name_col": "filename",
        "display_cols": ("capture_id", "filename", "format_detected", "row_count", "error", "ingested_at"),
    },
    "capture_source_manifest": {
        "label": "Source manifest", "group": "Provenance & Integrity",
        "description": "Source-level provenance manifest retained for capture audit.",
        "id_col": None, "name_col": "filename",
        "display_cols": ("capture_id", "filename", "sha256", "size_bytes"),
    },
    "capture_source_artifacts": {
        "label": "Source artifacts", "group": "Provenance & Integrity",
        "description": "Materialized or linked source artifacts associated with capture evidence.",
        "id_col": None, "name_col": "filename",
        "display_cols": ("capture_id", "filename", "artifact_type", "sha256"),
    },
    "capture_content_manifest": {
        "label": "Content manifest", "group": "Provenance & Integrity",
        "description": "Content hashes and canonical manifest evidence used for integrity/provenance.",
        "id_col": None, "name_col": "sha256",
        "display_cols": ("capture_id", "sha256", "content_type", "source_file"),
    },
    "capture_tags": {
        "label": "Capture tags", "group": "Capture Metadata",
        "description": "Normalized capture taxonomy tags.",
        "id_col": None, "name_col": "tag",
        "display_cols": ("capture_id", "tag"),
    },
}
CAPTURE_QUERY_PAGE_SIZE = 100



def capture_query_columns(con, table: str) -> list[str]:
    return [r[1] for r in con.execute(f"PRAGMA table_info({table})").fetchall()]


def capture_query_display_columns(cols: list[str], spec: dict) -> list[str]:
    """Curated first-glance columns; full physical rows remain available in row drill-down."""
    preferred = [name for name in spec.get("display_cols", ()) if name in cols]
    if preferred:
        return preferred
    return cols[:10]


def capture_query_groups() -> list[dict]:
    groups: dict[str, list[dict]] = {}
    for table, spec in CAPTURE_QUERY_TABLES.items():
        groups.setdefault(spec["group"], []).append({
            "table": table,
            "label": spec["label"],
            "description": spec["description"],
        })
    return [
        {"label": group, "datasets": datasets}
        for group, datasets in groups.items()
    ]


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
    display_cols = capture_query_display_columns(cols, spec)
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
        "table": table,
        "dataset": {"table": table, **spec},
        "dataset_groups": capture_query_groups(),
        "capture_id": capture_id, "q": q,
        "cols": cols, "display_cols": display_cols,
        "rows": rows, "page": page, "total": total, "total_pages": total_pages,
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
        health = explore_event.scan_event_health(events_yml.parent, zoneid) if events_yml.exists() else {
            "rows": {}, "summary": {"ok": 0, "stub": 0, "invalid": 0, "failed": 0}
        }
        server_refs_by_csid = {}
        if con.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='npc_event_refs'"
        ).fetchone():
            for row in con.execute(
                "SELECT source,npc_script,csid FROM npc_event_refs WHERE zone_name=?",
                (zone,),
            ).fetchall():
                server_refs_by_csid.setdefault(int(row["csid"]), []).append(dict(row))
        runtime_counts = {}
        if zoneid is not None:
            for row in con.execute(
                """SELECT entity_id,event_hex,COUNT(*) AS n
                   FROM capture_events
                   WHERE replace(lower(zone_db),' ','_')=replace(lower(?),' ','_')"""
                + _rq_exclude(con) + """
                   GROUP BY entity_id,event_hex""",
                (zone,),
            ).fetchall():
                try:
                    runtime_counts[(int(row["entity_id"]), int(str(row["event_hex"]), 0))] = int(row["n"])
                except (TypeError, ValueError):
                    continue
        for b in blocks:
            entity_id = b["entity_id"]
            name_row = None
            if zoneid is not None:
                name_row = con.execute(
                    "SELECT name FROM npc_names WHERE zoneid = ? AND npcid = ?", (zoneid, entity_id)
                ).fetchone()
            name = name_row[0] if name_row else None
            q_stripped = q.strip() if q else ""
            entity_match = bool(q_stripped) and (
                q_stripped.lower() in str(entity_id).lower() or (name and q_stripped.lower() in name.lower())
            )
            # A bare/negative digit string is treated as a candidate csid too, matched exactly (not
            # substring) -- a substring match on entity_id alone let unrelated entities with the
            # csid embedded in their id (e.g. entity 16982289 for csid 289) shadow the real hit.
            q_csid = int(q_stripped) if q_stripped.lstrip("-").isdigit() else None
            for eid in b["event_ids"]:
                if eid == 65535:  # LSB/Topaz sentinel for "no event", not a real CSID
                    continue
                if q_stripped and not entity_match and eid != q_csid:
                    continue
                actor_norm = re.sub(r"[^a-z0-9]+", "", (name or "").lower())
                actor_server_refs = [
                    ref for ref in server_refs_by_csid.get(int(eid), [])
                    if actor_norm
                    and re.sub(r"[^a-z0-9]+", "", str(ref["npc_script"]).lower()) == actor_norm
                ]
                health_row = health.get("rows", {}).get(f"{int(entity_id)}:{int(eid)}", {
                    "status": "unknown", "detail": "No decompile health result is available."
                })
                rows.append({
                    "entity_id": entity_id, "name": name, "csid": eid,
                    "server_ref_count": len(actor_server_refs),
                    "zone_csid_server_ref_count": len(server_refs_by_csid.get(int(eid), [])),
                    "runtime_count": runtime_counts.get((int(entity_id), int(eid)), 0),
                    "decompile_status": health_row.get("status", "unknown"),
                    "decompile_detail": health_row.get("detail"),
                    "decompile_line_count": health_row.get("line_count", 0),
                })
    con.close()
    return templates.TemplateResponse(request, "events.html", {
        "zone": zone, "q": q, "zones": zones, "rows": rows, "generated_note": generated_note,
        "health_summary": health.get("summary", {}) if zone else {},
    })


def _event_server_refs(con: sqlite3.Connection, zone: str, entity_name: str | None, csid: int) -> list[dict]:
    """Exact zone+CSID server refs, with actor-name matching presented as evidence quality only."""
    if not con.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='npc_event_refs'"
    ).fetchone():
        return []
    rows = con.execute(
        """SELECT source,zone_name,npc_script,csid
           FROM npc_event_refs
           WHERE zone_name=? AND csid=?
           ORDER BY source,npc_script""",
        (zone, csid),
    ).fetchall()
    wanted = re.sub(r"[^a-z0-9]+", "", (entity_name or "").lower())
    out = []
    for row in rows:
        d = dict(row)
        script_norm = re.sub(r"[^a-z0-9]+", "", str(d["npc_script"]).lower())
        d["actor_match"] = bool(wanted and wanted == script_norm)
        d["path"] = None
        d["excerpt"] = None
        root = None
        source = str(d["source"]).lower()
        if source == "lsb":
            root = build_lsb_index.LSB_ROOT
        elif source == "topaz":
            root = build_lsb_index.TOPAZ_ROOT
        elif source == "dsp":
            root = build_dsp_index.DSP_ROOT
        d["calls"] = []
        if root:
            candidate = Path(root) / "scripts" / "zones" / zone / "npcs" / f"{d['npc_script']}.lua"
            if candidate.is_file():
                d["path"] = candidate.as_posix()
                try:
                    text = candidate.read_text(encoding="utf-8", errors="replace")
                    lines = text.splitlines()
                    event_matches = [
                        match for match in lua_events.EVENT_RE.finditer(text)
                        if int(match.group("id")) == int(csid)
                    ]
                    if event_matches:
                        event_match = event_matches[0]
                        hit_line = text.count("\n", 0, event_match.start()) + 1
                        start = max(0, hit_line - 5)
                        end = min(len(lines), hit_line + 9)
                        d["excerpt"] = "\n".join(
                            f"{idx + 1:04d}: {lines[idx]}" for idx in range(start, end)
                        )
                        d["line"] = hit_line

                        funcs = list(lua_events.FUNC_RE.finditer(text))
                        containing = None
                        fn_index = -1
                        for idx, fn in enumerate(funcs):
                            if fn.start() <= event_match.start():
                                containing = fn
                                fn_index = idx
                            else:
                                break
                        fn_start = containing.start() if containing else max(0, event_match.start() - 1000)
                        fn_end = (
                            funcs[fn_index + 1].start()
                            if containing and fn_index + 1 < len(funcs)
                            else min(len(text), event_match.end() + 2500)
                        )
                        d["function"] = containing.group(1) if containing else None
                        d["calls"] = lua_events.typed_calls(
                            text, fn_start, fn_end, containing
                        )
                except OSError:
                    pass
        out.append(d)
    return out


def _event_capture_rows(con: sqlite3.Connection, zone: str, entity: int, csid: int) -> list[dict]:
    event_hex = f"0x{int(csid):04X}"
    rows = con.execute(
        """SELECT e.capture_id,c.capture_label,e.zone_db,e.seq,e.direction,e.opcode,e.opcode_name,
                  e.entity_id,e.entity_name,e.event_hex,e.option,e.message_id,e.params_raw
           FROM capture_events e
           LEFT JOIN captures c ON c.capture_id=e.capture_id
           WHERE e.entity_id=? AND upper(e.event_hex)=upper(?)
             AND (replace(lower(e.zone_db),' ','_')=replace(lower(?),' ','_')
                  OR e.zone_db='__UNKNOWN__')
           ORDER BY e.capture_id,e.seq
           LIMIT 200""",
        (entity, event_hex, zone),
    ).fetchall()
    return [dict(row) for row in rows]


@app.get("/events/view", response_class=HTMLResponse)
def events_view(request: Request, zone: str, entity: int, csid: int):
    con = get_con()
    zoneid_row = con.execute("SELECT zoneid FROM zones WHERE name = ?", (zone.upper(),)).fetchone()
    zoneid = zoneid_row[0] if zoneid_row else None
    entity_row = (
        con.execute("SELECT name FROM npc_names WHERE zoneid=? AND npcid=?", (zoneid, entity)).fetchone()
        if zoneid is not None else None
    )
    entity_name = entity_row[0] if entity_row else None

    out_dir = explore_event.ensure_export(
        zone, settings_mod.get_ffxi_install() or explore_event.DEFAULT_FFXI_PATH
    )
    result = explore_event_run(out_dir, entity, csid, zoneid)
    checks = []
    summary = {"message_ids": [], "calls": [], "message_count": 0, "call_count": 0, "line_count": 0}
    if zoneid is not None and result["decompiled"]:
        checks = explore_event.cross_check(con, zoneid, result["decompiled"])
        summary = explore_event.summarize_decompile(result["decompiled"])

    server_refs = _event_server_refs(con, zone, entity_name, csid)
    capture_rows = _event_capture_rows(con, zone, entity, csid)
    observed_options = [row["option"] for row in capture_rows if row.get("option") is not None]
    observed_params = [row["params_raw"] for row in capture_rows if row.get("params_raw")]
    scaffold = explore_event.lua_scaffold(csid, observed_options, observed_params)
    flow_summary = explore_event.event_flow_summary(
        result["decompiled"] or "", capture_rows, server_refs
    )

    dialog_rows = []
    for msg_id, our_text, note in checks:
        dialog_rows.append({
            "message_id": msg_id,
            "text": our_text,
            "note": note,
        })

    con.close()
    return templates.TemplateResponse(request, "event_view.html", {
        "zone": zone, "zoneid": zoneid, "entity": entity, "entity_name": entity_name, "csid": csid,
        "decompiled": result["decompiled"], "error": result["error"], "checks": checks,
        "summary": summary, "server_refs": server_refs, "capture_rows": capture_rows,
        "dialog_rows": dialog_rows, "scaffold": scaffold, "flow_summary": flow_summary,
    })


def explore_event_run(out_dir: Path, entity_id: int, csid: int, zoneid: int | None) -> dict:
    # Canonical in-process path. Unicode dialog/event text remains Python str end-to-end; no
    # Windows console/code-page boundary, and browser health scans use this exact same decoder.
    return explore_event.decompile_event(out_dir, entity_id, csid, zoneid)


def _packet_decoder_normalize_text(text: str, opcode: str) -> tuple[str, str | None]:
    """Normalize plain hex or a pasted PacketLogger/PacketViewer hex-grid block."""
    raw = (text or "").strip()
    if not raw:
        return "", None
    if opcode:
        try:
            opcode_norm = f"0x{int(opcode, 0):03X}"
            records = build_capture_index.parse_packetlogger_records(raw, opcode_norm)
        except Exception:
            records = []
        if records:
            if len(records) > 1:
                raise ValueError(
                    f"Pasted input contains {len(records)} packet blocks. Use Bulk decode for multi-packet input."
                )
            return records[0]["raw_hex"], "Parsed multiline PacketLogger / PacketViewer hex grid."
    compact = "".join(raw.split())
    if compact and all(ch in "0123456789abcdefABCDEF" for ch in compact) and len(compact) % 2 == 0:
        return compact, None
    raise ValueError(
        "Input is neither plain hexadecimal bytes nor a recognized PacketLogger/PacketViewer hex-grid block."
    )


def _packet_decoder_upload_rows(
    filename: str,
    data: bytes,
    *,
    fallback_direction: str = "s2c",
    fallback_opcode: str = "",
) -> tuple[list[dict], dict]:
    """Run an uploaded capture/log through the real capture ingestion adapters in a scratch DB."""
    con = sqlite3.connect(":memory:")
    con.row_factory = sqlite3.Row
    build_capture_index.init_db(con)
    capture_id = build_capture_index.create_manual_capture(
        con, "packet-decoder-upload", "PACKET_DECODE", None
    )
    result = {"filename": filename, "format": None, "rows": 0, "error": None}
    tmp_path = None
    src = None
    try:
        suffix = Path(filename).suffix.lower()
        if suffix in {".zip", ".7z"}:
            tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
            tmp.write(data)
            tmp.close()
            tmp_path = Path(tmp.name)
            src = build_capture_index.Source(tmp_path)
            file_results = []
            counts = build_capture_index.ingest_from_source(
                con, capture_id, src, file_results=file_results
            )
            result["format"] = "capture_bundle"
            result["rows"] = int(counts.get("raw_packets", 0))
            failures = [row for row in file_results if row.get("error")]
            if failures and not result["rows"]:
                result["error"] = "; ".join(
                    f"{row.get('filename')}: {row.get('error')}" for row in failures[:5]
                )
        else:
            result.update(build_capture_index.ingest_single_file(con, capture_id, filename, data))

        rows = [
            dict(row)
            for row in con.execute(
                """SELECT seq,ts,direction,opcode,raw_hex,source_file,source_format
                   FROM capture_raw_packets WHERE capture_id=? ORDER BY seq""",
                (capture_id,),
            ).fetchall()
        ]

        if not rows and fallback_opcode:
            text = data.decode("utf-8", "replace")
            opcode_norm = f"0x{int(fallback_opcode, 0):03X}"
            parsed = build_capture_index.parse_packetlogger_records(text, opcode_norm)
            if parsed:
                direction = "incoming" if fallback_direction == "s2c" else "outgoing"
                rows = [
                    {
                        "seq": i,
                        "ts": row["ts"],
                        "direction": direction,
                        "opcode": opcode_norm,
                        "raw_hex": row["raw_hex"],
                        "source_file": filename,
                        "source_format": "packetlogger-upload",
                    }
                    for i, row in enumerate(parsed, 1)
                ]
                result.update({"format": "packetlogger", "rows": len(rows), "error": None})

        return rows, result
    finally:
        if src is not None:
            src.close()
        con.close()
        if tmp_path is not None:
            tmp_path.unlink(missing_ok=True)


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
def packets_decode(
    request: Request,
    direction: str = "s2c",
    opcode: str = "",
    hex_bytes: str = "",
    q: str = "",
    mode: str = "manual",
):
    decoded = None
    decode_error = None
    schema = None
    layout = None
    input_note = None
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
                normalized_hex, input_note = _packet_decoder_normalize_text(hex_bytes, opcode)
                result = packet_decode.decode(direction, opcode_int, normalized_hex)
                layout = packet_decode.analyze_layout(direction, opcode_int, normalized_hex)
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
        "decoded": decoded, "decode_error": decode_error, "schema": schema, "layout": layout,
        "mode": "bulk" if mode == "bulk" else "manual",
        "input_note": input_note,
        "bulk_rows": None, "bulk_log_text": "", "bulk_parse_error": None, "bulk_sources": [],
    })


@app.post("/packets/decode", response_class=HTMLResponse)
async def packets_decode_submit(request: Request):
    """POST form companion for large/multiline ad-hoc packet input."""
    form = await request.form()
    return packets_decode(
        request,
        direction=(form.get("direction") or "s2c"),
        opcode=(form.get("opcode") or "").strip(),
        hex_bytes=form.get("hex_bytes") or "",
        q=(form.get("q") or "").strip(),
        mode="manual",
    )


@app.get("/packets/bulk", response_class=HTMLResponse)
def packets_bulk_form(request: Request):
    """Compatibility entrypoint: bulk decoding now lives in the shared packet workbench."""
    return RedirectResponse(url="/packets/decode?mode=bulk", status_code=303)


@app.post("/packets/bulk", response_class=HTMLResponse)
async def packets_bulk_submit(request: Request):
    """Decode pasted logs or uploaded capture/log files using the canonical capture adapters."""
    form = await request.form()
    direction = form.get("direction", "s2c")
    opcode = (form.get("opcode") or "").strip()
    log_text = form.get("log_text") or ""
    uploads = [u for u in form.getlist("packet_files") if getattr(u, "filename", "")]
    rows = []
    sources = []
    parse_error = None

    for upload in uploads:
        try:
            data = await upload.read()
            file_rows, source = _packet_decoder_upload_rows(
                upload.filename,
                data,
                fallback_direction=direction,
                fallback_opcode=opcode,
            )
            sources.append(source)
            rows.extend(file_rows)
        except Exception as exc:
            sources.append({
                "filename": upload.filename,
                "format": None,
                "rows": 0,
                "error": str(exc),
            })

    if log_text.strip():
        if not opcode:
            parse_error = "Opcode is required for pasted PacketLogger/PacketViewer text."
        else:
            try:
                opcode_norm = f"0x{int(opcode, 0):03X}"
                pairs = build_capture_index.parse_packetlogger_log(log_text, opcode_norm)
                for ts, raw_hex in pairs:
                    rows.append({
                        "ts": ts,
                        "raw_hex": raw_hex,
                        "direction": "incoming" if direction == "s2c" else "outgoing",
                        "opcode": opcode_norm,
                        "source_file": "pasted input",
                        "source_format": "packetlogger-paste",
                    })
                if not pairs and not uploads:
                    parse_error = (
                        "No packet blocks found. Paste a PacketLogger/PacketViewer hex-grid block "
                        "or upload a supported capture/log file."
                    )
            except Exception as exc:
                parse_error = str(exc)

    decoded_rows = []
    for index, row in enumerate(rows, 1):
        pd_direction = "s2c" if row.get("direction") == "incoming" else "c2s"
        opcode_value = row.get("opcode") or opcode
        try:
            opcode_int = int(str(opcode_value), 0)
            result = packet_decode.decode(pd_direction, opcode_int, row["raw_hex"])
            decoded_rows.append({
                **row,
                "seq": row.get("seq") or index,
                "pd_direction": pd_direction,
                "description": result.description,
                "fields": [
                    {"name": f.name, "value": f.display_value, "out_of_range": f.out_of_range}
                    for f in result.fields
                ],
                "decode_error": None,
            })
        except Exception as exc:
            decoded_rows.append({
                **row,
                "seq": row.get("seq") or index,
                "pd_direction": pd_direction,
                "description": None,
                "fields": [],
                "decode_error": str(exc),
            })

    if uploads and not decoded_rows and not parse_error:
        recognized = [s for s in sources if s.get("format")]
        if recognized:
            parse_error = "Uploaded source was recognized, but it contained no canonical raw packet bytes."
        else:
            parse_error = "No supported packet/capture format was recognized in the uploaded file(s)."

    return templates.TemplateResponse(request, "packets_decode.html", {
        "q": "", "direction": direction, "opcode": opcode, "hex_bytes": "",
        "decoded": None, "decode_error": None, "schema": None, "layout": None,
        "mode": "bulk", "input_note": None,
        "bulk_rows": decoded_rows or None,
        "bulk_log_text": log_text,
        "bulk_parse_error": parse_error,
        "bulk_sources": sources,
    })


def _wiki_page_view(con, source: str, title: str) -> dict | None:
    """Structured view of one stored/dumped wiki page for the Browse tab."""
    page = wiki_evidence.find_reference_page(con, source, title)
    if not page:
        return None
    text = page.get("wikitext") if "wikitext" in page else page.get("page_text")
    text = text or ""
    page_title = page.get("title") or title
    page_id = str(page.get("pageid") or page.get("page_id") or page_title)

    blocks = wiki_document.stored_blocks(con, source, page_id)
    persisted_structure = bool(blocks)
    source_format = None
    if not blocks:
        page_id, source_format, blocks = wiki_document.build_blocks(page)
    else:
        row = con.execute(
            "SELECT source_format FROM reference_wiki_documents WHERE source_id=? AND page_id=?",
            (source, page_id),
        ).fetchone()
        source_format = row[0] if row else "structured"

    visible_blocks = [b for b in blocks if not (b.get("metadata") or {}).get("hidden")]
    groups = wiki_document.presentation_groups(visible_blocks)
    for section in groups:
        for item in section.get("content", []):
            candidate=item.get("field_candidate")
            if candidate and candidate.get("source_links"):
                candidate["source_links"]=wiki_document.resolve_reviewed_template_links(
                    con,candidate["source_links"])
                for link in candidate["source_links"]:
                    # Toolkit entity hints are read-only and require exactly one
                    # resolved client/server reference. Do not create graph edges.
                    matches=wiki_evidence.resolve_subject(con,link.get("lookup_title") or "")
                    # Only named source fields with a reliable target domain may
                    # propose a typed identity; conditions are prose, not entities.
                    allowed_domains={
                        "DROPS":{"item","key_item"},
                        "REWARDS":{"item","key_item"},
                        "LOCATION":{"zone"},
                        "NM_IDENTITY":{"entity"},
                    }.get(candidate.get("field_type"))
                    if allowed_domains is None:
                        matches=[]
                        link["entity_resolution"]="NOT_APPLICABLE"
                    else:
                        matches=[m for m in matches if m.get("target_domain") in allowed_domains]
                    identities={(m.get("target_domain"),m.get("target_table"),str(m.get("target_key")))
                                for m in matches if m.get("target_table") and m.get("target_key") is not None}
                    link["entity_candidates"]=[
                        {"domain":m.get("target_domain"),"table":m.get("target_table"),
                         "key":str(m.get("target_key")),"label":m.get("target_label") or "",
                         "method":m.get("mapping_method") or "UNKNOWN"}
                        for m in matches if m.get("target_table") and m.get("target_key") is not None
                    ][:10]
                    link["entity_candidate_count"]=len(identities)
                    link["entity_candidate_lines"]="\n".join(
                        f"{m['label']} ({m['domain']} / {m['table']} / {m['key']}) via {m['method']}"
                        for m in link["entity_candidates"]
                    ) or "No compatible entity candidates"
                    if len(identities)==1:
                        domain,table,key=next(iter(identities))
                        link["entity_resolution"]="UNIQUE_ENTITY_HINT"
                        link["entity_target"]={"domain":domain,"table":table,"key":key,
                                               "trace_query":("entity:"+key if domain=="entity" else key)}
                        # Direct node navigation is allowed only when the
                        # Feature Trace catalog recognizes this exact row.
                        exact_node=f"catalog:{table}:{key}"
                        try:
                            confirmed_node=feature_trace.node_info(con,exact_node,con)
                        except (ValueError,KeyError,sqlite3.Error):
                            confirmed_node=None
                        if confirmed_node and str(confirmed_node.get("node_id"))==exact_node:
                            link["entity_target"]["trace_node"]=exact_node
                    else:
                        link["entity_resolution"]=("AMBIGUOUS" if identities else "UNRESOLVED") if allowed_domains is not None else "NOT_APPLICABLE"
                        link["entity_target"]=None
    topic = wiki_document.page_topic(con, source, page_id)
    degraded = any((b.get("metadata") or {}).get("degraded") for b in visible_blocks)
    return {
        "title": page_title,
        "page_id": page_id,
        "url": page.get("url") or wiki_jobs.page_url(source, page_title),
        "revision": page.get("revid") or page.get("revision_id"),
        "timestamp": page.get("timestamp") or page.get("revision_timestamp"),
        "blocks": visible_blocks,
        "groups": groups,
        "block_count": len(visible_blocks),
        "chars": len(text),
        "hash": page.get("page_hash") or hashlib.sha256(text.encode()).hexdigest(),
        "text": text,
        "is_ja": source == wiki_evidence.SOURCE_WIKIWIKI_JP,
        "source_format": source_format,
        "persisted_structure": persisted_structure,
        "degraded_structure": degraded,
        "topic": topic,
        "topic_suggestions": ([] if topic else wiki_document.suggest_topic_links(con, source_id=source, page_id=page_id)),
    }


@app.get("/wiki", response_class=HTMLResponse)
def wiki_browse(request: Request, title: str = "", source: str = wiki_evidence.SOURCE_BG, error: str = "", tab: str = "browse", q: str = "", review_status: str = "all", review_page: int = 1, review_origin: bool = False, review_result: str = "", recovery_page: int = 1, recovery_result: str = ""):
    report = None
    evidence = None
    comparison = None
    page_view = None
    search_results = []
    con = get_con()
    wiki_evidence.init_db(con)
    wiki_claim_compare.init_db(con)
    wiki_document.init_db(con)
    if q.strip():
        search_results = wiki_document.search_pages(con, q.strip(), limit=60, source_id=source)
    if title:
        if source == "all":
            source = wiki_evidence.SOURCE_BG
        if source == wiki_evidence.SOURCE_BG:
            report = wiki_compile.compile_report(con, title)
        evidence = wiki_evidence.page_evidence(con, source, title)
        comparison = wiki_claim_compare.alignment_report(con, title)
        page_view = _wiki_page_view(con, source, title)

    def _have(sid):
        return con.execute("SELECT 1 FROM reference_wiki_pages WHERE source_id=? LIMIT 1", (sid,)).fetchone() is not None
    available_sources = [
        {"id": wiki_evidence.SOURCE_BG, "label": "BG Wiki", "available": True},
        {"id": wiki_evidence.SOURCE_FFXICLOPEDIA, "label": "FFXIclopedia", "available": _have(wiki_evidence.SOURCE_FFXICLOPEDIA)},
        {"id": wiki_evidence.SOURCE_WIKIWIKI_JP, "label": "FFXI Wiki (Japanese)", "available": _have(wiki_evidence.SOURCE_WIKIWIKI_JP)},
    ]
    review_page = max(1, min(review_page, 10000))
    review_offset = (review_page - 1) * 50
    review_window = (wiki_document.topic_review_queue(
        con, source_id=source, limit=51, offset=review_offset, matching_only=True,
        status=review_status if review_status in ("pending", "dismissed") else "all")
        if tab == "review" and source != "all" else [])
    review_has_more = len(review_window) > 50
    recovery_page = max(1, min(recovery_page, 10000))
    recovery_preview = []
    recovery_total = 0
    recovery_has_more = False
    if tab == "recovery":
        from workbench.devtools.reference.wiki_import_audit import audit, preview_local_recovery
        recovery_offset = (recovery_page - 1) * 12
        recovery_summary = audit(con, sample_limit=12, recovery_offset=recovery_offset)
        recovery_total = recovery_summary.get("recovery_total", 0)
        recovery_has_more = recovery_summary.get("recovery_has_more", False)
        recovery_preview = preview_local_recovery(con, sample_limit=12, recovery_offset=recovery_offset)
    review_queue = review_window[:50]
    if tab == "review" and review_status in ("pending", "dismissed"):
        review_queue = [entry for entry in review_queue if entry[review_status]]
    con.close()
    site_links = [{"label": v["label"], "home": v["home"], "page": wiki_jobs.page_url(k, title) if title else None}
                  for k, v in wiki_jobs.SITES.items()]
    return templates.TemplateResponse(request, "wiki.html", {
        "title": title,
        "q": q,
        "source": source,
        "search_results": search_results,
        "report": report,
        "evidence": evidence,
        "available_sources": available_sources,
        "comparison": comparison,
        "error": error,
        "tab": tab if tab in ("browse", "evidence", "review", "recovery") else "browse",
        "review_queue": review_queue,
        "recovery_preview": recovery_preview,
        "recovery_page": recovery_page,
        "recovery_total": recovery_total,
        "recovery_has_more": recovery_has_more,
        "recovery_result": recovery_result if recovery_result in ("applied", "failed") else "",
        "review_page": review_page,
        "review_origin": review_origin,
        "review_result": review_result if review_result in ("approved", "dismissed") else "",
        "review_has_more": review_has_more,
        "review_status": review_status if review_status in ("all", "pending", "dismissed") else "all",
        "page_view": page_view,
        "site_links": site_links,
        "jobs": wiki_jobs.recent_jobs(),
    })


@app.post("/wiki/recovery/apply")
async def wiki_recovery_apply(request: Request):
    """Guarded single-page offline recovery; source hash is rechecked in transaction."""
    from workbench.devtools.reference.wiki_import_audit import apply_local_recovery
    form = await request.form()
    source = str(form.get("source") or "").strip()
    page_id = str(form.get("page_id") or "").strip()
    expected = str(form.get("source_hash") or "").strip()
    confirmed = str(form.get("confirm") or "") == "yes"
    try:
        page = int(form.get("recovery_page") or 1)
    except (ValueError, TypeError):
        page = 1
    page = max(1, min(page, 10000))
    redirect_base = f"/wiki?tab=recovery&recovery_page={page}"
    if not confirmed or not source or not page_id or len(expected) != 64:
        return RedirectResponse(redirect_base + "&recovery_result=failed", status_code=303)
    con = get_con()
    try:
        apply_local_recovery(con, source=source, page_id=page_id,
                             expected_raw_hash=expected, confirm=True)
    except (ValueError, sqlite3.Error):
        return RedirectResponse(redirect_base + "&recovery_result=failed", status_code=303)
    finally:
        con.close()
    return RedirectResponse(redirect_base + "&recovery_result=applied", status_code=303)


@app.get("/wiki/bulk/jp/jobs")
def wiki_jp_crawl_status():
    from workbench.devtools.reference import wiki_jp_crawl_jobs
    return {"jobs": wiki_jp_crawl_jobs.status(DB_PATH)}


@app.post("/wiki/bulk/jp/start")
async def wiki_jp_crawl_start(request: Request):
    from workbench.devtools.reference import wiki_jp_crawl_jobs
    form = await request.form()
    try:
        return {"job_id": wiki_jp_crawl_jobs.start(DB_PATH, form.get("seed") or "", int(form.get("limit") or 50))}
    except (ValueError, TypeError) as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)


@app.post("/wiki/bulk/jp/pause")
async def wiki_jp_crawl_pause(request: Request):
    from workbench.devtools.reference import wiki_jp_crawl_jobs
    form = await request.form()
    wiki_jp_crawl_jobs.pause(DB_PATH, str(form.get("job_id") or ""))
    return {"status": "pausing"}


@app.post("/wiki/bulk/jp/resume")
async def wiki_jp_crawl_resume(request: Request):
    from workbench.devtools.reference import wiki_jp_crawl_jobs
    form = await request.form()
    try:
        wiki_jp_crawl_jobs.resume(DB_PATH, str(form.get("job_id") or ""))
        return {"status": "queued"}
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)


@app.get("/wiki/bulk/bg/jobs")
def wiki_bg_dump_status():
    from workbench.devtools.reference import wiki_bg_dump_jobs
    return {"jobs": wiki_bg_dump_jobs.status(DB_PATH)}


@app.post("/wiki/bulk/bg/start")
async def wiki_bg_dump_start(request: Request):
    from workbench.devtools.reference import wiki_bg_dump_jobs
    from workbench.devtools.reference.scrape_bg_wiki import DUMP_PATH
    form = await request.form()
    try:
        return {"job_id": wiki_bg_dump_jobs.start(DB_PATH, DUMP_PATH, int(form.get("limit") or 50), auto_continue=str(form.get("auto_continue") or "").lower() in ("1", "true", "on"))}
    except (ValueError, TypeError, OSError) as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)


@app.post("/wiki/bulk/bg/pause")
async def wiki_bg_dump_pause(request: Request):
    from workbench.devtools.reference import wiki_bg_dump_jobs
    form = await request.form()
    wiki_bg_dump_jobs.pause(DB_PATH, str(form.get("job_id") or ""))
    return {"status": "pausing"}


@app.post("/wiki/bulk/bg/resume")
async def wiki_bg_dump_resume(request: Request):
    from workbench.devtools.reference import wiki_bg_dump_jobs
    form = await request.form()
    try:
        wiki_bg_dump_jobs.resume(DB_PATH, str(form.get("job_id") or ""))
        return {"status": "queued"}
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)


@app.get("/wiki/bulk/jobs")
def wiki_bulk_status():
    from workbench.devtools.reference import wiki_bulk_jobs
    return {"jobs": wiki_bulk_jobs.status(DB_PATH)}


@app.post("/wiki/bulk/start")
async def wiki_bulk_start(request: Request):
    from workbench.devtools.reference import wiki_bulk_jobs
    form = await request.form()
    try:
        job_id = wiki_bulk_jobs.start(DB_PATH, int(form.get("limit") or 50))
        return {"job_id": job_id}
    except (ValueError, TypeError) as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)


@app.post("/wiki/bulk/pause")
async def wiki_bulk_pause(request: Request):
    from workbench.devtools.reference import wiki_bulk_jobs
    form = await request.form()
    try:
        wiki_bulk_jobs.pause(DB_PATH, str(form.get("job_id") or ""))
        return {"status": "pausing"}
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)


@app.post("/wiki/bulk/resume")
async def wiki_bulk_resume(request: Request):
    from workbench.devtools.reference import wiki_bulk_jobs
    form = await request.form()
    try:
        wiki_bulk_jobs.resume(DB_PATH, str(form.get("job_id") or ""))
        return {"status": "queued"}
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)


@app.post("/wiki/scrape")
async def wiki_scrape_url(request: Request):
    form = await request.form()
    url = (form.get("url") or "").strip()
    try:
        job = wiki_jobs.start_job(url, DB_PATH)
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    return {"job": job}


@app.get("/wiki/snapshot/export")
def wiki_snapshot_download(source: str = "all"):
    """Generate a portable archive in a private temporary directory."""
    from workbench.devtools.reference import wiki_snapshot
    if source not in (*wiki_snapshot.SOURCES, "all"):
        return JSONResponse({"error": "Invalid Wiki source"}, status_code=400)
    directory = Path(tempfile.mkdtemp(prefix="wiki_snapshot_"))
    destination = directory / f"wiki-{source}.jsonl.gz"
    try:
        wiki_snapshot.export_snapshot(DB_PATH, destination, source)
    except (ValueError, OSError, sqlite3.Error) as exc:
        shutil.rmtree(directory, ignore_errors=True)
        return JSONResponse({"error": str(exc)}, status_code=400)
    from starlette.background import BackgroundTask
    return FileResponse(str(destination), media_type="application/gzip",
                        filename=destination.name,
                        background=BackgroundTask(shutil.rmtree, str(directory), ignore_errors=True))


@app.post("/wiki/snapshot/preview")
async def wiki_snapshot_preview(file: UploadFile = File(...)):
    """Read-only comparison; temporary upload is deleted after validation."""
    from workbench.devtools.reference import wiki_snapshot
    if not (file.filename or "").lower().endswith(".jsonl.gz"):
        return JSONResponse({"error": "Choose a .jsonl.gz Wiki snapshot"}, status_code=400)
    path = None
    try:
        with tempfile.NamedTemporaryFile(prefix="wiki_preview_", suffix=".jsonl.gz", delete=False) as target:
            path = Path(target.name)
            total = 0
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > 64 * 1024 * 1024:
                    raise ValueError("Snapshot upload exceeds 64 MiB limit")
                target.write(chunk)
        return {"preview": wiki_snapshot.preview_snapshot(DB_PATH, path)}
    except (ValueError, OSError, sqlite3.Error, EOFError, KeyError, TypeError, StopIteration) as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    finally:
        await file.close()
        if path:
            path.unlink(missing_ok=True)


@app.post("/wiki/snapshot/import")
async def wiki_snapshot_upload(request: Request, file: UploadFile = File(...)):
    """Validate a small local archive before importing; no arbitrary file paths."""
    from workbench.devtools.reference import wiki_snapshot
    if not (file.filename or "").lower().endswith(".jsonl.gz"):
        return JSONResponse({"error": "Choose a .jsonl.gz Wiki snapshot"}, status_code=400)
    path = None
    try:
        with tempfile.NamedTemporaryFile(prefix="wiki_upload_", suffix=".jsonl.gz", delete=False) as target:
            path = Path(target.name)
            total = 0
            while True:
                part = await file.read(1024 * 1024)
                if not part:
                    break
                total += len(part)
                if total > 64 * 1024 * 1024:
                    raise ValueError("Snapshot upload exceeds 64 MiB limit")
                target.write(part)
        result = wiki_snapshot.import_snapshot(DB_PATH, path)
        return {"result": result}
    except (ValueError, OSError, sqlite3.Error, EOFError, KeyError, TypeError) as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    finally:
        await file.close()
        if path:
            path.unlink(missing_ok=True)


@app.get("/wiki/diagnose")
def wiki_diagnose_title(title: str):
    """Diagnose missing search results against the actual configured database."""
    con = get_con()
    try:
        return wiki_document.diagnose_title(con, title)
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    finally:
        con.close()


@app.get("/wiki/cache-health")
def wiki_cache_health():
    return wiki_jobs.cache_health(DB_PATH)


@app.get("/wiki/jobs")
def wiki_job_status():
    return {"jobs": wiki_jobs.recent_jobs()}


@app.get("/wiki/translate")
def wiki_translate(source: str, title: str):
    """Machine translation of a stored page, display-only; the stored original is untouched."""
    con = get_con()
    try:
        view = _wiki_page_view(con, source, title)
        if not view:
            return JSONResponse({"status": "NOT_FOUND"}, status_code=404)
        return wiki_jobs.translate_cached(con, source, view["page_id"], view["hash"], view["text"])
    finally:
        con.close()


@app.post("/wiki/topic", response_class=HTMLResponse)
async def wiki_link_topic(request: Request):
    """Attach the current source page to a canonical multilingual topic."""
    form = await request.form()
    title = (form.get("title") or "").strip()
    source = (form.get("source") or wiki_evidence.SOURCE_BG).strip()
    canonical_title = (form.get("canonical_title") or "").strip()
    error = ""
    con = get_con()
    try:
        page = wiki_evidence.find_reference_page(con, source, title)
        if not page:
            raise ValueError(f"{source}: page not found for {title!r}")
        page_id = str(page.get("pageid") or page.get("page_id") or page.get("title") or title)
        suggested_topic_id = (form.get("suggested_topic_id") or "").strip()
        if suggested_topic_id:
            matches = wiki_document.suggest_topic_links(con, source_id=source, page_id=page_id)
            if not any(item["topic_id"] == suggested_topic_id and item["canonical_title"] == canonical_title
                       for item in matches):
                raise ValueError("Suggested topic no longer matches reviewed aliases; reload and review.")
        wiki_document.link_topic(
            con,
            source_id=source,
            page_id=page_id,
            canonical_title=canonical_title,
            method="MANUAL_REVIEW",
        )
    except ValueError as exc:
        error = str(exc)
    finally:
        con.close()
    review_page_raw = (form.get("review_page") or "").strip()
    review_status = (form.get("review_status") or "all").strip()
    if review_page_raw.isdecimal() and review_status in ("all", "pending", "dismissed") and not error:
        review_page = max(1, min(int(review_page_raw), 10000))
        suffix = f"?source={quote(source)}&tab=review&review_status={review_status}&review_page={review_page}"
    else:
        suffix = f"?title={quote(title)}&source={quote(source)}&tab=browse"
    if error:
        suffix += f"&error={quote(error)}"
    else:
        suffix += "&review_result=approved"
    return RedirectResponse("/wiki" + suffix, status_code=303)


@app.post("/wiki/topic/dismiss", response_class=HTMLResponse)
async def wiki_dismiss_topic(request: Request):
    """Explicitly dismiss one unlinked page's currently proposed topic."""
    form = await request.form()
    title = (form.get("title") or "").strip()
    source = (form.get("source") or wiki_evidence.SOURCE_BG).strip()
    topic_id = (form.get("suggested_topic_id") or "").strip()
    error = ""
    con = get_con()
    try:
        page = wiki_evidence.find_reference_page(con, source, title)
        if not page:
            raise ValueError("Wiki page not found")
        page_id = str(page.get("pageid") or page.get("page_id") or page.get("title") or title)
        wiki_document.dismiss_topic_suggestion(con, source_id=source, page_id=page_id, topic_id=topic_id)
    except ValueError as exc:
        error = str(exc)
    finally:
        con.close()
    review_page_raw = (form.get("review_page") or "").strip()
    review_status = (form.get("review_status") or "all").strip()
    if review_page_raw.isdecimal() and review_status in ("all", "pending", "dismissed") and not error:
        review_page = max(1, min(int(review_page_raw), 10000))
        suffix = f"?source={quote(source)}&tab=review&review_status={review_status}&review_page={review_page}"
    else:
        suffix = f"?title={quote(title)}&source={quote(source)}&tab=browse"
    if error:
        suffix += f"&error={quote(error)}"
    else:
        suffix += "&review_result=dismissed"
    return RedirectResponse("/wiki" + suffix, status_code=303)


@app.post("/wiki/map", response_class=HTMLResponse)
async def wiki_build_evidence_map(request: Request):
    form = await request.form()
    title = (form.get("title") or "").strip()
    source = (form.get("source") or wiki_evidence.SOURCE_BG).strip()
    error = ""
    con = get_con()
    try:
        result = wiki_evidence.ingest_page(con, source, title)
        if result.get("status") != "OK":
            error = f"{source}: page not found for {title!r}"
        else:
            wiki_evidence_graph.import_wiki_evidence(
                DB_PATH, WORKBENCH_DB, source_id=source, page_id=result["page_id"]
            )
    except (ValueError, SystemExit) as exc:
        error = str(exc)
    finally:
        con.close()
    suffix = f"?title={quote(title)}&source={quote(source)}"
    if error:
        suffix += f"&error={quote(error)}"
    return RedirectResponse("/wiki" + suffix, status_code=303)


@app.post("/wiki/compare", response_class=HTMLResponse)
async def wiki_compare_sources(request: Request):
    form = await request.form()
    title = (form.get("title") or "").strip()
    error = ""
    con = get_con()
    try:
        for src in (wiki_evidence.SOURCE_BG, wiki_evidence.SOURCE_FFXICLOPEDIA):
            existing = wiki_evidence.page_evidence(con, src, title)
            if existing.get("status") != "OK" or not existing.get("claims"):
                wiki_evidence.ingest_page(con, src, title)
        result = wiki_claim_compare.align_page(con, title)
        if result.get("status") != "OK":
            error = "No aligned wiki evidence is available for this title."
        else:
            wiki_evidence_graph.import_wiki_alignment(DB_PATH, WORKBENCH_DB, title=title)
    except (ValueError, SystemExit) as exc:
        error = str(exc)
    finally:
        con.close()
    suffix = f"?title={quote(title)}&source={quote(wiki_evidence.SOURCE_BG)}"
    if error:
        suffix += f"&error={quote(error)}"
    return RedirectResponse("/wiki" + suffix, status_code=303)


@app.post("/wiki/mapping/{mapping_id}/review", response_class=HTMLResponse)
async def wiki_review_mapping(request: Request, mapping_id: str):
    form = await request.form()
    title = (form.get("title") or "").strip()
    source = (form.get("source") or wiki_evidence.SOURCE_BG).strip()
    review_status = (form.get("review_status") or "").strip()
    notes = (form.get("notes") or "").strip() or None
    error = ""
    con = get_con()
    try:
        wiki_evidence.review_mapping(con, mapping_id, review_status, notes)
        evidence = wiki_evidence.page_evidence(con, source, title)
        if evidence.get("status") == "OK":
            wiki_evidence_graph.import_wiki_evidence(
                DB_PATH, WORKBENCH_DB, source_id=source, page_id=evidence["page_id"]
            )
    except ValueError as exc:
        error = str(exc)
    finally:
        con.close()
    suffix = f"?title={quote(title)}&source={quote(source)}"
    if error:
        suffix += f"&error={quote(error)}"
    return RedirectResponse("/wiki" + suffix, status_code=303)


@app.get("/wiki/export", response_class=PlainTextResponse)
def wiki_export(title: str = ""):
    con = get_con()
    report = wiki_compile.compile_report(con, title)
    con.close()
    return PlainTextResponse(wiki_compile.to_markdown(report), media_type="text/markdown")


def _sync_ocr_run_to_linked_captures(run_id: str) -> int:
    """Refresh derived VIDEO_OCR rows for every capture linked to this OCR run."""
    con = get_con()
    build_capture_index.init_db(con)
    capture_ids = [
        row[0]
        for row in con.execute(
            "SELECT capture_id FROM captures WHERE ocr_run_id=? ORDER BY capture_id",
            (run_id,),
        ).fetchall()
    ]
    if not capture_ids:
        con.close()
        return 0
    observations = youtube_chat_ocr.capture_observations(run_id)
    for capture_id in capture_ids:
        build_capture_index.replace_video_ocr_observations(
            con, capture_id, run_id, observations
        )
    con.close()
    return len(capture_ids)


def ocr_prereqs() -> list[dict]:
    from shutil import which
    prereqs = [
        {
            "tool": "yt-dlp", "label": "yt-dlp (downloads the video)",
            "installed": which("yt-dlp") is not None,
            "manual_label": "pip install yt-dlp", "manual_url": "https://github.com/yt-dlp/yt-dlp",
        },
        {
            "tool": "ffmpeg", "label": "ffmpeg (crops frames)",
            "installed": youtube_chat_ocr.tool_available("ffmpeg"),
            "manual_label": "gyan.dev Windows builds", "manual_url": "https://www.gyan.dev/ffmpeg/builds/",
        },
        {
            "tool": "tesseract", "label": "tesseract (OCR engine)",
            "installed": youtube_chat_ocr.tool_available("tesseract"),
            "manual_label": "UB-Mannheim Windows installer", "manual_url": "https://github.com/UB-Mannheim/tesseract/wiki",
        },
    ]
    for p in prereqs:
        if not p["installed"]:
            pending = install_external_tools.pending_installer(p["tool"])
            p["pending_path"] = str(pending) if pending else None
        else:
            p["pending_path"] = None
    return prereqs


@app.get("/ocr", response_class=HTMLResponse)
def ocr_index(request: Request, installed: str = "", ok: int = 1, detail: str = ""):
    con = get_con()
    zones = [r[0] for r in con.execute("SELECT name FROM zones ORDER BY name").fetchall()]
    con.close()
    return templates.TemplateResponse(request, "ocr.html", {
        "runs": youtube_chat_ocr.list_runs(),
        "zones": zones,
        "prereqs": ocr_prereqs(),
        "installed": installed, "installed_ok": bool(ok), "installed_detail": detail,
        "vendor_root": str(TOOLS_ROOT / "vendor"),
    })


@app.post("/ocr/start", response_class=HTMLResponse)
def ocr_start(request: Request, url: str = Form(...), cookies_from_browser: str = Form("")):
    try:
        run_id = youtube_chat_ocr.cmd_download(argparse.Namespace(
            url=url, force=False, cookies_from_browser=cookies_from_browser.strip() or None))
    except SystemExit as e:
        con = get_con()
        zones = [r[0] for r in con.execute("SELECT name FROM zones ORDER BY name").fetchall()]
        con.close()
        return templates.TemplateResponse(request, "ocr.html", {
            "runs": youtube_chat_ocr.list_runs(), "zones": zones, "error": str(e),
            "prereqs": ocr_prereqs(),
            "vendor_root": str(TOOLS_ROOT / "vendor"),
        })
    return RedirectResponse(f"/ocr/{run_id}", status_code=303)


@app.post("/ocr/{run_id}/delete", response_class=HTMLResponse)
def ocr_delete(request: Request, run_id: str):
    youtube_chat_ocr.delete_run(run_id)
    return RedirectResponse("/ocr", status_code=303)


@app.post("/ocr/{run_id}/create_capture", response_class=HTMLResponse)
async def ocr_create_capture(request: Request, run_id: str):
    """Create a capture linked to an OCR run and ingest its time-addressable VIDEO_OCR evidence.

    Parsed on-screen packet observations remain distinct from raw/binary packet captures; the user
    can still attach real logger files from the same session afterward for cross-source alignment.
    """
    form = await request.form()
    mission_name = (form.get("mission_name") or "").strip() or None
    content_type = form.get("content_type") or "instances"
    status = youtube_chat_ocr.run_status(run_id)
    meta = status.get("meta") or {}
    label = meta.get("title") or status.get("url") or run_id
    start_time = None
    upload_date = meta.get("upload_date")
    if upload_date:
        try:
            start_time = datetime.strptime(upload_date, "%Y%m%d").timestamp()
        except ValueError:
            start_time = None
    con = get_con()
    build_capture_index.init_db(con)
    capture_id = build_capture_index.create_manual_capture(
        con, label, content_type, mission_name,
        video_url=status.get("url"), ocr_run_id=run_id, start_time=start_time)
    build_capture_index.replace_video_ocr_observations(
        con,
        capture_id,
        run_id,
        youtube_chat_ocr.capture_observations(run_id),
    )
    con.close()
    return RedirectResponse(url=f"/captures/{capture_id}/add", status_code=303)


@app.get("/ocr/{run_id}", response_class=HTMLResponse)
def ocr_run_detail(request: Request, run_id: str, t: float = 5.0, error: str = ""):
    status = youtube_chat_ocr.run_status(run_id)
    if status["has_source"] and not status["has_preview"]:
        try:
            youtube_chat_ocr.extract_preview_frame(run_id, t)
            status = youtube_chat_ocr.run_status(run_id)
        except SystemExit as e:
            error = error or str(e)
    preview_size = youtube_chat_ocr.preview_frame_size(run_id) if status["has_preview"] else None
    con = get_con()
    zones = [r[0] for r in con.execute("SELECT name FROM zones ORDER BY name").fetchall()]
    con.close()
    return templates.TemplateResponse(request, "ocr_run.html", {
        "status": status,
        "zones": zones,
        "preview_size": preview_size,
        "preview_t": t,
        "transcripts": {
            s["section"]: youtube_chat_ocr.read_transcript(run_id, s["section"])
            for s in status["sections"] if s["has_transcript"]
        },
        "matched_rows": {
            s["section"]: youtube_chat_ocr.read_matched_rows(run_id, s["section"])
            for s in status["sections"] if s["has_transcript"]
        },
        "capture_profiles": youtube_chat_ocr.CAPTURE_PROFILES,
        "preprocess_profiles": youtube_chat_ocr.list_preprocess_profiles(),
        "layout_profiles": youtube_chat_ocr.load_layout_profiles(),
        "error": error,
        "ocr_seconds_per_frame": youtube_chat_ocr.ocr_seconds_per_frame(),
    })


@app.post("/ocr/{run_id}/preview", response_class=HTMLResponse)
def ocr_run_preview(run_id: str, t: float = Form(...)):
    (youtube_chat_ocr.run_dir(run_id) / "preview.png").unlink(missing_ok=True)
    return RedirectResponse(f"/ocr/{run_id}?t={t}", status_code=303)


@app.post("/ocr/{run_id}/frames", response_class=HTMLResponse)
def ocr_run_frames(run_id: str, x: int = Form(...), y: int = Form(...), w: int = Form(...),
                    h: int = Form(...), fps: float = Form(2.0),
                    section: str = Form(youtube_chat_ocr.DEFAULT_SECTION_LABEL),
                    profile: str = Form(youtube_chat_ocr.DEFAULT_CAPTURE_PROFILE),
                    preprocess: str = Form(youtube_chat_ocr.DEFAULT_PREPROCESS_PROFILE)):
    # `section` is a free-text label ("chat", "npclogger", ...) -- a run can hold several
    # independently-cropped regions, each with its own frames/dedupe/ocr/match pipeline below.
    # `profile` picks how 'match' parses this section's lines (plain/timestamped/packetlogger).
    error = ""
    try:
        youtube_chat_ocr.cmd_frames(argparse.Namespace(
            run_id=run_id, crop=f"{x},{y},{w},{h}", fps=fps,
            section=section or youtube_chat_ocr.DEFAULT_SECTION_LABEL,
            profile=profile or youtube_chat_ocr.DEFAULT_CAPTURE_PROFILE,
            preprocess=preprocess or youtube_chat_ocr.DEFAULT_PREPROCESS_PROFILE,
        ))
    except SystemExit as e:
        error = str(e)
    return RedirectResponse(f"/ocr/{run_id}" + (f"?error={quote(error)}" if error else ""), status_code=303)


@app.post("/ocr/{run_id}/layout/save", response_class=HTMLResponse)
async def ocr_save_layout(run_id: str, request: Request):
    form = await request.form()
    profile_id = (form.get("profile_id") or "").strip()
    name = (form.get("name") or "").strip()
    description = (form.get("description") or "").strip()
    error = ""
    try:
        youtube_chat_ocr.save_run_layout(run_id, profile_id, name, description)
    except ValueError as exc:
        error = str(exc)
    return RedirectResponse(
        f"/ocr/{run_id}" + (f"?error={quote(error)}" if error else ""),
        status_code=303,
    )


@app.post("/ocr/{run_id}/layout/apply", response_class=HTMLResponse)
async def ocr_apply_layout(run_id: str, request: Request):
    form = await request.form()
    profile_id = (form.get("profile_id") or "").strip()
    error = ""
    try:
        youtube_chat_ocr.apply_layout_profile(run_id, profile_id)
    except (ValueError, SystemExit) as exc:
        error = str(exc)
    return RedirectResponse(
        f"/ocr/{run_id}" + (f"?error={quote(error)}" if error else ""),
        status_code=303,
    )


@app.post("/ocr/layout/{profile_id}/delete", response_class=HTMLResponse)
def ocr_delete_layout(profile_id: str, run_id: str = Form("")):
    youtube_chat_ocr.delete_layout_profile(profile_id)
    return RedirectResponse(f"/ocr/{run_id}" if run_id else "/ocr", status_code=303)


@app.post("/ocr/{run_id}/{section}/dedupe", response_class=HTMLResponse)
def ocr_run_dedupe(run_id: str, section: str, threshold: int = Form(6)):
    error = ""
    try:
        youtube_chat_ocr.cmd_dedupe(argparse.Namespace(run_id=run_id, section=section, threshold=threshold))
    except SystemExit as e:
        error = str(e)
    return RedirectResponse(f"/ocr/{run_id}" + (f"?error={quote(error)}" if error else ""), status_code=303)


@app.post("/ocr/{run_id}/{section}/ocr", response_class=HTMLResponse)
def ocr_run_ocr(run_id: str, section: str):
    # Tesseract over 1000+ frames can run many minutes -- run it off the request thread so the
    # page comes back immediately and can poll /ocr/{run_id}/{section}/progress instead of the
    # browser tab just hanging on the POST with no feedback.
    def _run():
        try:
            youtube_chat_ocr.cmd_ocr(argparse.Namespace(run_id=run_id, section=section))
        except SystemExit as e:
            youtube_chat_ocr._write_ocr_progress(run_id, section, 0, 0, finished=True, error=str(e))
    threading.Thread(target=_run, daemon=True).start()
    return RedirectResponse(f"/ocr/{run_id}?ocr_started={quote(section)}", status_code=303)


@app.get("/ocr/{run_id}/{section}/progress")
def ocr_run_progress(run_id: str, section: str):
    return youtube_chat_ocr.read_ocr_progress(run_id, section)


@app.post("/ocr/{run_id}/{section}/match", response_class=HTMLResponse)
def ocr_run_match(run_id: str, section: str, zone: str = Form(""), min_score: float = Form(0.55)):
    error = ""
    try:
        youtube_chat_ocr.cmd_match(argparse.Namespace(run_id=run_id, section=section, zone=zone or None, min_score=min_score))
        _sync_ocr_run_to_linked_captures(run_id)
    except SystemExit as e:
        error = str(e)
    return RedirectResponse(f"/ocr/{run_id}" + (f"?error={quote(error)}" if error else ""), status_code=303)


@app.post("/ocr/{run_id}/{section}/correct", response_class=HTMLResponse)
def ocr_run_correct(run_id: str, section: str, frame: str = Form(...), text: str = Form("")):
    # empty text means "revert to the OCR result" (cmd_correct's --clear), not "set it to blank" --
    # a blank correction would be indistinguishable from an unset one in the table anyway.
    error = ""
    try:
        youtube_chat_ocr.cmd_correct(argparse.Namespace(
            run_id=run_id, section=section, frame=frame, text=text, clear=not text.strip(),
        ))
        _sync_ocr_run_to_linked_captures(run_id)
    except SystemExit as e:
        error = str(e)
    return RedirectResponse(f"/ocr/{run_id}" + (f"?error={quote(error)}" if error else ""), status_code=303)


@app.post("/ocr/{run_id}/{section}/cleanup", response_class=HTMLResponse)
def ocr_run_cleanup(run_id: str, section: str, frames: str | None = Form(None), unique: str | None = Form(None)):
    # Unchecked HTML checkboxes are simply omitted from the POST body (not sent as "false"), so
    # presence-of-key is what signals intent here, not a bool default.
    error = ""
    try:
        youtube_chat_ocr.cmd_cleanup(argparse.Namespace(
            run_id=run_id, section=section, frames=frames is not None, unique=unique is not None,
        ))
    except SystemExit as e:
        error = str(e)
    return RedirectResponse(f"/ocr/{run_id}" + (f"?error={quote(error)}" if error else ""), status_code=303)


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
    all_tags = build_capture_index.all_tag_choices(con)
    from workbench.captures import review_queue as _rq
    flags = _rq.pending_by_capture(con)
    for d in rows:
        d["review"] = flags.get(d["capture_id"], [])
    con.close()
    return templates.TemplateResponse(request, "captures.html", {
        "rows": rows, "content_type": content_type, "content_types": content_types,
        "tag": tag, "all_tags": all_tags,
        "q": q, "missions": missions,
    })


@app.get("/captures/{capture_id}/spatial.json")
def capture_spatial_json(capture_id: int, zone_db: str = "", q: str = ""):
    con = get_con()
    cap = con.execute("SELECT zones FROM captures WHERE capture_id=?", (capture_id,)).fetchone()
    zones = json.loads(cap["zones"]) if cap and cap["zones"] else []
    zone_db = zone_db or (zones[0] if zones else "")
    entities = capture_spatial.capture_spatial_entities(con, capture_id, zone_db, q) if zone_db else []
    zoneid = zoneid_for_zone_db(con, zone_db) if zone_db else None
    con.close()
    return JSONResponse({
        "capture_id": capture_id,
        "zone_db": zone_db,
        "zoneid": zoneid,
        "entities": entities,
    })


_SHIFT_CACHE: dict = {}


def _msgid_shift(con, capture_id, zone_db, msgid=None):
    """Measured (never assumed) server-id -> DAT-index shift. Order: master range list (all captures,
    piecewise) -> this capture's own measurement -> unverified. -> (shift|None, info).
    None = unverified: show raw id."""
    from workbench.captures import msgid_shift
    zid = zoneid_for_zone_db(con, zone_db) if zone_db else None
    if zid is not None and msgid is not None:
        sh, status = msgid_shift.master_lookup(con, zid, msgid)
        if sh is not None:
            return sh, {"source": "master", "status": status, "shift": sh}
    key = (capture_id, zone_db)
    if key not in _SHIFT_CACHE:
        shift, info = msgid_shift.lookup(con, capture_id, zone_db)
        if info is None:
            try:
                msgid_shift.compute(con, capture_id, zoneid_for_zone_db)
            except Exception:
                pass
            shift, info = msgid_shift.lookup(con, capture_id, zone_db)
        _SHIFT_CACHE[key] = (shift, info)
    sh, info = _SHIFT_CACHE[key]
    if info is not None:
        info = dict(info, source="capture")
    return sh, info


def zoneid_for_zone_db(con, zone_db: str) -> int | None:
    """capture_npc_entries.zone_db is the NPCLogger.db filename stem, spaced ("Ilrusi Atoll");
    zones.name is Topaz's own SCREAMING_SNAKE form ("ILRUSI_ATOLL"). Normalize both to compare."""
    norm = zone_db.upper().replace(" ", "_").replace("'", "").replace("-", "_")
    # NPCLogger names [S] zones "Windurst Waters [S]"; zones.name spells them "..._S"
    norm = re.sub(r"_?\[S\]$", "_S", norm)
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
    if zoneid == 0:
        # Nav-bar entry point has no zone context yet -- land on the first real zone and let the
        # page's own zone dropdown take it from there, same pattern as the current Zone Editor's implicit default.
        first = con.execute("SELECT zoneid FROM zones WHERE zoneid > 0 ORDER BY name LIMIT 1").fetchone()
        con.close()
        if first:
            return RedirectResponse(url=f"/zones/{first[0]}/view3d")
        return HTMLResponse("No zones in database yet.", status_code=404)
    all_zones = con.execute("SELECT zoneid, name FROM zones WHERE zoneid > 0 ORDER BY name").fetchall()
    zone_row = con.execute("SELECT name, geometry_rom_path FROM zones WHERE zoneid=?", (zoneid,)).fetchone()
    zone_name = zone_row[0] if zone_row else f"zone {zoneid}"
    geometry_rom_path = zone_row[1] if zone_row else None
    ffxi_path = settings_mod.get_ffxi_install()
    # Phase 3: live in-browser MZB/MMB parse (gui/static/ffxi-dat, vendored from Vanalytics) gives
    # real textures/water/instancing straight from the DAT bytes -- no offline OBJ bake needed when
    # both the install path and this zone's geometry DAT are known. Falls back to the pre-baked OBJ
    # (build_zone_visual_cache.py) below when either is missing.
    live_parse_available = bool(ffxi_path and geometry_rom_path)

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
        "live_parse_available": live_parse_available,
        "ffxi_path_json": json.dumps(ffxi_path or ""),
        "geometry_rom_path_json": json.dumps(geometry_rom_path or ""),
        "all_zones": [{"zoneid": z[0], "name": z[1]} for z in all_zones],
        "capture_spatial_url_json": json.dumps(
            f"/captures/{capture_id}/spatial.json?zone_db={quote(zone_db)}"
            if capture_id and zone_db else ""
        ),
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
    if not build_zone_visual_cache.visual_mesh_api_available():
        return PlainTextResponse(
            build_zone_visual_cache.visual_mesh_api_error(),
            status_code=409,
        )
    con = get_con()
    ok = build_zone_visual_cache.build_one(con, zoneid, ffxi_path)
    con.close()
    if not ok:
        return PlainTextResponse(
            f"Failed to build visual mesh cache for zoneid {zoneid} -- check server log for the DAT parse error.",
            status_code=500,
        )
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

    zone_row = con.execute("SELECT name, geometry_rom_path FROM zones WHERE zoneid=?", (zoneid,)).fetchone()
    zone_name = zone_row[0] if zone_row else f"zone {zoneid}"
    geometry_rom_path = zone_row[1] if zone_row else None
    ffxi_path = settings_mod.get_ffxi_install()
    # Keep the multi-path viewer on the same live client-DAT path as the single-path viewer.
    # Previously this route omitted these template fields, so zone_view3d.html treated live
    # parsing as unavailable and forced the legacy server-side OBJ cache builder.
    live_parse_available = bool(ffxi_path and geometry_rom_path)

    entities = build_capture_index.get_capture_entity_ids_with_path(con, capture_id, zone_db) if zone_db else []
    spatial_entities = capture_spatial.capture_spatial_entities(con, capture_id, zone_db) if zone_db else []
    spatial_by_id = {e["id"]: e for e in spatial_entities}
    paths = []
    for i, (eid, name) in enumerate(entities[:MULTI_PLOT_LIMIT]):
        pts = get_entity_path_with_y(con, capture_id, eid)
        if pts:
            r, g, b = distinct_color(i, len(entities))
            meta = spatial_by_id.get(int(eid), {})
            paths.append({
                "id": int(eid),
                "name": name or str(eid),
                "color": f"rgb({r},{g},{b})",
                "points": pts,
                "x": meta.get("x"), "y": meta.get("y"), "z": meta.get("z"),
            })
    con.close()

    obj_available = (ZONE_VISUAL_DIR / f"{zoneid}.obj").exists()
    return templates.TemplateResponse(request, "zone_view3d.html", {
        "zoneid": zoneid, "zone_name": zone_name, "capture_id": capture_id, "entity_id": 0,
        "entity_name": None, "paths_json": json.dumps(paths), "legend": paths,
        "obj_available": obj_available, "multi": True, "zone_db": zone_db, "zones": zones,
        "truncated": len(entities) > MULTI_PLOT_LIMIT, "limit": MULTI_PLOT_LIMIT,
        "live_parse_available": live_parse_available,
        "ffxi_path_json": json.dumps(ffxi_path or ""),
        "geometry_rom_path_json": json.dumps(geometry_rom_path or ""),
        "all_zones": [],
        "capture_spatial_url_json": json.dumps(
            f"/captures/{capture_id}/spatial.json?zone_db={zone_db}"
        ),
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
def captures_plot_all(
    request: Request, capture_id: int, zone_db: str = "", pad_yalms: float = 200,
    detail: int = 0, q: str = "", labels: int = 1,
):
    con = get_con()
    cap = con.execute("SELECT * FROM captures WHERE capture_id=?", (capture_id,)).fetchone()
    zones = json.loads(cap["zones"]) if cap and cap["zones"] else []
    zone_db = zone_db or (zones[0] if zones else "")

    entities = build_capture_index.get_capture_entity_ids_with_path(con, capture_id, zone_db) if zone_db else []
    spatial_entities = capture_spatial.capture_spatial_entities(con, capture_id, zone_db, q) if zone_db else []
    zoneid = zoneid_for_zone_db(con, zone_db) if zone_db else None
    variants = topdown_variants(zoneid)
    topdown_available = variants["collision"] or variants["detailed"]
    con.close()

    color_by_id = {
        int(eid): "rgb(%d,%d,%d)" % distinct_color(i, max(len(entities), 1))
        for i, (eid, _name) in enumerate(entities[:MULTI_PLOT_LIMIT])
    }
    legend = [
        {
            "entity_id": e["id"], "name": e["n"], "color": color_by_id.get(e["id"], "#e0c840"),
            "x": e["x"], "y": e["y"], "z": e["z"], "model": e["model"],
            "hpp": e["hpp"], "has_path": e["has_path"],
        }
        for e in spatial_entities
    ]

    return templates.TemplateResponse(request, "path_plot_all.html", {
        "capture_id": capture_id, "cap": cap, "zones": zones, "zone_db": zone_db, "zoneid": zoneid,
        "entities": entities, "legend": legend, "topdown_available": topdown_available,
        "pad_yalms": pad_yalms, "truncated": len(entities) > MULTI_PLOT_LIMIT,
        "limit": MULTI_PLOT_LIMIT, "detail": detail, "variants": variants,
        "q": q, "labels": bool(labels), "spatial_count": len(spatial_entities),
    })


@app.get("/captures/plot_all.png")
def captures_plot_all_png(
    capture_id: int, zone_db: str, pad_yalms: float = 200, detail: int = 0,
    q: str = "", labels: int = 1,
):
    """Every entity in one capture+zone with real path data, plotted together on the zone's real
    top-down mesh silhouette -- same coordinate-aligned approach as the single-entity plot, each
    entity given its own deterministic color (distinct_color) plus a small legend on the HTML page.
    detail=1 uses the denser visual-mesh cache instead of the default collision-mesh one."""
    con = get_con()
    entities = build_capture_index.get_capture_entity_ids_with_path(con, capture_id, zone_db)
    spatial_entities = capture_spatial.capture_spatial_entities(con, capture_id, zone_db, q)
    zoneid = zoneid_for_zone_db(con, zone_db)
    all_paths = []
    for eid, name in entities[:MULTI_PLOT_LIMIT]:
        if q and not any(e["id"] == int(eid) for e in spatial_entities):
            continue
        pts = build_capture_index.get_entity_path(con, capture_id, eid)
        if pts:
            all_paths.append((eid, pts))
    con.close()

    paths = topdown_paths(zoneid, bool(detail))
    if not paths or (not all_paths and not spatial_entities):
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

    # Capture-observed entities that never produced a path are still real spatial evidence.
    # Draw them as gold markers and optionally label every visible entity with name/id/position.
    spatial_px = []
    for e in spatial_entities:
        px, py = to_px(e["x"], e["z"])
        spatial_px.append((px, py, e))
        all_px_points.append((px, py))
        rr = max(3, marker_r)
        draw.ellipse([px - rr, py - rr, px + rr, py + rr], fill=(224, 200, 64, 255))
    if labels:
        for px, py, e in spatial_px:
            label = f'{e["n"]} [{e["id"]}] ({e["x"]:.1f},{e["y"]:.1f},{e["z"]:.1f})'
            draw.text((px + marker_r + 2, py - marker_r - 2), label, fill=(255, 255, 255, 255),
                      stroke_width=2, stroke_fill=(0, 0, 0, 220))

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
    _c = get_con(); _t = build_capture_index.all_tag_choices(_c); _c.close()
    return templates.TemplateResponse(request, "capture_new.html", {"all_tags": _t})


@app.post("/captures/new", response_class=HTMLResponse)
async def captures_new_submit(request: Request):
    form = await request.form()
    label = (form.get("label") or "").strip()
    content_type = form.get("content_type", "instances")
    mission_name = (form.get("mission_name") or "").strip() or None
    tags = form.getlist("tags") + build_capture_index.split_tags(form.get("new_tags", ""))
    if not label:
        return templates.TemplateResponse(request, "capture_new.html",
                                           {"error": "A label is required.", "all_tags": build_capture_index.CAPTURE_TAGS})  # noqa
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
    tags = form.getlist("tags") + build_capture_index.split_tags(form.get("new_tags", ""))
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
    row_counts = {}
    for t in capture_integrity.schema_capture_tables(con):
        row_counts[t] = con.execute(
            f'SELECT COUNT(*) FROM "{t}" WHERE capture_id=?', (capture_id,)
        ).fetchone()[0]
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
    evidence_dir = KEY_EVIDENCE_ROOT / str(int(capture_id))
    if evidence_dir.exists():
        shutil.rmtree(evidence_dir, ignore_errors=True)
    return RedirectResponse(url="/captures", status_code=303)


CAPTURE_SEARCH_PAGE_SIZE = 200

CAPTURE_EVIDENCE_MODULES = {
    "events": {
        "label": "Events & Dialogue",
        "description": "CSIDs, NPC events, options, message IDs and resolved dialogue.",
        "hint": "NPC name, message ID, or event opcode",
    },
    "packets": {
        "label": "Raw Protocol",
        "description": "Canonical raw packets searched by protocol category or opcode.",
        "hint": "Packet category or exact opcode",
    },
    "entities": {
        "label": "Entities",
        "description": "NPC/mob identity, model, position and runtime snapshots across captures.",
        "hint": "Entity name or exact entity ID",
    },
    "battle": {
        "label": "Battle & Actions",
        "description": "ActionView actions, HP observations and attack-delay evidence.",
        "hint": "Actor/mob/action name or exact actor ID",
    },
    "items": {
        "label": "Items & Key Items",
        "description": "Key-item events plus item-bearing structured capture observations.",
        "hint": "Item/key-item name or exact ID",
    },
    "vendors": {
        "label": "Vendors & Shops",
        "description": "ShopStock, GuildStock and price observations across captures.",
        "hint": "Vendor/NPC name, item name, or exact item/entity ID",
    },
    "crafting": {
        "label": "Crafting",
        "description": "CraftTrack synthesis/crafting observations and their material/result payload.",
        "hint": "Item name/ID or text contained in the crafting observation",
    },
    "chat": {
        "label": "Chat & Text",
        "description": "Canonical chat observations and legacy CapLog chat text.",
        "hint": "Text substring",
    },
    "spatial": {
        "label": "Spatial & Movement",
        "description": "Entity/path presence, player traces, POI and spawn observations without expanding every path point.",
        "hint": "Zone, entity name, or exact entity ID",
    },
    "environment": {
        "label": "Environment & World State",
        "description": "Weather and conquest/world-state observations normalized from capture tools.",
        "hint": "Zone, weather/state text, or value",
    },
}


def _capture_generic_search(con, module: str, q: str, page: int) -> tuple[list[dict], int, int, int]:
    """Return a normalized evidence row shape for non-event/protocol modules."""
    q = (q or "").strip()
    page = max(1, page)
    if not q:
        return [], 0, 1, page

    like = f"%{q}%"
    numeric = int(q) if q.lstrip("-").isdigit() else None
    sql = ""
    params: list = []

    if module == "entities":
        where = "e.entity_id = ?" if numeric is not None else "e.name LIKE ?"
        params = [numeric if numeric is not None else like]
        sql = f"""SELECT e.capture_id,c.capture_label,'ENTITY' AS evidence_kind,
                         e.zone_db AS zone,NULL AS ts,e.entity_id AS subject_id,
                         COALESCE(e.name, CAST(e.entity_id AS TEXT)) AS title,
                         'model=' || COALESCE(CAST(e.model_id AS TEXT),'?') ||
                         ' pos=(' || COALESCE(CAST(e.x AS TEXT),'?') || ',' ||
                         COALESCE(CAST(e.y AS TEXT),'?') || ',' ||
                         COALESCE(CAST(e.z AS TEXT),'?') || ') hpp=' ||
                         COALESCE(CAST(e.hpp AS TEXT),'?') AS summary,
                         'capture_npc_entries' AS dataset,
                         CAST(e.entity_id AS TEXT) AS record_id
                  FROM capture_npc_entries e
                  JOIN captures c ON c.capture_id=e.capture_id
                  WHERE {where}"""
    elif module == "battle":
        if numeric is not None:
            action_where = "(a.actor = ? OR a.actor_name LIKE ? OR a.name LIKE ?)"
            action_params = [numeric, like, like]
        else:
            action_where = "(a.actor_name LIKE ? OR a.name LIKE ? OR a.action_type LIKE ?)"
            action_params = [like, like, like]
        sql = f"""SELECT a.capture_id,c.capture_label,'ACTION' AS evidence_kind,
                         NULL AS zone,CAST(a.ts AS TEXT) AS ts,a.actor AS subject_id,
                         COALESCE(a.actor_name,a.name,CAST(a.actor AS TEXT)) AS title,
                         COALESCE(a.action_type,'action') || ' • ' ||
                         COALESCE(a.name,'') || ' • animation=' ||
                         COALESCE(CAST(a.animation AS TEXT),'?') || ' message=' ||
                         COALESCE(CAST(a.message AS TEXT),'?') AS summary,
                         'capture_actions' AS dataset,a.action_key AS record_id
                  FROM capture_actions a JOIN captures c ON c.capture_id=a.capture_id
                  WHERE {action_where}
                  UNION ALL
                  SELECT h.capture_id,c.capture_label,'HP_EVENT',NULL,NULL,NULL,
                         h.mob_name,
                         'HP ' || COALESCE(CAST(h.hp_low AS TEXT),'?') || '–' ||
                         COALESCE(CAST(h.hp_high AS TEXT),'?'),
                         'capture_hp_events',CAST(h.seq AS TEXT)
                  FROM capture_hp_events h JOIN captures c ON c.capture_id=h.capture_id
                  WHERE h.mob_name LIKE ?
                  UNION ALL
                  SELECT d.capture_id,c.capture_label,'ATTACK_DELAY',d.zone_db,NULL,NULL,
                         d.mob_name,
                         'avg=' || COALESCE(CAST(d.delay_avg AS TEXT),'?') ||
                         ' min=' || COALESCE(CAST(d.delay_min AS TEXT),'?') ||
                         ' max=' || COALESCE(CAST(d.delay_max AS TEXT),'?') ||
                         ' hits=' || COALESCE(CAST(d.hit_count AS TEXT),'?'),
                         'capture_attack_delay',d.mob_name
                  FROM capture_attack_delay d JOIN captures c ON c.capture_id=d.capture_id
                  WHERE d.mob_name LIKE ?"""
        params = action_params + [like, like]
    elif module == "items":
        structured_where = "(s.item_id = ? OR s.item_name LIKE ?)" if numeric is not None else "s.item_name LIKE ?"
        structured_params = [numeric, like] if numeric is not None else [like]
        ki_where = "(k.keyitem_id = ? OR k.keyitem_name LIKE ?)" if numeric is not None else "k.keyitem_name LIKE ?"
        ki_params = [numeric, like] if numeric is not None else [like]
        sql = f"""SELECT k.capture_id,c.capture_label,'KEY_ITEM' AS evidence_kind,
                         k.zone_name AS zone,k.ts,k.keyitem_id AS subject_id,
                         COALESCE(k.keyitem_name,CAST(k.keyitem_id AS TEXT)) AS title,
                         COALESCE(k.event_type,'key-item event') AS summary,
                         'capture_ki_events' AS dataset,CAST(k.seq AS TEXT) AS record_id
                  FROM capture_ki_events k JOIN captures c ON c.capture_id=k.capture_id
                  WHERE {ki_where}
                  UNION ALL
                  SELECT s.capture_id,c.capture_label,'ITEM_OBSERVATION',
                         s.zone,s.ts,s.item_id,
                         COALESCE(s.item_name,CAST(s.item_id AS TEXT)),
                         s.family || CASE WHEN s.price IS NOT NULL THEN ' • price=' || s.price ELSE '' END,
                         'capture_structured_records',
                         s.source_file || ':' || s.family || ':' || s.record_key
                  FROM capture_structured_records s JOIN captures c ON c.capture_id=s.capture_id
                  WHERE s.item_id IS NOT NULL AND {structured_where}"""
        params = ki_params + structured_params
    elif module == "vendors":
        families = ("shopstock_buy_db","shopstock_sell_db","guildstock_db","pricelog_simple","pricelog_lua")
        placeholders = ",".join("?" for _ in families)
        search = "(s.item_id = ? OR s.entity_id = ? OR s.item_name LIKE ? OR s.entity_name LIKE ?)" if numeric is not None else "(s.item_name LIKE ? OR s.entity_name LIKE ?)"
        search_params = [numeric,numeric,like,like] if numeric is not None else [like,like]
        sql = f"""SELECT s.capture_id,c.capture_label,'VENDOR' AS evidence_kind,
                         s.zone,s.ts,COALESCE(s.entity_id,s.item_id) AS subject_id,
                         COALESCE(s.entity_name,s.item_name,s.family) AS title,
                         s.family || ' • ' || COALESCE(s.item_name,'item ' || s.item_id,'') ||
                         CASE WHEN s.price IS NOT NULL THEN ' • price=' || s.price ELSE '' END,
                         'capture_structured_records',
                         s.source_file || ':' || s.family || ':' || s.record_key
                  FROM capture_structured_records s JOIN captures c ON c.capture_id=s.capture_id
                  WHERE s.family IN ({placeholders}) AND {search}"""
        params = list(families) + search_params
    elif module == "crafting":
        if numeric is not None:
            where = "(s.item_id = ? OR s.item_name LIKE ? OR s.payload_json LIKE ?)"
            params = [numeric, like, like]
        else:
            where = "(s.item_name LIKE ? OR s.payload_json LIKE ?)"
            params = [like, like]
        sql = f"""SELECT s.capture_id,c.capture_label,'CRAFTING' AS evidence_kind,
                         s.zone,s.ts,s.item_id AS subject_id,
                         COALESCE(s.item_name,'Craft observation') AS title,
                         s.family || ' • ' || COALESCE(s.record_type,'CRAFTTRACK'),
                         'capture_structured_records',
                         s.source_file || ':' || s.family || ':' || s.record_key
                  FROM capture_structured_records s JOIN captures c ON c.capture_id=s.capture_id
                  WHERE s.family='crafttrack_csv' AND {where}"""
    elif module == "chat":
        sql = """SELECT o.capture_id,c.capture_label,'CHAT' AS evidence_kind,
                        o.zone_db AS zone,o.ts,NULL AS subject_id,
                        substr(o.text,1,120) AS title,
                        COALESCE(o.source_format,'chat') AS summary,
                        'capture_chat_observations' AS dataset,CAST(o.seq AS TEXT) AS record_id
                 FROM capture_chat_observations o JOIN captures c ON c.capture_id=o.capture_id
                 WHERE o.text LIKE ?
                 UNION ALL
                 SELECT h.capture_id,c.capture_label,'CAPLOG_CHAT',
                        h.zone_db,h.ts,NULL,substr(h.text,1,120),
                        'caplog_chat','capture_caplog_chat',CAST(h.seq AS TEXT)
                 FROM capture_caplog_chat h JOIN captures c ON c.capture_id=h.capture_id
                 WHERE h.text LIKE ?"""
        params = [like, like]
    elif module == "spatial":
        # Path tables can contain thousands of points per entity. Return one aggregate row
        # per capture/zone/entity path instead of flooding search with every sample.
        if numeric is not None:
            entity_where = "(e.entity_id = ? OR e.name LIKE ?)"
            entity_params = [numeric, like]
            path_where = "p.entity_id = ?"
            path_params = [numeric]
        else:
            entity_where = "(e.name LIKE ? OR e.zone_db LIKE ?)"
            entity_params = [like, like]
            path_where = "p.zone_db LIKE ?"
            path_params = [like]
        sql = f"""SELECT e.capture_id,c.capture_label,'ENTITY_POSITION' AS evidence_kind,
                         e.zone_db AS zone,NULL AS ts,e.entity_id AS subject_id,
                         COALESCE(e.name,CAST(e.entity_id AS TEXT)) AS title,
                         'position=(' || COALESCE(CAST(e.x AS TEXT),'?') || ',' ||
                         COALESCE(CAST(e.y AS TEXT),'?') || ',' ||
                         COALESCE(CAST(e.z AS TEXT),'?') || ') dir=' ||
                         COALESCE(CAST(e.dir AS TEXT),'?') AS summary,
                         'capture_npc_entries' AS dataset,CAST(e.entity_id AS TEXT) AS record_id
                  FROM capture_npc_entries e JOIN captures c ON c.capture_id=e.capture_id
                  WHERE {entity_where}
                  UNION ALL
                  SELECT p.capture_id,c.capture_label,'ENTITY_PATH',p.zone_db,NULL,p.entity_id,
                         COALESCE(MAX(e.name),CAST(p.entity_id AS TEXT)),
                         CAST(COUNT(*) AS TEXT) || ' path points • legs=' ||
                         CAST(COUNT(DISTINCT p.leg) AS TEXT),
                         'capture_npc_path',CAST(p.entity_id AS TEXT)
                  FROM capture_npc_path p
                  JOIN captures c ON c.capture_id=p.capture_id
                  LEFT JOIN capture_npc_entries e
                    ON e.capture_id=p.capture_id AND e.zone_db=p.zone_db AND e.entity_id=p.entity_id
                  WHERE {path_where}
                  GROUP BY p.capture_id,p.zone_db,p.entity_id,c.capture_label
                  UNION ALL
                  SELECT s.capture_id,c.capture_label,
                         CASE WHEN s.family='poitrack_db' THEN 'POI' ELSE 'SPAWN' END,
                         s.zone,s.ts,s.entity_id,
                         COALESCE(s.entity_name,s.record_type,s.family),
                         s.family || ' • ' || substr(s.payload_json,1,180),
                         'capture_structured_records',
                         s.source_file || ':' || s.family || ':' || s.record_key
                  FROM capture_structured_records s JOIN captures c ON c.capture_id=s.capture_id
                  WHERE s.family IN ('poitrack_db','spawntrack_csv')
                    AND (s.zone LIKE ? OR s.entity_name LIKE ? OR s.payload_json LIKE ?)"""
        params = entity_params + path_params + [like, like, like]
    elif module == "environment":
        # Environment observations live in structured capture families. Search the
        # normalized zone fields plus raw payload because weather/conquest generations
        # expose different column names over time.
        sql = """SELECT s.capture_id,c.capture_label,
                        CASE WHEN s.family='weathertrack_db' THEN 'WEATHER' ELSE 'WORLD_STATE' END,
                        s.zone,s.ts,s.entity_id,
                        COALESCE(s.zone,s.record_type,s.family) AS title,
                        s.family || ' • ' || substr(s.payload_json,1,220) AS summary,
                        'capture_structured_records',
                        s.source_file || ':' || s.family || ':' || s.record_key
                 FROM capture_structured_records s JOIN captures c ON c.capture_id=s.capture_id
                 WHERE s.family IN ('weathertrack_db','conquesttrack_csv')
                   AND (s.zone LIKE ? OR s.payload_json LIKE ? OR s.record_type LIKE ?)"""
        params = [like, like, like]
    else:
        return [], 0, 1, page

    count_sql = f"SELECT COUNT(*) FROM ({sql})"
    total = int(con.execute(count_sql, params).fetchone()[0])
    total_pages = max(1, (total + CAPTURE_SEARCH_PAGE_SIZE - 1) // CAPTURE_SEARCH_PAGE_SIZE)
    page = min(page, total_pages)
    offset = (page - 1) * CAPTURE_SEARCH_PAGE_SIZE
    rows = [
        dict(r) for r in con.execute(
            f"SELECT * FROM ({sql}) ORDER BY capture_id, ts LIMIT ? OFFSET ?",
            params + [CAPTURE_SEARCH_PAGE_SIZE, offset],
        ).fetchall()
    ]
    return rows, total, total_pages, page


def _capture_search_row_key(row: dict) -> str | None:
    """Canonical locator key for an Evidence Search result.

    This deliberately returns None for aggregate/search-only rows that do not correspond to one
    physical normalized row (for example aggregated NPC path summaries). Related Evidence must
    never manufacture a row identity merely to make a drill-down link available.
    """
    dataset = row.get("dataset")
    record_id = row.get("record_id")
    if not dataset or record_id is None:
        return None
    try:
        if dataset == "capture_npc_entries":
            if row.get("zone") is None or row.get("subject_id") is None:
                return None
            key = {"zone_db": row["zone"], "entity_id": int(row["subject_id"])}
        elif dataset == "capture_actions":
            key = {"action_key": str(record_id)}
        elif dataset in {"capture_hp_events", "capture_ki_events",
                         "capture_chat_observations", "capture_caplog_chat",
                         "capture_raw_packets"}:
            key = {"seq": int(record_id)}
        elif dataset == "capture_attack_delay":
            if row.get("zone") is None:
                return None
            key = {"zone_db": row["zone"], "mob_name": str(record_id)}
        elif dataset == "capture_structured_records":
            source_file, family, source_key = str(record_id).rsplit(":", 2)
            key = {"source_file": source_file, "family": family, "record_key": source_key}
        else:
            return None
    except (TypeError, ValueError):
        return None
    return capture_integrity.canonical_row_key(key)


def _capture_related_locators(
    con: sqlite3.Connection, capture_id: int, target_table: str, row_key: str
) -> tuple[list[dict], list[dict]]:
    """Return exact source locators plus normalized rows sharing the same physical evidence.

    Correlation is intentionally strict. A relation is emitted only when two normalized records
    point at the same hashed source artifact and their byte/line spans overlap, or both identify
    the same SQLite source table+rowid. Timestamps, entity IDs, item IDs, names, and nearby packet
    sequence numbers are NOT correlation keys here.
    """
    anchors = capture_integrity.find_row_locators(con, capture_id, target_table, row_key)
    related: list[dict] = []
    seen: set[tuple[str, str, str]] = set()
    old_factory = con.row_factory
    con.row_factory = sqlite3.Row
    try:
        for anchor in anchors:
            source_sha = anchor.get("source_sha256")
            if not source_sha:
                continue
            candidates = con.execute(
                """SELECT capture_id,filename,target_table,row_key,source_sha256,locator_basis,
                          start_line,end_line,start_offset,end_offset,details_json
                   FROM capture_row_locators
                   WHERE capture_id=? AND filename=? AND source_sha256=?
                     AND NOT (target_table=? AND row_key=?)
                   ORDER BY target_table,row_key""",
                (capture_id, anchor["filename"], source_sha, target_table,
                 capture_integrity.canonical_row_key(row_key)),
            ).fetchall()
            for candidate_row in candidates:
                candidate = dict(candidate_row)
                try:
                    candidate["details"] = json.loads(candidate.pop("details_json") or "{}")
                except json.JSONDecodeError:
                    candidate["details"] = {}
                    candidate.pop("details_json", None)

                relation = None
                a_start, a_end = anchor.get("start_offset"), anchor.get("end_offset")
                c_start, c_end = candidate.get("start_offset"), candidate.get("end_offset")
                if None not in (a_start, a_end, c_start, c_end):
                    if int(a_start) < int(c_end) and int(c_start) < int(a_end):
                        relation = "same source byte span"
                if relation is None:
                    a_first, a_last = anchor.get("start_line"), anchor.get("end_line")
                    c_first, c_last = candidate.get("start_line"), candidate.get("end_line")
                    if None not in (a_first, a_last, c_first, c_last):
                        if int(a_first) <= int(c_last) and int(c_first) <= int(a_last):
                            relation = "same source line span"
                if relation is None and anchor.get("locator_basis") == "sqlite-row" \
                        and candidate.get("locator_basis") == "sqlite-row":
                    ad = anchor.get("details") or {}
                    cd = candidate.get("details") or {}
                    if (ad.get("source_table") is not None and ad.get("source_rowid") is not None
                            and ad.get("source_table") == cd.get("source_table")
                            and ad.get("source_rowid") == cd.get("source_rowid")):
                        relation = "same SQLite source row"
                if relation is None:
                    continue

                identity = (
                    candidate["filename"], candidate["target_table"], candidate["row_key"]
                )
                if identity in seen:
                    continue
                seen.add(identity)
                candidate["relation"] = relation
                related.append(candidate)
    finally:
        con.row_factory = old_factory
    return anchors, related


def _capture_entity_identity_matches(
    con: sqlite3.Connection, capture_id: int, target_table: str, row_key: str
) -> list[dict]:
    """Decorate deterministic service-level entity matches with GUI drill-down links."""
    matches = capture_related_evidence.entity_identity_matches(
        con, capture_id, target_table, row_key
    )
    for item in matches:
        peer_table = item["target_table"]
        peer_key = item["row_key"]
        item["data_url"] = (
            f"/captures/query?table={quote(peer_table)}&capture_id={capture_id}"
        )
        item["entity_url"] = f"/entity/{int(item['entity_id'])}"
        item["source_url"] = None
        locators = capture_integrity.find_row_locators(
            con, capture_id, peer_table, peer_key
        )
        if locators:
            locator = locators[0]
            item["source_url"] = (
                f"/captures/{capture_id}/source-locator?"
                f"filename={quote(str(locator['filename']))}&"
                f"target_table={quote(peer_table)}&"
                f"row_key={quote(peer_key)}"
            )
    return matches


def _capture_item_identity_matches(
    con: sqlite3.Connection, capture_id: int, target_table: str, row_key: str
) -> list[dict]:
    """Decorate service-level ordinary-item matches with GUI drill-down links."""
    matches = capture_related_evidence.item_identity_matches(
        con, capture_id, target_table, row_key
    )
    for item in matches:
        peer_table = item["target_table"]
        peer_key = item["row_key"]
        item["data_url"] = (
            f"/captures/query?table={quote(peer_table)}&capture_id={capture_id}"
        )
        item["item_url"] = f"/items/{int(item['item_id'])}"
        item["source_url"] = None
        locators = capture_integrity.find_row_locators(
            con, capture_id, peer_table, peer_key
        )
        if locators:
            locator = locators[0]
            item["source_url"] = (
                f"/captures/{capture_id}/source-locator?"
                f"filename={quote(str(locator['filename']))}&"
                f"target_table={quote(peer_table)}&"
                f"row_key={quote(peer_key)}"
            )
    return matches


def _packet_correlation_ref_for_row(target_table: str, row_key: str) -> tuple[str, str] | None:
    """Translate one normalized capture row into packet_correlation's stable ref namespace."""
    try:
        key = json.loads(capture_integrity.canonical_row_key(row_key))
    except (TypeError, json.JSONDecodeError):
        return None
    try:
        if target_table == "capture_raw_packets":
            return packet_correlation.RAW, f"raw-packet:{int(key['seq'])}"
        if target_table == "capture_events":
            return packet_correlation.IDVIEW, f"idview:{key['zone_db']}:{int(key['seq'])}"
        if target_table == "capture_eventview":
            return packet_correlation.EVENTVIEW, f"eventview:{key['zone_db']}:{int(key['seq'])}"
    except (KeyError, TypeError, ValueError):
        return None
    return None


def _packet_correlation_row_for_ref(kind: str, ref: str) -> tuple[str, str] | None:
    """Translate a packet correlation peer ref back to a Data Explorer row identity."""
    try:
        if kind == packet_correlation.RAW and ref.startswith("raw-packet:"):
            seq = int(ref.split(":", 1)[1])
            return "capture_raw_packets", capture_integrity.canonical_row_key({"seq": seq})
        if kind == packet_correlation.EVENTVIEW and ref.startswith("eventview:"):
            zone, seq = ref.removeprefix("eventview:").rsplit(":", 1)
            return "capture_eventview", capture_integrity.canonical_row_key(
                {"zone_db": zone, "seq": int(seq)}
            )
        if kind == packet_correlation.IDVIEW and ref.startswith("idview:"):
            zone, seq = ref.removeprefix("idview:").rsplit(":", 1)
            return "capture_events", capture_integrity.canonical_row_key(
                {"zone_db": zone, "seq": int(seq)}
            )
    except (TypeError, ValueError):
        return None
    return None


@app.get("/captures/search", response_class=HTMLResponse)
def captures_search(
    request: Request,
    entity: str = "", message_id: str = "", ev_opcodes: list[str] = Query(default=[]),
    pk_category: str = "", pk_opcode: str = "",
    module: str = "", mode: str = "", q: str = "", page: int = 1,
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
    selected_module = module or mode or "events"
    if selected_module not in CAPTURE_EVIDENCE_MODULES:
        selected_module = "events"
    con = get_con()
    events = []
    packets = []
    generic_rows = []
    total = 0
    total_pages = 1
    page = max(1, page)

    available_ev_opcodes = [dict(r) for r in con.execute(
        "SELECT DISTINCT opcode, opcode_name FROM capture_events ORDER BY opcode").fetchall()]

    if selected_module == "events" and (entity or message_id or ev_opcodes):
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
                    "SELECT text FROM dialog_text WHERE zoneid=? AND idx=?", (zoneid, d["message_id"] - (_msgid_shift(con, d["capture_id"], zone_db, d["message_id"])[0] or 0))
                ).fetchone()
                d["dialog_text"] = trow[0] if trow else None
            d["related_row_key"] = capture_integrity.canonical_row_key(
                {"zone_db": d.get("zone_db"), "seq": d.get("seq")}
            )
            events.append(d)

    if selected_module == "packets" and (pk_category or pk_opcode):
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
            d["related_row_key"] = capture_integrity.canonical_row_key({"seq": d.get("seq")})
            packets.append(d)

    if selected_module not in {"events", "packets"}:
        generic_rows, total, total_pages, page = _capture_generic_search(
            con, selected_module, q, page
        )
        for row in generic_rows:
            row["related_row_key"] = _capture_search_row_key(row)

    categories = packet_decode.list_categories()
    con.close()
    # Pager needs to resubmit the current search's own filters (mode + whichever are set) plus a
    # new page number -- this page has two independent filter sets (events vs packets) that don't
    # share param names, so rather than re-deriving each combo in the template, the current
    # request's own query params (minus "page") are passed through as hidden inputs.
    qs_pairs = [(k, v) for k, v in request.query_params.multi_items() if k != "page"]
    if not qs_pairs:
        qs_pairs = [("module", selected_module)]
    return templates.TemplateResponse(request, "capture_search.html", {
        "module": selected_module,
        "module_meta": CAPTURE_EVIDENCE_MODULES[selected_module],
        "modules": [
            {"id": key, **value} for key, value in CAPTURE_EVIDENCE_MODULES.items()
        ],
        "q": q, "entity": entity, "message_id": message_id,
        "ev_opcodes": ev_opcodes, "available_ev_opcodes": available_ev_opcodes,
        "pk_category": pk_category, "pk_opcode": pk_opcode, "categories": categories,
        "events": events, "packets": packets, "generic_rows": generic_rows,
        "page": page, "total": total, "total_pages": total_pages, "qs_pairs": qs_pairs,
    })


@app.get("/captures/{capture_id}/related-evidence", response_class=HTMLResponse)
def captures_related_evidence(
    request: Request, capture_id: int, target_table: str, row_key: str,
):
    """Show only provenance-proven sibling evidence from the same physical source span."""
    con = get_con()
    cap = con.execute(
        "SELECT capture_id,capture_label FROM captures WHERE capture_id=?", (capture_id,)
    ).fetchone()
    if not cap:
        con.close()
        return HTMLResponse("Capture not found", status_code=404)

    allowed_tables = {
        "capture_actions", "capture_attack_delay", "capture_caplog_chat",
        "capture_chat_observations", "capture_events", "capture_eventview",
        "capture_hp_events", "capture_ki_events", "capture_level_range",
        "capture_npc_entries", "capture_npc_history", "capture_npc_path",
        "capture_pc_path", "capture_raw_packets", "capture_structured_records",
    }
    if target_table not in allowed_tables:
        con.close()
        raise HTTPException(status_code=400, detail="Unsupported capture evidence table")

    canonical_key = capture_integrity.canonical_row_key(row_key)
    anchors, related = _capture_related_locators(
        con, capture_id, target_table, canonical_key
    )

    entity_matches = _capture_entity_identity_matches(
        con, capture_id, target_table, canonical_key
    )
    item_matches = _capture_item_identity_matches(
        con, capture_id, target_table, canonical_key
    )

    packet_matches = []
    correlation_ref = _packet_correlation_ref_for_row(target_table, canonical_key)
    if correlation_ref is not None:
        # Rebuild from normalized observations so this drill-down never depends on a stale
        # correlation cache. Temporal/alignment matches may be persisted for the Alignment view,
        # but list_non_temporal_matches() excludes them from this verified Related Evidence panel.
        packet_correlation.correlate_capture(con, capture_id)
        kind, ref = correlation_ref
        for match in packet_correlation.list_non_temporal_matches(con, capture_id, kind, ref):
            peer = _packet_correlation_row_for_ref(match["peer_kind"], match["peer_ref"])
            if peer is None:
                continue
            peer_table, peer_key = peer
            item = {
                "target_table": peer_table,
                "row_key": peer_key,
                "relation": "explicit packet correlation",
                "basis": match["basis"],
                "score": match.get("score"),
                "peer_kind": match["peer_kind"],
                "peer_ref": match["peer_ref"],
                "details": match.get("details") or {},
                "data_url": (
                    f"/captures/query?table={quote(peer_table)}&capture_id={capture_id}"
                ),
                "packet_url": None,
                "source_url": None,
            }
            if peer_table == "capture_raw_packets":
                try:
                    seq = int(json.loads(peer_key)["seq"])
                except (TypeError, ValueError, KeyError, json.JSONDecodeError):
                    seq = None
                if seq is not None:
                    item["packet_url"] = f"/captures/{capture_id}/packets/{seq}"
            peer_locators = capture_integrity.find_row_locators(
                con, capture_id, peer_table, peer_key
            )
            if peer_locators:
                locator = peer_locators[0]
                item["source_url"] = (
                    f"/captures/{capture_id}/source-locator?"
                    f"filename={quote(str(locator['filename']))}&"
                    f"target_table={quote(peer_table)}&"
                    f"row_key={quote(peer_key)}"
                )
            packet_matches.append(item)

    for item in anchors + related:
        item["source_url"] = (
            f"/captures/{capture_id}/source-locator?"
            f"filename={quote(str(item['filename']))}&"
            f"target_table={quote(str(item['target_table']))}&"
            f"row_key={quote(str(item['row_key']))}"
        )
        item["data_url"] = (
            f"/captures/query?table={quote(str(item['target_table']))}&capture_id={capture_id}"
        )
        item["packet_url"] = None
        if item["target_table"] == "capture_raw_packets":
            try:
                seq = json.loads(item["row_key"]).get("seq")
            except (TypeError, json.JSONDecodeError):
                seq = None
            if seq is not None:
                item["packet_url"] = f"/captures/{capture_id}/packets/{int(seq)}"

    cap_dict = dict(cap)
    con.close()
    return templates.TemplateResponse(request, "capture_related_evidence.html", {
        "cap": cap_dict,
        "target_table": target_table,
        "row_key": canonical_key,
        "anchors": anchors,
        "related": related,
        "packet_matches": packet_matches,
        "entity_matches": entity_matches,
        "item_matches": item_matches,
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
                provenance = capture_integrity.record_source_file(
                    con, capture_id, uf.filename, data,
                    format_detected=None, parser_name="archive_open", row_count=0, error=str(ex),
                )
                con.commit()
                results.append({
                    "filename": uf.filename, "format": None, "rows": 0, "error": str(ex),
                    "sha256": provenance["sha256"], "byte_size": provenance["byte_size"],
                })
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


@app.get("/captures/{capture_id}/alignment", response_class=HTMLResponse)
def captures_alignment(request: Request, capture_id: int, video_ts: float | None = None,
                       capture_ts: float | None = None, clock_kind: str = "", error: str = ""):
    con = get_con()
    build_capture_index.init_db(con)
    timeline_alignment.init_db(con)
    cap = con.execute("SELECT * FROM captures WHERE capture_id=?", (capture_id,)).fetchone()
    if not cap:
        con.close()
        return HTMLResponse("Capture not found", status_code=404)
    summary = timeline_alignment.alignment_summary(con, capture_id)
    video_candidates = timeline_alignment.video_timeline_candidates(con, capture_id)
    capture_candidates = timeline_alignment.capture_timeline_candidates(con, capture_id)
    landmarks = timeline_alignment.shared_packet_landmarks(con, capture_id)
    packet_correlation.init_db(con)
    correlations = packet_correlation.list_correlations(con, capture_id)
    correlation_summary = {
        "matched": sum(1 for row in correlations if row["status"] == packet_correlation.STATUS_MATCHED),
        "ambiguous": sum(1 for row in correlations if row["status"] == packet_correlation.STATUS_AMBIGUOUS),
        "total": len(correlations),
    }
    con.close()
    return templates.TemplateResponse(request, "capture_alignment.html", {
        "cap": dict(cap),
        "summary": summary,
        "video_candidates": video_candidates,
        "capture_candidates": capture_candidates,
        "landmarks": landmarks,
        "correlations": correlations,
        "correlation_summary": correlation_summary,
        "clock_kinds": sorted(timeline_alignment.CLOCK_KINDS),
        "prefill_video_ts": video_ts,
        "prefill_capture_ts": capture_ts,
        "prefill_clock_kind": clock_kind,
        "error": error,
        "key_evidence_types": sorted(timeline_alignment.KEY_EVIDENCE_TYPES),
    })


@app.post("/captures/{capture_id}/alignment/correlate")
def captures_alignment_correlate(capture_id: int):
    con = get_con()
    try:
        packet_correlation.correlate_capture(con, capture_id)
    finally:
        con.close()
    return RedirectResponse(url=f"/captures/{capture_id}/alignment", status_code=303)


@app.post("/captures/{capture_id}/alignment/anchors")
async def captures_alignment_add_anchor(request: Request, capture_id: int):
    form = await request.form()
    try:
        video_ts = float(form.get("video_ts"))
        capture_ts = float(form.get("capture_ts"))
        clock_kind = str(form.get("clock_kind") or "")
        source_type = str(form.get("source_type") or "MANUAL")
        label = (form.get("label") or "").strip() or None
        video_ref = (form.get("video_ref") or "").strip() or None
        capture_ref = (form.get("capture_ref") or "").strip() or None
        notes = (form.get("notes") or "").strip() or None
        con = get_con()
        timeline_alignment.add_anchor(
            con, capture_id,
            video_ts=video_ts,
            capture_ts=capture_ts,
            clock_kind=clock_kind,
            source_type=source_type,
            label=label,
            video_ref=video_ref,
            capture_ref=capture_ref,
            notes=notes,
        )
        packet_correlation.correlate_capture(con, capture_id)
        con.close()
    except (TypeError, ValueError) as exc:
        return RedirectResponse(
            url=f"/captures/{capture_id}/alignment?error={quote(str(exc))}",
            status_code=303,
        )
    return RedirectResponse(url=f"/captures/{capture_id}/alignment", status_code=303)


@app.post("/captures/{capture_id}/alignment/anchors/{anchor_id}/delete")
def captures_alignment_delete_anchor(capture_id: int, anchor_id: str):
    con = get_con()
    timeline_alignment.delete_anchor(con, capture_id, anchor_id)
    packet_correlation.correlate_capture(con, capture_id)
    con.close()
    return RedirectResponse(url=f"/captures/{capture_id}/alignment", status_code=303)


def _key_evidence_file_path(capture_id: int, evidence_id: str, suffix: str) -> Path:
    capture_root = (KEY_EVIDENCE_ROOT / str(int(capture_id))).resolve()
    capture_root.mkdir(parents=True, exist_ok=True)
    target = (capture_root / f"{evidence_id}{suffix}").resolve()
    try:
        target.relative_to(capture_root)
    except ValueError:
        raise ValueError("key evidence path escapes capture evidence root")
    return target


@app.post("/captures/{capture_id}/alignment/evidence")
async def captures_alignment_add_evidence(request: Request, capture_id: int):
    form = await request.form()
    stored_path = None
    try:
        evidence_type = str(form.get("evidence_type") or "KEY_EVENT").upper()
        label = (form.get("label") or "").strip()
        video_raw = (form.get("video_ts") or "").strip()
        capture_raw = (form.get("capture_ts") or "").strip()
        clock_kind = (form.get("clock_kind") or "").strip() or None
        anchor_id = (form.get("anchor_id") or "").strip() or None
        source_ref = (form.get("source_ref") or "").strip() or None
        notes = (form.get("notes") or "").strip() or None
        video_ts = float(video_raw) if video_raw else None
        capture_ts = float(capture_raw) if capture_raw else None
        upload = form.get("screenshot")
        evidence_id = f"keyev-{uuid.uuid4().hex[:16]}"
        file_ref = mime_type = None

        if upload is not None and getattr(upload, "filename", None):
            data = await upload.read()
            if not data:
                raise ValueError("uploaded screenshot is empty")
            if len(data) > KEY_EVIDENCE_MAX_BYTES:
                raise ValueError("screenshot exceeds 20 MB limit")
            mime_type = (getattr(upload, "content_type", None) or "").lower()
            suffix = KEY_EVIDENCE_IMAGE_TYPES.get(mime_type)
            if suffix is None:
                raise ValueError("screenshot must be PNG, JPEG, WebP, or BMP")
            try:
                with Image.open(io.BytesIO(data)) as img:
                    img.verify()
            except Exception as exc:
                raise ValueError(f"uploaded screenshot is not a valid image: {exc}") from exc
            stored_path = _key_evidence_file_path(capture_id, evidence_id, suffix)
            stored_path.write_bytes(data)
            file_ref = stored_path.relative_to(TOOLS_ROOT).as_posix()
            evidence_type = "SCREENSHOT"

        con = get_con()
        cap = con.execute("SELECT 1 FROM captures WHERE capture_id=?", (capture_id,)).fetchone()
        if not cap:
            con.close()
            raise ValueError("capture not found")
        timeline_alignment.add_key_evidence(
            con,
            capture_id,
            evidence_type=evidence_type,
            label=label,
            video_ts=video_ts,
            capture_ts=capture_ts,
            clock_kind=clock_kind,
            anchor_id=anchor_id,
            source_ref=source_ref,
            file_ref=file_ref,
            mime_type=mime_type,
            notes=notes,
            evidence_id=evidence_id,
        )
        con.close()
    except (TypeError, ValueError) as exc:
        if stored_path is not None:
            stored_path.unlink(missing_ok=True)
        return RedirectResponse(
            url=f"/captures/{capture_id}/alignment?error={quote(str(exc))}",
            status_code=303,
        )
    return RedirectResponse(url=f"/captures/{capture_id}/alignment", status_code=303)


@app.post("/captures/{capture_id}/alignment/evidence/{evidence_id}/delete")
def captures_alignment_delete_evidence(capture_id: int, evidence_id: str):
    con = get_con()
    timeline_alignment.init_db(con)
    row = con.execute(
        "SELECT file_ref FROM capture_key_evidence WHERE capture_id=? AND evidence_id=?",
        (capture_id, evidence_id),
    ).fetchone()
    deleted = timeline_alignment.delete_key_evidence(con, capture_id, evidence_id)
    con.close()
    if deleted and row and row[0]:
        candidate = (TOOLS_ROOT / row[0]).resolve()
        root = (KEY_EVIDENCE_ROOT / str(int(capture_id))).resolve()
        try:
            candidate.relative_to(root)
        except ValueError:
            pass
        else:
            candidate.unlink(missing_ok=True)
    return RedirectResponse(url=f"/captures/{capture_id}/alignment", status_code=303)


@app.get("/captures/{capture_id}/alignment/evidence/{evidence_id}/image")
def captures_alignment_evidence_image(capture_id: int, evidence_id: str):
    con = get_con()
    timeline_alignment.init_db(con)
    row = con.execute(
        """SELECT file_ref,mime_type FROM capture_key_evidence
           WHERE capture_id=? AND evidence_id=? AND file_ref IS NOT NULL""",
        (capture_id, evidence_id),
    ).fetchone()
    con.close()
    if not row:
        raise HTTPException(status_code=404, detail="Screenshot evidence not found")
    target = (TOOLS_ROOT / row[0]).resolve()
    root = (KEY_EVIDENCE_ROOT / str(int(capture_id))).resolve()
    try:
        target.relative_to(root)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid evidence path")
    if not target.is_file():
        raise HTTPException(status_code=404, detail="Screenshot file missing")
    return FileResponse(target, media_type=row[1] or "application/octet-stream")


@app.post("/captures/{capture_id}/rebuild-source")
async def captures_rebuild_source(request: Request, capture_id: int):
    form = await request.form()
    filename = str(form.get("filename") or "").strip()
    if not filename:
        return RedirectResponse(
            url=f"/captures/{capture_id}?rebuild_error={quote('source filename is required')}",
            status_code=303,
        )
    con = get_con()
    try:
        result = build_capture_index.rebuild_capture_source(con, capture_id, filename)
        scope = result.get("scope") or "single_source"
        rows = result.get("rows", 0)
        message = f"Rebuilt {filename} ({scope}, {rows} normalized rows)"
        return RedirectResponse(
            url=f"/captures/{capture_id}?rebuild_status={quote(message)}",
            status_code=303,
        )
    except Exception as ex:
        return RedirectResponse(
            url=f"/captures/{capture_id}?rebuild_error={quote(str(ex))}",
            status_code=303,
        )
    finally:
        con.close()


@app.get("/captures/{capture_id}/source-locator", response_class=HTMLResponse)
def captures_source_locator(
    request: Request,
    capture_id: int,
    filename: str,
    target_table: str,
    row_key: str,
):
    """Inspect the exact physical source row/block behind one normalized capture row."""
    con = get_con()
    cap = con.execute("SELECT * FROM captures WHERE capture_id=?", (capture_id,)).fetchone()
    if not cap:
        con.close()
        return HTMLResponse("Capture not found", status_code=404)

    locators = capture_integrity.find_row_locators(con, capture_id, target_table, row_key)
    locator = next((item for item in locators if item["filename"] == filename), None)
    if locator is None:
        con.close()
        return HTMLResponse("Capture source locator not found", status_code=404)

    source_state = "unavailable"
    source_error = None
    source_excerpt = None
    source_row = None
    source_columns = []
    path, _subroot, origin_error = build_capture_index._capture_source_origin(con, capture_id)
    if origin_error:
        source_error = origin_error
    else:
        src = None
        try:
            src = build_capture_index.Source(path)
            if filename not in set(src.list_files()):
                source_error = "Source file is no longer present in the original folder/archive."
            else:
                data = src.read_bytes(filename)
                current_hash = capture_integrity.sha256_bytes(data)
                if locator.get("source_sha256") and current_hash != locator["source_sha256"]:
                    source_state = "hash_mismatch"
                    source_error = (
                        "Current source bytes do not match the SHA-256 recorded when this evidence "
                        "was ingested; current bytes are not displayed as original evidence."
                    )
                elif locator["locator_basis"] == "sqlite-row":
                    details = locator.get("details") or {}
                    source_table = str(details.get("source_table") or "")
                    source_rowid = details.get("source_rowid")
                    if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", source_table) or source_rowid is None:
                        source_error = "SQLite locator is missing a safe source table or rowid."
                    else:
                        sub, tmp_path = src.open_sqlite(filename)
                        try:
                            sub.row_factory = sqlite3.Row
                            row = sub.execute(
                                f'SELECT rowid AS __source_rowid__, * FROM "{source_table}" WHERE rowid=?',
                                (int(source_rowid),),
                            ).fetchone()
                            if row is None:
                                source_error = "The recorded SQLite rowid is not present in the source database."
                            else:
                                source_state = "verified"
                                source_columns = list(row.keys())
                                source_row = {key: row[key] for key in source_columns}
                                for key, value in list(source_row.items()):
                                    if isinstance(value, (bytes, bytearray)):
                                        source_row[key] = bytes(value).hex()
                        finally:
                            build_capture_index.close_sqlite(sub, tmp_path)
                else:
                    start = locator.get("start_offset")
                    end = locator.get("end_offset")
                    if start is not None and end is not None:
                        if end < start:
                            source_error = "Recorded byte range is invalid."
                        else:
                            raw = data[int(start):int(end)]
                            if len(raw) > 262144:
                                raw = raw[:262144]
                                source_error = "Source excerpt exceeded 256 KiB and was truncated for display."
                            source_excerpt = raw.decode("utf-8", "replace")
                            source_state = "verified"
                    elif locator.get("start_line") is not None:
                        decoded = data.decode("utf-8", "replace").splitlines()
                        first = max(1, int(locator["start_line"]))
                        last = max(first, int(locator.get("end_line") or first))
                        source_excerpt = "\n".join(decoded[first - 1:last])
                        source_state = "verified"
                    else:
                        source_error = "This locator has no displayable physical source span."
        except Exception as ex:
            source_error = f"{type(ex).__name__}: {ex}"
        finally:
            if src is not None:
                src.close()

    cap_dict = dict(cap)
    con.close()
    return templates.TemplateResponse(request, "capture_source_locator.html", {
        "cap": cap_dict,
        "locator": locator,
        "source_state": source_state,
        "source_error": source_error,
        "source_excerpt": source_excerpt,
        "source_row": source_row,
        "source_columns": source_columns,
    })


@app.get("/captures/{capture_id}", response_class=HTMLResponse)
def captures_detail(
    request: Request, capture_id: int, content_type: str = "", q: str = "",
    rebuild_status: str = "", rebuild_error: str = "",
):
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
    detail["n_structured_records"] = con.execute(
        "SELECT COUNT(*) FROM capture_structured_records WHERE capture_id=?", (capture_id,)
    ).fetchone()[0]
    detail["structured_records"] = con.execute(
        """SELECT family,record_type,ts,zone,entity_id,entity_name,item_id,item_name,price,
                  source_file,record_key,payload_json
           FROM capture_structured_records WHERE capture_id=?
           ORDER BY family,source_file,record_key LIMIT 200""",
        (capture_id,),
    ).fetchall()
    detail["pc_path_zones"] = build_capture_index.get_pc_path_zones(con, capture_id)
    detail["tags"] = build_capture_index.get_capture_tags(con, capture_id)
    _detail_tags = build_capture_index.all_tag_choices(con)
    detail["hp_events"] = con.execute(
        "SELECT mob_name, hp_low, hp_high FROM capture_hp_events WHERE capture_id=? ORDER BY seq",
        (capture_id,)).fetchall()
    detail["health"] = capture_integrity.capture_health(con, capture_id)
    detail["exact_capture_duplicates"] = capture_integrity.find_exact_capture_duplicates(con, capture_id)
    rebuild_inventory = {
        item["filename"]: item
        for item in build_capture_index.capture_rebuild_inventory(con, capture_id)
    }
    for source_row in detail["health"].get("source_manifest", []):
        source_row["rebuild"] = rebuild_inventory.get(source_row["filename"])

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
        "all_tags": _detail_tags,
        "rebuild_status": rebuild_status, "rebuild_error": rebuild_error,
    })


@app.get("/shift-master", response_class=HTMLResponse)
def shift_master_page(request: Request):
    from workbench.captures import msgid_shift
    con = get_con()
    try:
        msgid_shift.ensure_master_tables(con)
        rows = [dict(r) for r in con.execute(
            """SELECT m.*, COALESCE(z.name,'?') AS zone_name,
                      (SELECT COUNT(*) FROM dialog_drift_report d WHERE d.zoneid=m.zoneid AND d.status='mismatch') AS drift
               FROM msgid_shift_master m LEFT JOIN zones z ON z.zoneid=m.zoneid ORDER BY m.zoneid, m.id_lo""")]
        o = con.execute("SELECT COUNT(*), COUNT(DISTINCT capture_id) FROM msgid_shift_obs").fetchone()
    finally:
        con.close()
    return templates.TemplateResponse(request, "shift_master.html", {"rows": rows, "obs_total": o[0], "obs_caps": o[1]})


@app.post("/shift-master/rebuild")
def shift_master_rebuild():
    from workbench.captures import msgid_shift
    con = get_con()
    try:
        ids = [r[0] for r in con.execute("SELECT DISTINCT capture_id FROM capture_caplog_chat")]
        for cid in ids:
            msgid_shift.observe(con, cid, zoneid_for_zone_db)
        msgid_shift.build_master(con)
        _SHIFT_CACHE.clear()
    finally:
        con.close()
    return RedirectResponse("/shift-master", status_code=303)


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
                "SELECT text FROM dialog_text WHERE zoneid=? AND idx=?", (zoneid, d["message_id"] - (_msgid_shift(con, capture_id, zone_db, d["message_id"])[0] or 0))
            ).fetchone()
            d["dialog_text"] = trow[0] if trow else None
        sh, info = _msgid_shift(con, capture_id, zone_db, d["message_id"])
        d["shift_info"] = info
        d["shift_verified"] = sh is not None
        events.append(d)

    interaction_candidates = reconstruct_interaction_candidates(events)

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
        "events": events, "interaction_candidates": interaction_candidates,
        "ki_events": ki_events, "eventview": eventview, "items": items,
        "actions": actions,
        "events_total": events_total, "eventview_total": eventview_total,
        "raw_packets_total": raw_packets_total,
        "show_items": show_items, "item_containers": item_containers,
        "items_matching_total": items_matching_total, "default_tab": default_tab,
        "entity": entity, "opcodes": opcodes, "available_opcodes": available_opcodes,
        "direction": direction, "directions": directions,
        "ev_gp": ev_gp, "show_raw": show_raw,
    })


@app.get("/captures/{capture_id}/packets/{seq}", response_class=HTMLResponse)
def capture_packet_detail(request: Request, capture_id: int, seq: int):
    """Contextual decoder for one canonical raw packet observation.

    Unlike the ad-hoc /packets/decode page, this keeps the packet inside its capture/session:
    timestamp, source provenance, neighboring packets and cross-source correlations remain visible
    while the exact same packet_decode.analyze_layout() drives the byte/field inspector.
    """
    con = get_con()
    cap = con.execute("SELECT * FROM captures WHERE capture_id=?", (capture_id,)).fetchone()
    row = con.execute(
        "SELECT * FROM capture_raw_packets WHERE capture_id=? AND seq=?",
        (capture_id, seq),
    ).fetchone()
    if not cap or not row:
        con.close()
        return HTMLResponse("Capture packet not found", status_code=404)

    packet = dict(row)
    layout = None
    decode_error = None
    pd_direction = None
    direction_basis = "capture observation"
    try:
        opcode_int = int(packet["opcode"], 0)
        if packet["direction"] == "incoming":
            pd_direction = "s2c"
        elif packet["direction"] == "outgoing":
            pd_direction = "c2s"
        else:
            # Network-level evidence may legitimately have unknown endpoint roles. Do not coerce
            # unknown to c2s. A unique definition can select a decode schema for inspection while
            # the underlying observation direction remains unknown.
            known = [
                d for d in ("s2c", "c2s")
                if packet_decode.get_field_schema(d, opcode_int) is not None
            ]
            if len(known) == 1:
                pd_direction = known[0]
                direction_basis = "unique known opcode definition; capture direction remains unknown"
        packet["pd_direction"] = pd_direction
        packet["decode_direction_basis"] = direction_basis
        if pd_direction is None:
            decode_error = (
                "Capture direction is unknown and this opcode does not have exactly one unambiguous "
                "known direction definition; raw evidence is preserved without guessing a decoder side."
            )
        else:
            layout = packet_decode.analyze_layout(pd_direction, opcode_int, packet["raw_hex"])
    except Exception as exc:
        decode_error = str(exc)

    prev_row = con.execute(
        """SELECT seq,ts,direction,opcode FROM capture_raw_packets
           WHERE capture_id=? AND seq<? ORDER BY seq DESC LIMIT 1""",
        (capture_id, seq),
    ).fetchone()
    next_row = con.execute(
        """SELECT seq,ts,direction,opcode FROM capture_raw_packets
           WHERE capture_id=? AND seq>? ORDER BY seq ASC LIMIT 1""",
        (capture_id, seq),
    ).fetchone()

    neighbor_rows = con.execute(
        """SELECT seq,ts,direction,opcode FROM capture_raw_packets
           WHERE capture_id=? AND seq BETWEEN ? AND ? ORDER BY seq""",
        (capture_id, max(0, seq - 6), seq + 6),
    ).fetchall()
    neighbors = []
    for neighbor in neighbor_rows:
        item = dict(neighbor)
        try:
            n_direction = "s2c" if item["direction"] == "incoming" else (
                "c2s" if item["direction"] == "outgoing" else None
            )
            n_result = packet_decode.decode(n_direction, int(item["opcode"], 0), "") if n_direction else None
            item["description"] = n_result.description if n_result else None
        except Exception:
            item["description"] = None
        neighbors.append(item)

    locator = con.execute(
        """SELECT filename,source_sha256,locator_basis,start_line,end_line,start_offset,end_offset,details_json
           FROM capture_row_locators
           WHERE capture_id=? AND target_table='capture_raw_packets' AND row_key=?
           ORDER BY filename LIMIT 1""",
        (capture_id, json.dumps({"seq": seq}, sort_keys=True)),
    ).fetchone()
    provenance = dict(locator) if locator else None
    if provenance:
        provenance["row_key"] = json.dumps({"seq": seq}, sort_keys=True)
        try:
            provenance["details"] = json.loads(provenance.pop("details_json") or "{}")
        except json.JSONDecodeError:
            provenance["details"] = {}

    packet_correlation.init_db(con)
    raw_ref = f"raw-packet:{seq}"
    corr_rows = con.execute(
        """SELECT * FROM capture_packet_correlations
           WHERE capture_id=?
             AND ((source_kind=? AND source_ref=?) OR (target_kind=? AND target_ref=?))
           ORDER BY status,basis,ABS(COALESCE(time_delta_seconds,0)),correlation_id""",
        (capture_id, packet_correlation.RAW, raw_ref, packet_correlation.RAW, raw_ref),
    ).fetchall()
    correlations = []
    for corr in corr_rows:
        d = dict(corr)
        d["other_kind"] = d["target_kind"] if d["source_kind"] == packet_correlation.RAW and d["source_ref"] == raw_ref else d["source_kind"]
        d["other_ref"] = d["target_ref"] if d["source_kind"] == packet_correlation.RAW and d["source_ref"] == raw_ref else d["source_ref"]
        try:
            d["details"] = json.loads(d.get("details_json") or "{}")
        except json.JSONDecodeError:
            d["details"] = {}
        d["other_href"] = None
        if d["other_kind"] == packet_correlation.RAW and d["other_ref"].startswith("raw-packet:"):
            try:
                other_seq = int(d["other_ref"].split(":", 1)[1])
                d["other_href"] = f"/captures/{capture_id}/packets/{other_seq}"
            except ValueError:
                pass
        elif d["other_kind"] == packet_correlation.EVENTVIEW:
            d["other_href"] = f"/captures/{capture_id}/timeline?tab=raw&show_raw=1"
        elif d["other_kind"] == packet_correlation.IDVIEW:
            d["other_href"] = f"/captures/{capture_id}/timeline?tab=events"
        elif d["other_kind"] == packet_correlation.VIDEO:
            d["other_href"] = f"/captures/{capture_id}/alignment"
        correlations.append(d)

    con.close()
    return templates.TemplateResponse(request, "capture_packet_detail.html", {
        "cap": cap, "capture_id": capture_id, "packet": packet, "layout": layout,
        "decode_error": decode_error, "prev_packet": prev_row, "next_packet": next_row,
        "neighbors": neighbors, "provenance": provenance, "correlations": correlations,
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
def settings_page(request: Request, saved: str = "", backup: str = "", ok: str = "", brand_error: str = ""):
    con = get_con()
    values = settings_mod.get_all(con)
    con.close()
    return templates.TemplateResponse(request, "settings.html", {
        "values": values, "saved": bool(saved), "backups": _list_backups(),
        "backup_result": backup, "backup_ok": bool(int(ok)) if ok else None,
        "brand_error": brand_error,
        "llm_key_configured": llm_client.has_api_key(),
        "ah_env_overrides": {k: settings_mod.ah_flag_source(k) for k in settings_mod.AH_FLAGS},
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

    brand_icon_value = None
    if form.get("shell_brand_reset_icon"):
        for existing in BRANDING_DIR.glob("custom_brand.*"):
            existing.unlink(missing_ok=True)
        brand_icon_value = "/static/valhalla_logo.png"
    else:
        upload = form.get("shell_brand_icon_upload")
        if upload is not None and getattr(upload, "filename", ""):
            raw = await upload.read()
            if len(raw) > BRAND_ICON_MAX_BYTES:
                return RedirectResponse(url="/settings?brand_error=Brand+icon+must+be+2+MB+or+smaller", status_code=303)
            try:
                with Image.open(io.BytesIO(raw)) as img:
                    image_format = (img.format or "").upper()
                    img.verify()
            except Exception:
                return RedirectResponse(url="/settings?brand_error=Uploaded+brand+icon+is+not+a+valid+image", status_code=303)
            ext = BRAND_ICON_FORMATS.get(image_format)
            if not ext:
                return RedirectResponse(url="/settings?brand_error=Brand+icon+must+be+PNG,+JPG,+WEBP,+or+GIF", status_code=303)
            for existing in BRANDING_DIR.glob("custom_brand.*"):
                existing.unlink(missing_ok=True)
            output = BRANDING_DIR / f"custom_brand{ext}"
            output.write_bytes(raw)
            brand_icon_value = f"/static/branding/{output.name}"

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
        "live_client_source": (form.get("live_client_source", "disabled")
                               if form.get("live_client_source") in ("disabled", "replay", "file_feed") else "disabled"),
        "live_client_feed_file": form.get("live_client_feed_file", "").strip()[:2048],
        "live_client_feed_client": form.get("live_client_feed_client", "").strip()[:200],
        "live_client_replay_file": form.get("live_client_replay_file", "").strip()[:2048],
        "live_client_replay_client": form.get("live_client_replay_client", "").strip()[:200],
        "live_client_auto_connect": "1" if form.get("live_client_auto_connect") else "0",
        "xi_model_viewer_url": form.get("xi_model_viewer_url", "").strip(),
        "shell_brand_enabled": "1" if form.get("shell_brand_enabled") else "0",
        "shell_brand_text": form.get("shell_brand_text", "").strip()[:80],
        **({"shell_brand_icon": brand_icon_value} if brand_icon_value is not None else {}),
        "port": port_value,
        "backup_retention_count": retention_value,
        "llm_base_url": form.get("llm_base_url", "").strip() or settings_mod.DEFAULTS["llm_base_url"],
        "llm_default_model": form.get("llm_default_model", "").strip() or settings_mod.DEFAULTS["llm_default_model"],
        "ah_legacy_test_writes": "1" if form.get("ah_legacy_test_writes") else "0",
        "ah_dsp_myisam_test_writes": "1" if form.get("ah_dsp_myisam_test_writes") else "0",
        "ah_augmented_reward_test_writes": "1" if form.get("ah_augmented_reward_test_writes") else "0",
        "ah_preview_ttl_seconds": (form.get("ah_preview_ttl_seconds", "").strip()
                                   if form.get("ah_preview_ttl_seconds", "").strip().isdigit()
                                   else settings_mod.DEFAULTS["ah_preview_ttl_seconds"]),
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


# ---- Domain landing pages -------------------------------------------------------------------
@app.get("/domains/assault", response_class=HTMLResponse)
def assault_domain_page(request: Request):
    """Assault domain workspace: a stable home for Assault-specific development/admin workflows.

    Existing generic editors remain canonical; this page links into them rather than duplicating
    Zone Editor or mission/capture logic while the domain package grows.
    """
    return templates.TemplateResponse(request, "domain_assault.html", {"request": request})


# ---- Nyzul Isle plot tool (nyzul_plot.py) ---------------------------------------------------
from workbench.devtools.domains import nyzul_plot
from workbench.devtools.spatial import zone_plot  # reused below for zone 77's live door/prop rows (npc_list "_"-named entities)


@app.get("/nyzul", response_class=HTMLResponse)
def nyzul_page(request: Request):
    return templates.TemplateResponse(request, "nyzul_plot.html", {
        "request": request, "obj_available": (ZONE_VISUAL_DIR / "77.obj").exists()})


@app.get("/nyzul/data.json")
def nyzul_data():
    d = nyzul_plot.load_data()
    d["reach"] = nyzul_plot.reachability()
    d["exclusions"] = nyzul_plot.load_exclusions()
    # Door/wall props for zone 77, straight from the live DB -- same npc_list "_"-prefixed-name
    # convention Zone Plot already uses to tell doors/props apart from real NPCs (zone_plot.py's
    # zone_data()), reused here rather than re-deriving it.
    try:
        d["doors"] = [e for e in zone_plot.zone_data(77, server="dsp")["entities"] if e["k"] == "d"]
    except Exception as ex:
        d["doors"] = []
        d["doors_error"] = str(ex)
    return JSONResponse(d)


@app.get("/nyzul/navmesh.bin")
def nyzul_navmesh():
    return Response(nyzul_plot.nav_triangles_bytes(), media_type="application/octet-stream")


@app.post("/nyzul/exclusions")
async def nyzul_save_exclusions(request: Request):
    nyzul_plot.save_exclusions(await request.json())
    return {"ok": True}


# ---- Generic zone plot (zone_plot.py) -------------------------------------------------------
# (imported above, alongside nyzul_plot)


@app.get("/zoneplot")
def zoneplot_page():
    """Legacy Zone Editor entrypoint retained only for old bookmarks."""
    return RedirectResponse(url="/zoneplot2", status_code=308)


@app.get("/zoneplot2", response_class=HTMLResponse)
def zoneplot2_page(request: Request):
    return templates.TemplateResponse(request, "zone_plot2.html", {"request": request})


@app.get("/zoneplot/server.json")
def zoneplot_server_get():
    from workbench.runtime import settings_store as settings
    return JSONResponse({"server": zone_plot.get_server(), "dsp_configured": settings.get_dsp_root() is not None})


@app.post("/zoneplot/server.json")
async def zoneplot_server_set(request: Request):
    b = await request.json()
    try:
        zone_plot.set_server(b["server"])
        return JSONResponse({"server": zone_plot.get_server()})
    except Exception as ex:
        return JSONResponse({"error": str(ex)}, status_code=400)


@app.get("/zoneplot/zones.json")
def zoneplot_zones():
    return JSONResponse(zone_plot.zone_list())


@app.get("/zoneplot/{zid}/live_info.json")
def zoneplot_live_info(zid: int):
    """Same live-parse availability check as zone_view3d (Phase 3) -- reused by the Zone Editor's
    'Live (textured)' mesh complexity option so it can fetch+parse the real zone DAT client-side
    instead of the untextured .zmesh/OBJ pipeline."""
    con = get_con()
    zone_row = con.execute("SELECT geometry_rom_path FROM zones WHERE zoneid=?", (zid,)).fetchone()
    con.close()
    geometry_rom_path = zone_row[0] if zone_row else None
    ffxi_path = settings_mod.get_ffxi_install()
    return JSONResponse({
        "available": bool(ffxi_path and geometry_rom_path),
        "ffxi_path": ffxi_path or "",
        "geometry_rom_path": geometry_rom_path or "",
    })


@app.get("/zoneplot/descriptors.json")
def zoneplot_descriptors():
    import json as _j
    d = TOOLS_ROOT / "plot_descriptors"
    return JSONResponse([_j.loads(f.read_text()) for f in sorted(d.glob("*.json"))])


@app.get("/zoneplot/{zid}/data.json")
def zoneplot_data(zid: int, instance: int = 0):
    d = zone_plot.zone_data(zid, instance)
    d["obj"] = True  # /mesh.zmesh builds the cache on demand; empty response if the zone has no geometry
    return JSONResponse(d)


@app.get("/zoneplot/{zid}/capture_paths.json")
def zoneplot_capture_paths_list(zid: int):
    """Captures with PathLog data in this zone, for the Zone Editor's Paths tab."""
    con = get_con()
    try:
        return JSONResponse({"captures": capture_paths.captures_for_zone(con, zid)})
    finally:
        con.close()


@app.get("/zoneplot/{zid}/capture_paths/{capture_id}.json")
def zoneplot_capture_paths(zid: int, capture_id: int):
    """Full per-leg PathLog traces (PC + every NPC/mob) for one capture in this zone."""
    con = get_con()
    try:
        return JSONResponse(capture_paths.capture_paths(con, zid, capture_id))
    finally:
        con.close()


@app.get("/zoneplot/from_capture")
def captures_zoneplot_redirect(capture_id: int, entity_id: int = 0, pc: int = 0, zone_db: str = ""):
    """Capture-section entry point into the Zone Editor's Paths tab (replaces the old per-entity
    2D/3D plot links): resolves the capture's zone and deep-links capture/entity/PC selection."""
    con = get_con()
    if not zone_db:
        if entity_id:
            row = con.execute("SELECT zone_db FROM capture_npc_entries WHERE capture_id=? AND entity_id=?",
                              (capture_id, entity_id)).fetchone()
            zone_db = row[0] if row else ""
        if not zone_db:
            cap = con.execute("SELECT zones FROM captures WHERE capture_id=?", (capture_id,)).fetchone()
            zones = json.loads(cap["zones"]) if cap and cap["zones"] else []
            zone_db = zones[0] if zones else ""
    zoneid = zoneid_for_zone_db(con, zone_db) if zone_db else None
    con.close()
    if zoneid is None:
        return PlainTextResponse("Could not resolve this capture's zone to a zone id.", status_code=404)
    qs = f"zone={zoneid}&capture={capture_id}" + ("&pc=1" if pc else "") + (f"&entity={entity_id}" if entity_id else "")
    return RedirectResponse(url=f"/zoneplot2?{qs}", status_code=303)


@app.get("/zoneplot/{zid}/reach.json")
def zoneplot_reach(zid: int, instance: int = 0, ax: float = None, ay: float = 0.0, az: float = 0.0):
    return JSONResponse(zone_plot.reach(zid, (ax, ay, az) if ax is not None else None, instance))


@app.get("/zoneplot/{zid}/navdiag.json")
def zoneplot_navdiag(zid: int, x: float, y: float, z: float):
    try:
        return JSONResponse(zone_plot.nav_diagnostics(zid, x, y, z))
    except Exception as ex:
        return JSONResponse({"error": str(ex)}, status_code=400)


@app.get("/zoneplot/{zid}/navpath.json")
def zoneplot_navpath(zid: int, x1: float, y1: float, z1: float, x2: float, y2: float, z2: float):
    try:
        return JSONResponse(zone_plot.nav_route(zid, (x1, y1, z1), (x2, y2, z2)))
    except Exception as ex:
        return JSONResponse({"ok": False, "reason": str(ex)}, status_code=400)


@app.get("/zoneplot/{zid}/scripts.json")
def zoneplot_scripts(zid: int):
    try:
        return JSONResponse(zone_plot.script_info(zid))
    except Exception as ex:
        return JSONResponse({"error": str(ex)}, status_code=400)


@app.get("/zoneplot/{zid}/mesh.zmesh")
def zoneplot_mesh(zid: int, lod: int = 0):
    from workbench.devtools.spatial import zmesh as zmesh
    if not (ZONE_VISUAL_DIR / f"{zid}.obj").exists():  # build the visual-mesh cache on demand
        import sqlite3
        from workbench.runtime import settings_store as settings
        from workbench.devtools.spatial import build_visual_cache as bz
        ffxi = settings.get_ffxi_install()
        if ffxi:
            con = sqlite3.connect(str(bz.DB_PATH))
            try:
                bz.build_one(con, zid, ffxi)
            finally:
                con.close()
    p = zmesh.convert(zid, lod=lod if lod in zmesh.LODS else 0)
    if not p:
        return Response(b"", media_type="application/octet-stream")
    return FileResponse(p, media_type="application/octet-stream")


@app.get("/zoneplot/{zid}/mesh_info.json")
def zoneplot_mesh_info(zid: int):
    """Base (LOD 0) triangle count, without downloading the mesh -- lets the client pick a sane default LOD
    before it commits to fetching a potentially huge zone (e.g. zone 34 is ~4.7M tris / 44MB at Full)."""
    from workbench.devtools.spatial import zmesh as zmesh
    if not (ZONE_VISUAL_DIR / f"{zid}.obj").exists():
        import sqlite3
        from workbench.runtime import settings_store as settings
        from workbench.devtools.spatial import build_visual_cache as bz
        ffxi = settings.get_ffxi_install()
        if ffxi:
            con = sqlite3.connect(str(bz.DB_PATH))
            try:
                bz.build_one(con, zid, ffxi)
            finally:
                con.close()
    p = zmesh.convert(zid, lod=0)
    if not p:
        return JSONResponse({"ntris": 0, "nverts": 0})
    import struct
    b = p.read_bytes()
    nv, nt = struct.unpack_from("<II", b, 4)
    return JSONResponse({"ntris": nt, "nverts": nv, "bytes": p.stat().st_size})


@app.post("/zoneplot/{zid}/build_cache")
def zoneplot_build_cache(zid: int):
    """UI-triggered equivalent of `py -3 build_zone_visual_cache.py <zid>` -- builds the Legacy OBJ
    cache on demand so Zone Plot users never have to drop to a terminal for it. Captures build_one's
    own print() diagnostics (dat path missing, no geometry_rom_path, parse failure, etc.) so the
    button can surface the real reason instead of just a bare pass/fail."""
    import contextlib
    import io
    import sqlite3
    from workbench.devtools.spatial import build_visual_cache as bz
    ffxi = settings_mod.get_ffxi_install()
    if not ffxi:
        return JSONResponse({"ok": False, "log": "FFXI install path isn't configured -- set it on the Settings page first"}, status_code=400)
    buf = io.StringIO()
    con = sqlite3.connect(str(bz.DB_PATH))
    try:
        with contextlib.redirect_stdout(buf):
            ok = bz.build_one(con, zid, ffxi)
    finally:
        con.close()
    return JSONResponse({"ok": ok, "log": buf.getvalue().strip()})


@app.post("/zoneplot/edit")
async def zoneplot_edit(request: Request):
    from workbench.editors.zone import editor as zone_edit
    b = await request.json()
    try:
        return JSONResponse(zone_edit.update_position(b["k"], b["id"], b["x"], b["y"], b["z"], b.get("r", 0), b.get("comment", "")))
    except Exception as ex:
        return JSONResponse({"error": str(ex)}, status_code=400)


@app.get("/zoneplot/history/{kind}/{eid}")
async def zoneplot_entity_history(kind: str, eid: int, limit: int = 20):
    from workbench.editors.zone import editor as zone_edit
    try:
        return JSONResponse(zone_edit.entity_history(kind, eid, limit))
    except Exception as ex:
        return JSONResponse({"error": str(ex)}, status_code=400)


@app.post("/zoneplot/restore_entity_previous")
async def zoneplot_restore_entity_previous(request: Request):
    from workbench.editors.zone import editor as zone_edit
    b = await request.json()
    try:
        return JSONResponse(zone_edit.restore_entity_previous(b["k"], b["id"]))
    except Exception as ex:
        return JSONResponse({"error": str(ex)}, status_code=400)


@app.post("/zoneplot/edit_bulk")
async def zoneplot_edit_bulk(request: Request):
    from workbench.editors.zone import editor as zone_edit
    b = await request.json()
    try:
        return JSONResponse(zone_edit.update_positions_bulk(b["rows"], b.get("comment", "")))
    except Exception as ex:
        return JSONResponse({"error": str(ex)}, status_code=400)


@app.post("/zoneplot/animate")
async def zoneplot_animate(request: Request):
    from workbench.editors.zone import editor as zone_edit
    b = await request.json()
    try:
        return JSONResponse(zone_edit.update_animation(b["k"], b["id"], b["animation"], b["animationsub"], b.get("comment", "")))
    except Exception as ex:
        return JSONResponse({"error": str(ex)}, status_code=400)


@app.get("/zoneplot/animation-meta.json")
def zoneplot_animation_meta():
    from workbench.client.models import zone_animation_meta as zone_animation_meta
    try:
        return JSONResponse(zone_animation_meta.metadata())
    except Exception as ex:
        return JSONResponse({"error": str(ex)}, status_code=400)


@app.post("/zoneplot/model/preview")
async def zoneplot_model_preview(request: Request):
    from workbench.editors.zone import editor as zone_edit
    b = await request.json()
    try:
        return JSONResponse(zone_edit.preview_model_change(b["k"], b["id"], b["model_id"]))
    except Exception as ex:
        return JSONResponse({"error": str(ex)}, status_code=400)


@app.post("/zoneplot/model/apply")
async def zoneplot_model_apply(request: Request):
    from workbench.editors.zone import editor as zone_edit
    b = await request.json()
    try:
        return JSONResponse(zone_edit.apply_model_change(
            b["k"], b["id"], b["model_id"], b.get("comment", "")
        ))
    except Exception as ex:
        return JSONResponse({"error": str(ex)}, status_code=400)


@app.post("/zoneplot/model/sync_sql")
async def zoneplot_model_sync_sql(request: Request):
    from workbench.editors.zone import editor as zone_edit
    b = await request.json()
    try:
        return JSONResponse(zone_edit.sync_model_sql(b["k"], b["id"]))
    except Exception as ex:
        return JSONResponse({"error": str(ex)}, status_code=400)


@app.post("/zoneplot/delete")
async def zoneplot_delete(request: Request):
    from workbench.editors.zone import editor as zone_edit
    b = await request.json()
    try:
        return JSONResponse(zone_edit.delete_entity(b["k"], b["id"], b.get("comment", "")))
    except Exception as ex:
        return JSONResponse({"error": str(ex)}, status_code=400)


@app.get("/zoneplot/catalogue.json")
def zoneplot_catalogue(kind: str, q: str = "", zone: str = "", family: str = "", sort: str = "name"):
    from workbench.editors.zone import editor as zone_edit
    return JSONResponse(zone_edit.catalogue(kind, q, zone=zone, family=family, sort=sort))


@app.get("/zoneplot/{zid}/next_id.json")
def zoneplot_next_id(zid: int):
    from workbench.editors.zone import editor as zone_edit
    try:
        return JSONResponse(zone_edit.next_id_info(zid))
    except Exception as ex:
        return JSONResponse({"error": str(ex)}, status_code=400)


@app.get("/zoneplot/{eid}/drops.json")
def zoneplot_drops(eid: int):
    from workbench.editors.zone import editor as zone_edit
    try:
        return JSONResponse(zone_edit.get_drops(eid))
    except Exception as ex:
        return JSONResponse({"error": str(ex)}, status_code=400)


@app.post("/zoneplot/drops/dropid")
async def zoneplot_drops_dropid(request: Request):
    from workbench.editors.zone import editor as zone_edit
    b = await request.json()
    try:
        return JSONResponse(zone_edit.set_group_dropid(b["mobid"], b["dropid"], b.get("comment", "")))
    except Exception as ex:
        return JSONResponse({"error": str(ex)}, status_code=400)


@app.post("/zoneplot/drops/save")
async def zoneplot_drops_save(request: Request):
    from workbench.editors.zone import editor as zone_edit
    b = await request.json()
    try:
        return JSONResponse(zone_edit.save_drop_row(
            b["dropid"], b.get("drop_type", 0), b["group_id"], b["item_id"], b["group_rate"], b["item_rate"],
            b.get("orig_drop_type"), b.get("orig_group_id"), b.get("orig_item_id"), b.get("comment", "")))
    except Exception as ex:
        return JSONResponse({"error": str(ex)}, status_code=400)


@app.post("/zoneplot/drops/delete")
async def zoneplot_drops_delete(request: Request):
    from workbench.editors.zone import editor as zone_edit
    b = await request.json()
    try:
        return JSONResponse(zone_edit.delete_drop_row(b["dropid"], b.get("drop_type", 0), b["group_id"], b["item_id"], b.get("comment", "")))
    except Exception as ex:
        return JSONResponse({"error": str(ex)}, status_code=400)


@app.get("/zoneplot/items.json")
def zoneplot_items(q: str = ""):
    from workbench.editors.zone import editor as zone_edit
    return JSONResponse(zone_edit.item_catalogue(q))


@app.post("/zoneplot/add")
async def zoneplot_add(request: Request):
    from workbench.editors.zone import editor as zone_edit
    b = await request.json()
    try:
        return JSONResponse(zone_edit.add_entity(b["k"], b["zone"], b["src"], b["x"], b["y"], b["z"], b.get("r", 0), b.get("name", ""), b.get("comment", ""), b.get("instance", 0)))
    except Exception as ex:
        return JSONResponse({"error": str(ex)}, status_code=400)


@app.post("/zoneplot/sync_sql/entity")
async def zoneplot_sync_sql_entity(request: Request):
    from workbench.editors.zone import editor as zone_edit
    b = await request.json()
    try:
        return JSONResponse(zone_edit.sync_entity_sql(b["k"], b["id"]))
    except Exception as ex:
        return JSONResponse({"error": str(ex)}, status_code=400)


@app.post("/zoneplot/sync_sql/dropid")
async def zoneplot_sync_sql_dropid(request: Request):
    from workbench.editors.zone import editor as zone_edit
    b = await request.json()
    try:
        return JSONResponse(zone_edit.sync_group_dropid_sql(b["mobid"]))
    except Exception as ex:
        return JSONResponse({"error": str(ex)}, status_code=400)


@app.post("/zoneplot/sync_sql/drop_row")
async def zoneplot_sync_sql_drop_row(request: Request):
    from workbench.editors.zone import editor as zone_edit
    b = await request.json()
    try:
        return JSONResponse(zone_edit.sync_drop_row_sql(
            b["dropid"], b.get("drop_type", 0), b["group_id"], b["item_id"],
            b.get("orig_drop_type"), b.get("orig_group_id"), b.get("orig_item_id")))
    except Exception as ex:
        return JSONResponse({"error": str(ex)}, status_code=400)


@app.get("/zoneplot/backups.json")
def zoneplot_backups():
    from workbench.editors.zone import editor as zone_edit
    return JSONResponse(zone_edit.list_backups())


@app.post("/zoneplot/{zid}/snapshot")
def zoneplot_snapshot(zid: int, label: str = ""):
    from workbench.editors.zone import editor as zone_edit
    return JSONResponse({"id": zone_edit.snapshot_zone(zid, label)})


@app.post("/zoneplot/restore")
async def zoneplot_restore(request: Request):
    from workbench.editors.zone import editor as zone_edit
    b = await request.json()
    try:
        return JSONResponse(zone_edit.restore(b["id"], b.get("exact", False)))
    except Exception as ex:
        return JSONResponse({"error": str(ex)}, status_code=400)


@app.get("/zoneplot/{zid}/navmesh.bin")
def zoneplot_nav(zid: int):
    d = zone_plot.zone_data(zid)
    p = zone_plot.nav_path(d["zone"])
    if not p:
        return Response(b"", media_type="application/octet-stream")
    return Response(zone_plot.nav.nav_triangles_bytes(p), media_type="application/octet-stream")


@app.get("/zoneplot/{zid}/navmesh_meta.bin")
def zoneplot_nav_meta(zid: int):
    """Per-triangle (yMin, yMax, area, polyType) float32 quads, same triangle order as
    navmesh.bin, for the hover readout's Placement-Y / area-type display."""
    d = zone_plot.zone_data(zid)
    p = zone_plot.nav_path(d["zone"])
    if not p:
        return Response(b"", media_type="application/octet-stream")
    return Response(zone_plot.nav.nav_triangle_meta_bytes(p), media_type="application/octet-stream")


# ---- Item Editor (item_edit.py / item_dat_tools.py) ------------------------------------------
# Live search-and-edit GUI for all item classes across item_basic/item_equipment/item_weapon/
# item_usable/item_puppet/item_furnishing, plus the real client-DAT record the FFXI client
# independently enforces (level etc.) -- see item_edit.py's module docstring. Separate from the
# existing /items page, which is a read-only LSB<->external id-drift comparison tool.

# Import once at startup: the editor page fires several /itemedit/*.json requests at once, and
# the threadpool used to import item_edit concurrently on first load, so some threads saw the
# module half-initialised ("module 'item_edit' has no attribute 'mod_names'", HTTP 500).
try:
    from workbench.editors.items import editor as item_edit  # noqa: F401
except Exception as _ex:  # surfaced per-request instead of blocking startup
    print(f"WARNING: item_edit preload failed: {_ex}")


@app.get("/itemedit", response_class=HTMLResponse)
def itemedit_page(request: Request):
    return templates.TemplateResponse(request, "itemedit.html", {})


@app.get("/itemedit/search.json")
def itemedit_search(q: str = "", category: str = "", min_level: int = -1, max_level: int = -1,
                    job: int = -1, skill: int = -1, client_state: str = ""):
    from workbench.editors.items import editor as item_edit
    try:
        return JSONResponse(item_edit.search(q, category, min_level, max_level, job, skill, client_state))
    except Exception as ex:
        return JSONResponse({"error": str(ex)}, status_code=400)


@app.get("/itemedit/backups.json")
def itemedit_backups():
    from workbench.editors.items import editor as item_edit
    return JSONResponse(item_edit.list_backups())


@app.get("/itemedit/{item_id}/history.json")
def itemedit_history(item_id: int, limit: int = 100):
    from workbench.editors.items import editor as item_edit
    try:
        return JSONResponse(item_edit.list_item_history(item_id, limit))
    except Exception as ex:
        return JSONResponse({"error": str(ex)}, status_code=400)


@app.get("/itemedit/{item_id}/usage.json")
def itemedit_usage(item_id: int, source_limit: int = 100):
    from workbench.editors.items import editor as item_edit
    try:
        return JSONResponse(item_edit.item_usage(item_id, source_limit))
    except Exception as ex:
        return JSONResponse({"error": str(ex)}, status_code=400)


@app.post("/itemedit/batch/preview")
async def itemedit_batch_preview(request: Request):
    from workbench.editors.items import editor as item_edit
    try:
        body = await request.json()
        return JSONResponse(item_edit.preview_batch_edit(body.get("item_ids") or [], body.get("field"), body.get("value")))
    except Exception as ex:
        return JSONResponse({"error": str(ex)}, status_code=400)


@app.post("/itemedit/batch/apply")
async def itemedit_batch_apply(request: Request):
    from workbench.editors.items import editor as item_edit
    try:
        body = await request.json()
        return JSONResponse(item_edit.apply_batch_edit(
            body.get("item_ids") or [], body.get("field"), body.get("value"), body.get("comment") or ""
        ))
    except Exception as ex:
        return JSONResponse({"error": str(ex)}, status_code=400)


@app.post("/itemedit/batch/restore")
async def itemedit_batch_restore(request: Request):
    from workbench.editors.items import editor as item_edit
    try:
        body = await request.json()
        return JSONResponse(item_edit.restore_batch_backup(body.get("id"), body.get("comment") or ""))
    except Exception as ex:
        return JSONResponse({"error": str(ex)}, status_code=400)


@app.get("/itemedit/bitmasks.json")
def itemedit_bitmasks():
    from workbench.editors.items import editor as item_edit
    return JSONResponse(item_edit.bitmask_schema())


@app.get("/itemedit/modnames.json")
def itemedit_modnames():
    from workbench.editors.items import editor as item_edit
    return JSONResponse(item_edit.mod_names())


@app.get("/itemedit/modmeta.json")
def itemedit_modmeta():
    from workbench.editors.items import editor as item_edit
    return JSONResponse(item_edit.mod_metadata())


@app.get("/itemedit/pettypes.json")
def itemedit_pettypes():
    from workbench.editors.items import editor as item_edit
    return JSONResponse(item_edit.pet_type_names())


@app.get("/itemedit/latentnames.json")
def itemedit_latentnames():
    from workbench.editors.items import editor as item_edit
    return JSONResponse(item_edit.latent_names())


@app.get("/itemedit/latentmeta.json")
def itemedit_latentmeta():
    from workbench.editors.items import editor as item_edit
    return JSONResponse(item_edit.latent_metadata())


@app.get("/itemedit/special-cases.json")
def itemedit_special_cases(item_id: int = 0, name: str = ""):
    """Gear sets, food/use bonuses and server-code mentions for one item (read-only, parsed from the server tree)."""
    from workbench.devtools.spatial import zone_plot as zone_plot
    from workbench.editors.items import _special_cases
    try:
        root = zone_plot._server_root()
    except Exception:
        return JSONResponse({"item_id": item_id, "gear_sets": [], "effect_gain_mods": [], "code_references": []})
    return JSONResponse(_special_cases.special_cases(root, item_id, name))


@app.get("/itemedit/summary.json")
def itemedit_summary(item_id: int, compare: int = 0):
    """One unified 'what does this item do' summary (see workbench.editors.items.item_summary).
    compare=1 also attaches the LandSandBoat reference comparison."""
    from workbench.editors.items import item_summary, item_lsb_compare, editor as _ed
    try:
        s = item_summary.describe_item(item_id)
        s["lines"] = item_summary.summary_lines(s)
        if compare:
            s["lsb_compare"] = item_lsb_compare.compare_with_lsb(item_id, _ed.get_item(item_id))
        return s
    except ValueError as ex:
        return JSONResponse({"error": str(ex)}, status_code=404)


@app.get("/itemedit/script-health.json")
def itemedit_script_health():
    """Bulk item-script health: proc-flagged items (effect 431) and every item script file
    classified as behavior / check-only / stub, plus script files no item name maps to."""
    from workbench.editors.items import item_summary
    return item_summary.health_report()


@app.get("/itemhealth/report.json")
def itemhealth_report_json():
    from workbench.editors.items import item_proc_sync
    return item_proc_sync.build_report()


@app.get("/itemhealth/report.md")
def itemhealth_report_md():
    from fastapi.responses import PlainTextResponse
    from workbench.editors.items import item_proc_sync
    md = item_proc_sync.render_markdown(item_proc_sync.build_report())
    return PlainTextResponse(md, headers={"Content-Disposition": 'attachment; filename="item_script_health_report.md"'})


@app.get("/itemhealth/repair.json")
def itemhealth_repair(item_id: int = 0, apply: int = 0):
    """Preview (apply=0) or write (apply=1) a generated DSP onAdditionalEffect script for one item.
    Never overwrites a script that already has behavior; stubs are backed up first."""
    from workbench.editors.items import item_proc_sync
    try:
        return item_proc_sync.repair_item(item_id, apply=bool(apply))
    except Exception as ex:
        return JSONResponse({"ok": False, "error": str(ex)}, status_code=500)


@app.get("/itembrowser/facets.json")
def itembrowser_facets():
    from workbench.editors.items import item_browse
    try:
        return JSONResponse(item_browse.facets())
    except Exception as ex:
        return JSONResponse({"error": str(ex)}, status_code=400)


@app.get("/itembrowser/browse.json")
def itembrowser_browse(q: str = "", type: str = "", ah: int = -1, job: int = -1, slot: int = -1, skill: int = -1,
                       min_level: int = -1, max_level: int = -1, rare: int = 0, ex: int = 0, mod: int = -1,
                       ref: str = "", sort: str = "name", desc: int = 0, limit: int = 60, offset: int = 0):
    from workbench.editors.items import item_browse
    con = None
    try:
        try:
            con = get_con()  # reference catalogue lives in the toolkit's own SQLite DB; optional
        except Exception:
            con = None
        return JSONResponse(item_browse.browse(q, type, ah, job, slot, skill, min_level, max_level,
                                               bool(rare), bool(ex), mod, sort, bool(desc), limit, offset,
                                               ref=ref, ref_con=con))
    except Exception as ex_:
        return JSONResponse({"error": str(ex_)}, status_code=400)
    finally:
        if con is not None:
            con.close()


@app.get("/itembrowser/reference.json")
def itembrowser_reference(item_id: int, name: str = ""):
    """External-catalogue match (id agreement, description) and Topaz match for one item."""
    from workbench.editors.items import item_reference
    con = None
    try:
        con = get_con()
        if not name:
            from workbench.editors.items import item_browse
            r = item_browse.browse(str(item_id), limit=5)
            name = next((i["name"] for i in r["items"] if i["itemid"] == item_id), "")
        return JSONResponse(item_reference.reference(con, item_id, name, _external_item_by_id, backport_enabled()))
    except Exception as ex:
        return JSONResponse({"error": str(ex)}, status_code=400)
    finally:
        if con is not None:
            con.close()


@app.get("/itembrowser/reference-counts.json")
def itembrowser_reference_counts():
    from workbench.editors.items import item_reference, _db_alias
    con = None
    try:
        con = get_con()
        db = _db_alias.item_db(); cu = db.cursor(); cu.execute("select itemid, name from item_basic"); rows = cu.fetchall(); db.close()
        return JSONResponse(item_reference.counts(con, rows))
    except Exception as ex:
        return JSONResponse({"error": str(ex)}, status_code=400)
    finally:
        if con is not None:
            con.close()


@app.get("/itembrowser", response_class=HTMLResponse)
def itembrowser_page(request: Request):
    return templates.TemplateResponse(request, "itembrowser.html", {})


@app.get("/itemhealth", response_class=HTMLResponse)
def itemhealth_page(request: Request):
    return templates.TemplateResponse(request, "itemhealth.html", {})


@app.get("/itemedit/proc-script.json")
def itemedit_proc_script(item_id: int = 0, name: str = ""):
    """Where does this item's scripted proc live in the active server tree, and does the file exist?"""
    import re as _re
    from workbench.devtools.spatial import zone_plot as zone_plot
    internal = _re.sub(r"[^a-z0-9_]", "", (name or "").lower())
    out = {"item_id": item_id, "name": internal, "root": "", "candidates": []}
    try:
        root = zone_plot._server_root()
    except Exception:
        return JSONResponse(out)
    out["root"] = str(root)
    if not internal:
        return JSONResponse(out)
    for rel in (f"scripts/globals/items/{internal}.lua", f"scripts/items/{internal}.lua"):
        p = root / rel
        if p.is_file():
            try:
                txt = p.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                txt = ""
            hooks = sorted(set(_re.findall(r"function\s+(?:\w+[.:])?(on[A-Za-z]+)", txt)))
            out["candidates"].append({"path": rel, "exists": True, "has_additional_effect": "onAdditionalEffect" in txt,
                                      "hooks": hooks, "source": txt[:6000], "truncated": len(txt) > 6000})
    if not out["candidates"]:
        base = "scripts/items" if (root / "scripts/items").is_dir() and not (root / "scripts/globals/items").is_dir() else "scripts/globals/items"
        out["candidates"].append({"path": f"{base}/{internal}.lua", "exists": False, "has_additional_effect": False})
    return JSONResponse(out)


@app.get("/itemedit/dat-target.json")
def itemedit_dat_target_get():
    from workbench.editors.items import dat_tools as item_dat_tools
    return JSONResponse({
        "target": item_dat_tools.dat_target(),
        "pivot_root": str(item_dat_tools.pivot_root()),
    })


@app.post("/itemedit/dat-target.json")
async def itemedit_dat_target_set(request: Request):
    from workbench.editors.items import dat_tools as item_dat_tools
    b = await request.json()
    try:
        item_dat_tools.set_dat_target(b["target"])
        return JSONResponse({"target": item_dat_tools.dat_target(), "pivot_root": str(item_dat_tools.pivot_root())})
    except Exception as ex:
        return JSONResponse({"error": str(ex)}, status_code=400)


@app.get("/itemedit/client-layout-audit.json")
def itemedit_client_layout_audit():
    from workbench.editors.items import dat_tools as item_dat_tools
    return JSONResponse(item_dat_tools.item_record_layout_audit())


@app.get("/itemedit/{item_id}/client-record.json")
def itemedit_client_record(item_id: int):
    from workbench.editors.items import dat_tools as item_dat_tools
    try:
        return JSONResponse(item_dat_tools.client_record_inspector(item_id))
    except Exception as ex:
        return JSONResponse({"error": str(ex)}, status_code=400)


@app.get("/itemedit/{item_id}/icon.png")
def itemedit_icon(item_id: int):
    from workbench.editors.items import dat_tools as item_dat_tools
    try:
        png = item_dat_tools.item_icon_png(item_id)
        if not png:
            return Response(status_code=404)
        return Response(png, media_type="image/png", headers={"Cache-Control": "no-store"})
    except Exception as ex:
        return JSONResponse({"error": str(ex)}, status_code=400)


@app.get("/itemedit/{item_id}/live-pivot-diff.json")
def itemedit_live_pivot_diff(item_id: int):
    from workbench.editors.items import dat_tools as item_dat_tools
    try:
        return JSONResponse(item_dat_tools.compare_live_pivot_record(item_id))
    except Exception as ex:
        return JSONResponse({"error": str(ex)}, status_code=400)


@app.post("/itemedit/live-pivot-copy")
async def itemedit_live_pivot_copy(request: Request):
    from workbench.editors.items import dat_tools as item_dat_tools
    b = await request.json()
    try:
        return JSONResponse(item_dat_tools.copy_live_pivot_record(b["item_id"], b["direction"]))
    except Exception as ex:
        return JSONResponse({"error": str(ex)}, status_code=400)

@app.get("/itemedit/{item_id}/dat-pristine-diff.json")
def itemedit_dat_pristine_diff(item_id: int):
    from workbench.editors.items import dat_tools as item_dat_tools
    try:
        return JSONResponse(item_dat_tools.compare_client_record_to_pristine(item_id))
    except Exception as ex:
        return JSONResponse({"error": str(ex)}, status_code=400)

@app.get("/itemedit/dat-backups.json")
def itemedit_dat_backups():
    from workbench.editors.items import dat_tools as item_dat_tools
    return JSONResponse(item_dat_tools.list_dat_backups())


@app.post("/itemedit/dat-backups/restore")
async def itemedit_dat_backups_restore(request: Request):
    from workbench.editors.items import dat_tools as item_dat_tools
    b = await request.json()
    try:
        return JSONResponse(item_dat_tools.restore_dat_backup(b["dat_ui"], b.get("backup_id")))
    except Exception as ex:
        return JSONResponse({"error": str(ex)}, status_code=400)


@app.get("/itemedit/xi-pivot/manifest.json")
def itemedit_xi_pivot_manifest():
    from workbench.editors.items import dat_tools as item_dat_tools
    return JSONResponse(item_dat_tools.pivot_manifest())


@app.get("/itemedit/xi-pivot/export.zip")
def itemedit_xi_pivot_export():
    """Zips the current Xi-Pivot overlay folder (mirrors the ROM/x/y.DAT layout) for
    distribution -- drop the extracted "ROM" folder from this zip next to the game install per
    whatever DAT-overlay loader the user is pairing Xi-Pivot with; the real install is never
    touched to produce this."""
    from workbench.editors.items import dat_tools as item_dat_tools
    manifest = item_dat_tools.pivot_manifest()
    root = Path(manifest["root"])
    if not manifest["files"]:
        return JSONResponse({"error": "Xi-Pivot folder is empty -- no edits have been written to it yet"}, status_code=400)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in manifest["files"]:
            zf.write(root / f["rom_path"], arcname=f["rom_path"])
    buf.seek(0)
    return Response(buf.read(), media_type="application/zip",
                     headers={"Content-Disposition": 'attachment; filename="Xi-Pivot.zip"'})


@app.get("/itemedit/clone-template.json")
def itemedit_clone_template(item_id: int):
    from workbench.editors.items import editor as item_edit
    try:
        return JSONResponse(item_edit.clone_template(item_id))
    except Exception as ex:
        return JSONResponse({"error": str(ex)}, status_code=400)


@app.post("/itemedit/reconcile")
async def itemedit_reconcile(request: Request):
    from workbench.editors.items import editor as item_edit
    b = await request.json()
    try:
        return JSONResponse(item_edit.reconcile_item(
            b["item_id"], b["field"], b["direction"], b.get("comment", "")
        ))
    except Exception as ex:
        return JSONResponse({"error": str(ex)}, status_code=400)

@app.post("/itemedit/validate")
async def itemedit_validate(request: Request):
    from workbench.editors.items import editor as item_edit
    b = await request.json()
    try:
        return JSONResponse(item_edit.validate_item_changes(b["item_id"], b.get("tables", {}), b.get("effects")))
    except Exception as ex:
        return JSONResponse({"error": str(ex)}, status_code=400)

@app.post("/itemedit/save-atomic")
async def itemedit_save_atomic(request: Request):
    from workbench.editors.items import editor as item_edit
    b = await request.json()
    try:
        return JSONResponse(item_edit.save_item_atomic(
            b["item_id"], b.get("tables", {}), b.get("effects"), b.get("comment", "")
        ))
    except Exception as ex:
        return JSONResponse({"error": str(ex)}, status_code=400)

@app.post("/itemedit/update")
async def itemedit_update(request: Request):
    from workbench.editors.items import editor as item_edit
    b = await request.json()
    try:
        return JSONResponse(item_edit.update_item(b["item_id"], b["table"], b["fields"], b.get("comment", "")))
    except Exception as ex:
        return JSONResponse({"error": str(ex)}, status_code=400)


@app.get("/itemedit/slot-browser.json")
def itemedit_slot_browser(category: str, offset: int = 0, limit: int = 200, state: str = ""):
    from workbench.editors.items import dat_tools as item_dat_tools
    try:
        return JSONResponse(item_dat_tools.browse_slots(category, offset, limit, state))
    except Exception as ex:
        return JSONResponse({"error": str(ex)}, status_code=400)

@app.get("/itemedit/create-preview.json")
def itemedit_create_preview(category: str):
    from workbench.editors.items import dat_tools as item_dat_tools
    try:
        return JSONResponse(item_dat_tools.preview_free_slot(category))
    except Exception as ex:
        return JSONResponse({"error": str(ex)}, status_code=400)

# Must stay AFTER the static /itemedit/*.json routes above, or "{itemid}.json" (int) swallows them with a 422.
@app.get("/itemedit/{itemid}.json")
def itemedit_get(itemid: int):
    from workbench.editors.items import editor as item_edit
    try:
        return JSONResponse(item_edit.get_item(itemid))
    except Exception as ex:
        return JSONResponse({"error": str(ex)}, status_code=400)


@app.post("/itemedit/create")
async def itemedit_create(request: Request):
    from workbench.editors.items import editor as item_edit
    b = await request.json()
    try:
        return JSONResponse(item_edit.create_item(
            b["category"], b["item_type"], b["entry"], b.get("effects"), b.get("comment", "")
        ))
    except Exception as ex:
        return JSONResponse({"error": str(ex)}, status_code=400)


@app.post("/itemedit/delete")
async def itemedit_delete(request: Request):
    from workbench.editors.items import editor as item_edit
    b = await request.json()
    try:
        return JSONResponse(item_edit.delete_item(b["item_id"], b.get("comment", ""), bool(b.get("clear_dat", False))))
    except Exception as ex:
        return JSONResponse({"error": str(ex)}, status_code=400)


@app.post("/itemedit/restore-client-record")
async def itemedit_restore_client_record(request: Request):
    from workbench.editors.items import editor as item_edit
    b = await request.json()
    try:
        return JSONResponse(item_edit.restore_client_record_from_backup(
            b["id"], b.get("comment", "")
        ))
    except Exception as ex:
        return JSONResponse({"error": str(ex)}, status_code=400)

@app.post("/itemedit/restore")
async def itemedit_restore(request: Request):
    from workbench.editors.items import editor as item_edit
    b = await request.json()
    try:
        return JSONResponse(item_edit.restore(b["id"]))
    except Exception as ex:
        return JSONResponse({"error": str(ex)}, status_code=400)


@app.post("/itemedit/mods/set")
async def itemedit_mods_set(request: Request):
    from workbench.editors.items import editor as item_edit
    b = await request.json()
    try:
        return JSONResponse(item_edit.set_item_mod(b["item_id"], b["mod_id"], b["value"], b.get("comment", "")))
    except Exception as ex:
        return JSONResponse({"error": str(ex)}, status_code=400)


@app.post("/itemedit/mods/delete")
async def itemedit_mods_delete(request: Request):
    from workbench.editors.items import editor as item_edit
    b = await request.json()
    try:
        return JSONResponse(item_edit.delete_item_mod(b["item_id"], b["mod_id"], b.get("comment", "")))
    except Exception as ex:
        return JSONResponse({"error": str(ex)}, status_code=400)


@app.post("/itemedit/petmods/set")
async def itemedit_petmods_set(request: Request):
    from workbench.editors.items import editor as item_edit
    b = await request.json()
    try:
        return JSONResponse(item_edit.set_item_pet_mod(b["item_id"], b["mod_id"], b["pet_type"], b["value"], b.get("comment", "")))
    except Exception as ex:
        return JSONResponse({"error": str(ex)}, status_code=400)


@app.post("/itemedit/petmods/delete")
async def itemedit_petmods_delete(request: Request):
    from workbench.editors.items import editor as item_edit
    b = await request.json()
    try:
        return JSONResponse(item_edit.delete_item_pet_mod(b["item_id"], b["mod_id"], b["pet_type"], b.get("comment", "")))
    except Exception as ex:
        return JSONResponse({"error": str(ex)}, status_code=400)


@app.post("/itemedit/latents/add")
async def itemedit_latents_add(request: Request):
    from workbench.editors.items import editor as item_edit
    b = await request.json()
    try:
        return JSONResponse(item_edit.add_item_latent(b["item_id"], b["mod_id"], b["value"], b["latent_id"], b["latent_param"], b.get("comment", "")))
    except Exception as ex:
        return JSONResponse({"error": str(ex)}, status_code=400)


@app.post("/itemedit/latents/delete")
async def itemedit_latents_delete(request: Request):
    from workbench.editors.items import editor as item_edit
    b = await request.json()
    try:
        return JSONResponse(item_edit.delete_item_latent(b["item_id"], b["mod_id"], b["value"], b["latent_id"], b["latent_param"], b.get("comment", "")))
    except Exception as ex:
        return JSONResponse({"error": str(ex)}, status_code=400)


# ---- Model viewer (model_viewer.py) ----------------------------------------------------------
# Resolves an NPC/mob's real model DAT via mob_look_decode.py + model_schedule_dump.py's
# dat-extractor-backed FTABLE/VTABLE resolution, and serves the raw DAT bytes for gui/static/
# ffxi-dat/index.js (vendored from github.com/Soverance/Vanalytics, MIT license) to parse and
# render client-side with three.js. See gui/static/ffxi-dat/README.md for provenance.

@app.get("/modelviewer", response_class=HTMLResponse)
def modelviewer_page(request: Request):
    return templates.TemplateResponse(request, "model_viewer.html", {"request": request})


@app.get("/modelviewer/resolve.json")
def modelviewer_resolve(kind: str, id: int, server: str = None):
    from workbench.client.models import viewer as model_viewer
    try:
        return JSONResponse(model_viewer.resolve(kind, id, server))
    except Exception as ex:
        return JSONResponse({"error": str(ex)}, status_code=400)


@app.get("/modelviewer/model.json")
def modelviewer_model(model_id: int, server: str = None):
    from workbench.client.models import viewer as model_viewer
    try:
        return JSONResponse(model_viewer.resolve_model_id(model_id, server=server))
    except Exception as ex:
        return JSONResponse({"error": str(ex)}, status_code=400)


@app.get("/modelviewer/catalog.json")
def modelviewer_catalog(q: str = "", server: str = None, limit: int = 100, refresh: int = 0):
    from workbench.client.models import catalog as client_model_catalog
    try:
        return JSONResponse(client_model_catalog.search_catalog(
            q, server=server, limit=limit, refresh=bool(refresh)
        ))
    except Exception as ex:
        return JSONResponse({"error": str(ex)}, status_code=400)


@app.get("/modelviewer/catalog/correlate.json")
def modelviewer_catalog_correlate(
    model_id: int = None,
    file_id: int = None,
    rom_path: str = None,
    server: str = None,
):
    from workbench.client.models import catalog as client_model_catalog
    try:
        return JSONResponse({"rows": client_model_catalog.correlate(
            model_id=model_id, file_id=file_id, rom_path=rom_path, server=server
        )})
    except Exception as ex:
        return JSONResponse({"error": str(ex)}, status_code=400)


@app.get("/modelviewer/dat-info.json")
def modelviewer_dat_info(file_id: int = None, rom_path: str = None, server: str = None):
    from workbench.client.models import viewer as model_viewer
    try:
        return JSONResponse(model_viewer.resolve_dat(file_id=file_id, rom_path=rom_path, server=server))
    except Exception as ex:
        return JSONResponse({"error": str(ex)}, status_code=400)


@app.get("/modelviewer/dat")
def modelviewer_dat(ffxi_path: str, rom_path: str):
    from workbench.client.models import viewer as model_viewer
    try:
        data = model_viewer.read_dat_bytes(ffxi_path, rom_path)
        return Response(data, media_type="application/octet-stream")
    except Exception as ex:
        return JSONResponse({"error": str(ex)}, status_code=400)


@app.get("/datinspector", response_class=HTMLResponse)
def datinspector_page(
    request: Request,
    dat_id: str = "",
    zoneid: str = "",
    family: str = "",
    dat_path: str = "",
    ffxi_path: str = "",
):
    from workbench.client.dat import inspector as dat_inspector

    path = ffxi_path or (settings_mod.get_ffxi_install() or "C:/ValhallaXI/SquareEnix/FINAL FANTASY XI")
    result, error = None, None
    selected_mode = ""
    resolved_dat_id = None
    try:
        if dat_path.strip():
            selected_mode = "path"
            result = dat_inspector.inspect_path(path, dat_path.strip())
        elif zoneid.strip() or family.strip():
            selected_mode = "zone"
            if not zoneid.strip() or not family.strip():
                raise ValueError("Select both a zone and a DAT family.")
            resolved_dat_id = dat_inspector.dat_id_for_zone_family(int(zoneid), family)
            result = dat_inspector.inspect(path, resolved_dat_id)
        elif dat_id.strip():
            selected_mode = "id"
            resolved_dat_id = int(dat_id)
            result = dat_inspector.inspect(path, resolved_dat_id)
    except Exception as ex:
        error = f"{type(ex).__name__}: {ex}"

    families = [
        {
            "name": name,
            "label": dat_inspector.FAMILY_LABELS.get(name, name),
            "base": base,
        }
        for name, base in dat_inspector.FAMILIES
    ]
    zones = []
    try:
        if DB_PATH.is_file():
            con = sqlite3.connect(DB_PATH)
            try:
                zones = [
                    {"zoneid": int(row[0]), "name": row[1] or f"Zone {row[0]}"}
                    for row in con.execute(
                        "SELECT zoneid,name FROM zones WHERE zoneid BETWEEN 0 AND 255 ORDER BY zoneid"
                    ).fetchall()
                ]
            finally:
                con.close()
    except sqlite3.Error:
        zones = []

    if result:
        zone_name = None
        if result.get("zone_id") is not None:
            match = next((z for z in zones if z["zoneid"] == result["zone_id"]), None)
            zone_name = match["name"] if match else None
        result["zone_name"] = zone_name

        actions = []
        kinds = {m.get("tool_kind") for m in result.get("matches", [])}
        if "events" in kinds:
            href = f"/events?zone={quote(zone_name)}" if zone_name else "/events"
            actions.append({
                "label": "Open Events / CSID",
                "href": href,
                "note": "Browse/decompile the event records from this zone.",
                "primary": True,
            })
        if "dialog" in kinds:
            href = f"/dialog?zone={quote(zone_name)}" if zone_name else "/dialog"
            actions.append({
                "label": "Open Dialog Browser",
                "href": href,
                "note": "Search the decoded message/string table.",
                "primary": True,
            })
        if "entities" in kinds:
            actions.append({
                "label": "Open Entity Search",
                "href": "/entity",
                "note": "Resolve client entity names against indexed NPC/entity data.",
                "primary": True,
            })
        if result.get("zone_id") is not None:
            actions.append({
                "label": "Open Zone Editor",
                "href": "/zoneplot",
                "note": f"Zone-aware follow-up for zone {result['zone_id']}"
                        + (f" ({zone_name})" if zone_name else "") + ".",
                "primary": False,
            })

        # The Model Viewer has its own direct-DAT input. Keep this available especially when no
        # structured parser recognizes the file; that is a common outcome for model/texture DATs.
        actions.append({
            "label": "Open Model Viewer",
            "href": "/modelviewer",
            "note": f"Try direct DAT / file-ID correlation using {result.get('rom_relative') or result.get('filename')}.",
            "primary": not bool(result.get("matches")),
        })
        actions.append({
            "label": "Client Overview / ID Drift",
            "href": "/clientoverview",
            "note": "Compare this client/build against another snapshot.",
            "primary": False,
        })
        result["actions"] = actions

    return templates.TemplateResponse(request, "dat_inspector.html", {
        "request": request,
        "result": result,
        "error": error,
        "dat_id": dat_id,
        "zoneid": zoneid,
        "family": family,
        "dat_path": dat_path,
        "resolved_dat_id": resolved_dat_id,
        "selected_mode": selected_mode,
        "ffxi_path": path,
        "families": families,
        "zones": zones,
    })


def _clientoverview_context(
    request: Request,
    *,
    import_result: dict | None = None,
    import_error: str | None = None,
    comparison: dict | None = None,
    compare_error: str | None = None,
    import_form: dict | None = None,
    compare_form: dict | None = None,
):
    from workbench.client.snapshots import overview as client_overview
    from workbench.client import identity_gui

    install = settings_mod.get_ffxi_install() or "C:/ValhallaXI/SquareEnix/FINAL FANTASY XI"
    ov, error = None, None
    try:
        ov = client_overview.overview(install, WORKBENCH_DB)
    except Exception as ex:
        error = f"{type(ex).__name__}: {ex}"

    snapshots = identity_gui.list_client_snapshots(
        WORKBENCH_DB,
        current_snapshot_id=(ov or {}).get("snapshot_id"),
        current_client_path=(ov or {}).get("install") or install,
    )
    comparison_summary = (
        identity_gui.summarize_comparison(comparison) if comparison is not None else None
    )
    entity_summary = (
        identity_gui.summarize_entity_diagnostics(comparison.get("entity_diagnostics"))
        if comparison is not None else None
    )
    return {
        "request": request,
        "ov": ov,
        "error": error,
        "snapshots": snapshots,
        "import_result": import_result,
        "import_error": import_error,
        "comparison": comparison,
        "comparison_summary": comparison_summary,
        "entity_summary": entity_summary,
        "compare_error": compare_error,
        "import_form": import_form or {
            "client_root": install,
            "snapshot_id": "",
            "build_label": "",
            "region": "",
            "language": "",
        },
        "compare_form": compare_form or {
            "source_snapshot": "",
            "target_snapshot": "",
            "zone": "",
            "minimum_confidence": "HIGH",
        },
    }


@app.get("/clientoverview", response_class=HTMLResponse)
def clientoverview_page(request: Request):
    return templates.TemplateResponse(
        request,
        "client_overview.html",
        _clientoverview_context(request),
    )


@app.post("/clientoverview/import", response_class=HTMLResponse)
def clientoverview_import(
    request: Request,
    client_root: str = Form(...),
    snapshot_id: str = Form(...),
    build_label: str = Form(...),
    region: str = Form(""),
    language: str = Form(""),
):
    from workbench.client import identity_gui

    form = {
        "client_root": client_root,
        "snapshot_id": snapshot_id,
        "build_label": build_label,
        "region": region,
        "language": language,
    }
    try:
        result = identity_gui.import_client_snapshot(
            client_root=Path(client_root),
            snapshot_id=snapshot_id,
            build_label=build_label,
            region=region,
            language=language,
            xi_tinkerer=XI_TINKERER_CLI,
            db_path=WORKBENCH_DB,
            zone_db=DB_PATH,
            snapshots_root=TOOLS_ROOT / "client_snapshots",
        )
        ctx = _clientoverview_context(request, import_result=result)
    except Exception as ex:
        ctx = _clientoverview_context(
            request,
            import_error=f"{type(ex).__name__}: {ex}",
            import_form=form,
        )
    return templates.TemplateResponse(request, "client_overview.html", ctx)


@app.post("/clientoverview/compare", response_class=HTMLResponse)
def clientoverview_compare(
    request: Request,
    source_snapshot: str = Form(...),
    target_snapshot: str = Form(...),
    zone: str = Form(""),
    minimum_confidence: str = Form("HIGH"),
):
    from workbench.client import identity_gui

    form = {
        "source_snapshot": source_snapshot,
        "target_snapshot": target_snapshot,
        "zone": zone,
        "minimum_confidence": minimum_confidence,
    }
    try:
        comparison = identity_gui.compare_client_snapshots(
            WORKBENCH_DB,
            source_snapshot_id=source_snapshot,
            target_snapshot_id=target_snapshot,
            zone_key=zone,
            minimum_confidence=minimum_confidence,
        )
        ctx = _clientoverview_context(
            request,
            comparison=comparison,
            compare_form=form,
        )
    except Exception as ex:
        ctx = _clientoverview_context(
            request,
            compare_error=f"{type(ex).__name__}: {ex}",
            compare_form=form,
        )
    return templates.TemplateResponse(request, "client_overview.html", ctx)


@app.get("/clientoverview/compare.csv")
def clientoverview_compare_csv(
    source_snapshot: str,
    target_snapshot: str,
    zone: str = "",
    minimum_confidence: str = "HIGH",
):
    from workbench.client import identity_gui

    try:
        report = identity_gui.compare_client_snapshots(
            WORKBENCH_DB,
            source_snapshot_id=source_snapshot,
            target_snapshot_id=target_snapshot,
            zone_key=zone,
            minimum_confidence=minimum_confidence,
        )
    except Exception as ex:
        raise HTTPException(status_code=400, detail=f"{type(ex).__name__}: {ex}") from ex

    fields = [
        "zone_key",
        "source_actor_key",
        "source_event_id",
        "target_actor_key",
        "actor_status",
        "actor_confidence",
        "actor_semantic_identity",
        "actor_candidate_count",
        "actor_reason",
        "actor_recommendation",
        "target_event_id",
        "status",
        "confidence",
        "match_basis",
        "source_record_id",
        "target_record_id",
        "reason",
    ]
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(report["rows"])
    filename = (
        f"client-event-compare-{identity_gui.safe_snapshot_name(source_snapshot)}-"
        f"to-{identity_gui.safe_snapshot_name(target_snapshot)}.csv"
    )
    return Response(
        out.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/dialogdrift", response_class=HTMLResponse)
def dialogdrift_page(request: Request):
    from workbench.devtools.reference.dialog import drift_overview as ddo
    rows, error, checked = [], None, None
    try:
        rows = ddo.overview(DB_PATH)
        con = sqlite3.connect(f"file:{DB_PATH.as_posix()}?mode=ro", uri=True)
        checked = con.execute("SELECT MAX(checked_at) FROM dialog_drift_report").fetchone()[0]
        con.close()
    except Exception as ex:
        error = f"{type(ex).__name__}: {ex}"
    return templates.TemplateResponse(request, "dialog_drift.html", {
        "request": request, "rows": rows, "summary": ddo.summary(rows), "checked": checked, "error": error})


@app.get("/research", response_class=HTMLResponse)
def research_sessions_page(request: Request, created: str = ""):
    from workbench.research.session import ResearchSessionStore

    store = ResearchSessionStore(WORKBENCH_DB)
    sessions = store.list(limit=200)
    return templates.TemplateResponse(request, "research_sessions.html", {
        "request": request,
        "sessions": sessions,
        "created": created,
        "permission_profiles": (
            "READ_ONLY_RESEARCH",
            "PROPOSE_CHANGES",
            "VALIDATION_ORCHESTRATOR",
        ),
    })


@app.post("/research", response_class=HTMLResponse)
def research_sessions_create(
    request: Request,
    question: str = Form(...),
    provider: str = Form(...),
    model: str = Form(...),
    permission_profile: str = Form("READ_ONLY_RESEARCH"),
    source_snapshot_id: str = Form(""),
    target_snapshot_id: str = Form(""),
    feature_root: str = Form(""),
    entity_root: str = Form(""),
    max_tool_calls: int = Form(8),
):
    from workbench.research.session import ResearchSessionStore

    question = question.strip()
    provider = provider.strip()
    model = model.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Research question is required.")
    if not provider:
        raise HTTPException(status_code=400, detail="Provider is required.")
    if not model:
        raise HTTPException(status_code=400, detail="Model is required.")
    if max_tool_calls < 0 or max_tool_calls > 100:
        raise HTTPException(status_code=400, detail="Max tool calls must be between 0 and 100.")

    store = ResearchSessionStore(WORKBENCH_DB)
    try:
        session = store.create(
            question=question,
            provider=provider,
            model=model,
            permission_profile=permission_profile,
            source_snapshot_id=source_snapshot_id.strip() or None,
            target_snapshot_id=target_snapshot_id.strip() or None,
            feature_root=feature_root.strip() or None,
            entity_root=entity_root.strip() or None,
            budgets={"max_tool_calls": int(max_tool_calls)},
            replay_metadata={"created_from": "gui:/research"},
        )
    except ValueError as ex:
        raise HTTPException(status_code=400, detail=str(ex)) from ex
    return RedirectResponse(
        f"/research/{quote(session.research_session_id)}?created=1",
        status_code=303,
    )


@app.get("/research/contradictions", response_class=HTMLResponse)
def research_contradictions_page(
    request: Request,
    session_id: str = "",
    subject_id: str = "",
    evidence_type: str = "",
):
    from workbench.research.evidence_browser import list_contradictions

    report=list_contradictions(
        WORKBENCH_DB,
        research_session_id=session_id.strip() or None,
        subject_id=subject_id.strip() or None,
        evidence_type=evidence_type.strip() or None,
    )
    return templates.TemplateResponse(request,"research_contradictions.html",{
        "request":request,
        "report":report,
        "session_id":session_id,
        "subject_id":subject_id,
        "evidence_type":evidence_type,
    })


@app.get("/research/evidence", response_class=HTMLResponse)
def research_evidence_page(request: Request, evidence_id: str):
    from workbench.research.evidence_browser import evidence_record

    evidence=evidence_record(WORKBENCH_DB,evidence_id)
    if evidence is None:
        raise HTTPException(status_code=404,detail=f"No canonical evidence '{evidence_id}'")
    return templates.TemplateResponse(request,"research_evidence.html",{
        "request":request,
        "evidence":evidence,
    })


@app.get("/research/{research_session_id:path}", response_class=HTMLResponse)
def research_session_detail_page(
    request: Request,
    research_session_id: str,
    created: str = "",
    run_status: str = "",
    run_error: str = "",
    replayed_from: str = "",
):
    from workbench.research.session import ResearchSessionStore

    store = ResearchSessionStore(WORKBENCH_DB)
    session = store.get(research_session_id)
    if session is None:
        raise HTTPException(status_code=404, detail=f"No research session '{research_session_id}'")
    run_controls = dict((session.get("replay_metadata") or {}).get("run_controls") or {})
    return templates.TemplateResponse(request, "research_session_detail.html", {
        "request": request,
        "session": session,
        "created": created,
        "run_status": run_status,
        "run_error": run_error,
        "replayed_from": replayed_from,
        "run_defaults": {
            "provider": session["provider"],
            "model": session["model"],
            "max_tool_calls": int((session.get("budgets") or {}).get("max_tool_calls", 8)),
            "max_provider_calls": int(run_controls.get("max_provider_calls", 12)),
            "timeout": float(run_controls.get("timeout", 120.0)),
            "temperature": float(run_controls.get("temperature", 0.1)),
            "provider_base_url": run_controls.get("provider_base_url") or "",
        },
        "has_run": bool(session.get("tool_calls") or session.get("final_report")),
    })


def _research_execute_from_form(
    research_session_id: str,
    *,
    provider: str,
    model: str,
    max_tool_calls: int,
    max_provider_calls: int,
    timeout: float,
    temperature: float,
    provider_base_url: str,
    replay: bool,
):
    from workbench.research.runtime import execute_session

    base_url = provider_base_url.strip() or None
    if base_url is None and provider.strip().lower().replace("_", "-") in {"openwebui", "open-webui"}:
        con = get_con()
        try:
            values = settings_mod.get_all(con)
        finally:
            con.close()
        base_url = values.get("llm_base_url") or None

    return execute_session(
        WORKBENCH_DB,
        research_session_id,
        provider_id=provider,
        model=model,
        max_tool_calls=max_tool_calls,
        max_provider_calls=max_provider_calls,
        timeout=timeout,
        temperature=temperature,
        provider_base_url=base_url,
        replay=replay,
    )


@app.post("/research/run")
def research_session_run(
    research_session_id: str = Form(...),
    provider: str = Form(...),
    model: str = Form(...),
    max_tool_calls: int = Form(8),
    max_provider_calls: int = Form(12),
    timeout: float = Form(120.0),
    temperature: float = Form(0.1),
    provider_base_url: str = Form(""),
):
    try:
        result = _research_execute_from_form(
            research_session_id,
            provider=provider,
            model=model,
            max_tool_calls=max_tool_calls,
            max_provider_calls=max_provider_calls,
            timeout=timeout,
            temperature=temperature,
            provider_base_url=provider_base_url,
            replay=False,
        )
        note = f"{result['verification_state']}: {result['provider_calls']} provider call(s), {result['tool_calls']} tool call(s)"
        return RedirectResponse(
            f"/research/{quote(result['research_session_id'])}?run_status={quote(note)}",
            status_code=303,
        )
    except Exception as ex:
        return RedirectResponse(
            f"/research/{quote(research_session_id)}?run_error={quote(f'{type(ex).__name__}: {ex}')}",
            status_code=303,
        )


@app.post("/research/replay")
def research_session_replay(
    research_session_id: str = Form(...),
    provider: str = Form(...),
    model: str = Form(...),
    max_tool_calls: int = Form(8),
    max_provider_calls: int = Form(12),
    timeout: float = Form(120.0),
    temperature: float = Form(0.1),
    provider_base_url: str = Form(""),
):
    try:
        result = _research_execute_from_form(
            research_session_id,
            provider=provider,
            model=model,
            max_tool_calls=max_tool_calls,
            max_provider_calls=max_provider_calls,
            timeout=timeout,
            temperature=temperature,
            provider_base_url=provider_base_url,
            replay=True,
        )
        note = f"{result['verification_state']}: {result['provider_calls']} provider call(s), {result['tool_calls']} tool call(s)"
        return RedirectResponse(
            f"/research/{quote(result['research_session_id'])}?run_status={quote(note)}&replayed_from={quote(research_session_id)}",
            status_code=303,
        )
    except Exception as ex:
        return RedirectResponse(
            f"/research/{quote(research_session_id)}?run_error={quote(f'{type(ex).__name__}: {ex}')}",
            status_code=303,
        )


@app.get("/researchgaps", response_class=HTMLResponse)
def researchgaps_page(request: Request):
    from workbench.devtools.research import gaps as research_gaps
    res = None
    if _workbench_graph_connection() is not None:
        res = research_gaps.detect(WORKBENCH_DB)
    return templates.TemplateResponse(request, "research_gaps.html", {"request": request, "res": res})


def _domain_roots():
    from workbench.devtools.indexing import build_lsb_index
    return {"topaz": settings_mod.get_topaz_root(), "dsp": settings_mod.get_dsp_root(), "lsb": build_lsb_index.LSB_ROOT}


@app.get("/domains", response_class=HTMLResponse)
def domains_index_page(request: Request):
    from workbench.domains import service as dsvc
    roots, defs, rows = _domain_roots(), dsvc.load(), []
    for key, d in defs.items():
        res = dsvc.resolve(d, roots)
        rows.append({"key": key, "label": d["label"], "archetype": d["archetype"],
                     "wiki_pages": sum(dsvc.wiki_counts(d["wiki"]["categories"]).values()),
                     "status": dsvc.domain_status(d, res), "total": len(res), "editors": sum(1 for e in res if e["edit"])})
    return templates.TemplateResponse(request, "domains_index.html", {"request": request, "rows": rows, "roots": list(roots)})


@app.get("/domains/voidwatch/tracker.json")
def voidwatch_tracker_json():
    f = REPO_ROOT / "data" / "voidwatch" / "nm_tracker.json"
    if not f.exists():
        raise HTTPException(status_code=404, detail="data/voidwatch/nm_tracker.json missing")
    return Response(f.read_text(encoding="utf-8"), media_type="application/json")


@app.get("/domains/{key}", response_class=HTMLResponse)
def domain_detail_page(request: Request, key: str):
    from workbench.domains import service as dsvc
    defs = dsvc.load()
    if key not in defs:
        raise HTTPException(status_code=404, detail=f"No domain '{key}'")
    d, roots = defs[key], _domain_roots()
    return templates.TemplateResponse(request, "domain_detail.html", {
        "request": request, "d": d, "roots": list(roots), "ents": dsvc.resolve(d, roots),
        "wiki": dsvc.wiki_counts(d["wiki"]["categories"]), "slug": dsvc.slug})


@app.post("/binaryinspector/save-probes", response_class=HTMLResponse)
def binaryinspector_save_probes(request: Request, run_set: str = Form(...)):
    from workbench.client.binary import inspector as bi
    install = settings_mod.get_ffxi_install() or "C:/ValhallaXI/SquareEnix/FINAL FANTASY XI"
    probe_con = _workbench_graph_connection()
    if probe_con is None:
        note = "Workbench graph (workbench.db) is not built yet; nothing saved. Build/import it first."
        return RedirectResponse(f"/binaryinspector?run_set={run_set}&saved={quote(note)}", status_code=303)
    probe_con.close()
    try:
        r = bi.save_probe_set(run_set, install, WORKBENCH_DB)
        note = f"Saved {r['saved']} observations to {r['db']}."
    except Exception as ex:
        note = f"Save failed: {type(ex).__name__}: {ex}"
    return RedirectResponse(f"/binaryinspector?run_set={run_set}&saved={quote(note)}", status_code=303)


@app.get("/binaryinspector", response_class=HTMLResponse)
def binaryinspector_page(request: Request, path: str = "", q: str = "", imp: str = "", pattern: str = "",
                         exec_only: str = "", diff_path: str = "", run_set: str = "", saved: str = "",
                         scan_mem: str = ""):
    from workbench.client.binary import inspector as bi
    install = settings_mod.get_ffxi_install() or "C:/ValhallaXI/SquareEnix/FINAL FANTASY XI"
    ctx = {"request": request, "install": install, "candidates": bi.list_candidates(install),
           "path": path, "q": q, "imp": imp, "pattern": pattern, "exec_only": exec_only,
           "diff_path": diff_path, "idx": None, "error": None, "strings": None,
           "imports": None, "psearch": None, "diff": None,
           "probe_sets": bi.list_probe_sets(), "probe_result": None, "saved": saved, "run_set_file": run_set, "mem_scan": None}
    try:
        if scan_mem:
            ctx["mem_scan"] = bi.scan_running_client_version()
        if run_set:
            ctx["probe_result"] = bi.run_probe_set(run_set, install)
        if path.strip():
            idx = bi.get_index(path.strip())
            ctx["idx"] = idx
            ctx["imports"] = bi.imports_by_dll(idx, imp)
            if q.strip():
                ctx["strings"] = bi.search_strings(idx, q.strip())
            if pattern.strip():
                ctx["psearch"] = bi.pattern_search(path.strip(), pattern.strip(), bool(exec_only))
            if diff_path.strip():
                ctx["diff"] = bi.diff(path.strip(), diff_path.strip())
    except Exception as ex:
        ctx["error"] = f"{type(ex).__name__}: {ex}"
    return templates.TemplateResponse(request, "binary_inspector.html", ctx)


if __name__ == "__main__":
    import uvicorn
    _con = get_con()
    _port = int(settings_mod.get(_con, "port") or settings_mod.DEFAULTS["port"])
    _con.close()
    uvicorn.run("workbench.app.host:app", host="127.0.0.1", port=_port, reload=False)
