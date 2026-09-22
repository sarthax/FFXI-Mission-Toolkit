#!/usr/bin/env python3
"""
build_capture_index.py -- ingest real Assault capture bundles into the consolidated database so
the GUI/CLI can query and cross-reference them instead of re-reading raw folders/zips by hand.

Supports two real capture-tool formats, auto-detected per bundle (never mixed within one):
  - The "Thris Nov2025" set (36 zips, one per Assault mission, six zones) -- a Captain v1.6.1
    addon suite that's strictly richer than everything else: real per-entity SQLite databases
    (NPCLogger, ActionView), per-NPC path CSVs (PathLog), HP/KI/attack-delay logs, and the
    packet/dialogue logs already consumed elsewhere. Detected by NPCLogger/<Zone>.db presence.
  - The older idview/Wiggo-era format (used by every Nyzul Isle capture on disk, none of which
    have the newer SQLite logger) -- Npclogger/tables/<Zone>.lua, a raw append-log of entity-
    update packet snapshots with no timestamps, history, actions, or HP data, just position
    samples in file order. Thinner, but real -- ingest_npclogger_lua() parses it directly rather
    than skipping these captures. Only used when no NPCLogger/<Zone>.db exists in the bundle.

Ingest sources, either a folder or a .zip (zip is read in-memory, nothing is extracted to disk):
  captures            -- one row per ingested bundle (manifest info when available: capturer,
                          addon list, client build, start time, source path) -- the provenance
                          anchor every other table's capture_id points back to.
  capture_npc_entries -- one row per real entity seen in the capture (id, name, model_id, x/y/z,
                          hp%, flags where the format has them) -- current/last-known-state
                          snapshot. Sourced from NPCLogger.db's `entries` table, or (older format)
                          the last-seen values for that id in the Lua append-log.
  capture_npc_history -- NPCLogger.db's `history` table verbatim, when present -- a real
                          per-entity time series of state deltas with timestamps: spawn/despawn
                          timing, position over time, HP over time, all in one place. Not present
                          for older-format captures (no such data exists in that format).
  capture_npc_path    -- a real per-NPC position trace, either PathLog's purpose-built CSVs
                          (leg,x,y,z,dir,delta) for the newer format, or every raw line for that
                          id in the older format's Lua append-log (no timestamps, but real
                          file-order position samples).
  capture_actions     -- ActionView's Actions.db `entries` table (newer format only) -- real
                          ability/weaponskill/spell usage per actor with animation/message ids.
  capture_hp_events   -- HPTrack's "Defeated X: lo~hi HP" lines (newer format only) -- real
                          observed HP ranges, useful for validating sql_mob_pools.

Every ingested entity is also cross-referenced into entity_profile.py's field_sources table
under confidence tier "capture" (see entity_profile.CONFIDENCE) so Entity Lookup surfaces
capture-observed position/model/HP alongside SQL/wiki/dat facts, with the source visibly labeled
-- never silently merged into a single "truth".

Usage:
    py -3 build_capture_index.py ingest "<path to a capture folder or .zip>"
    py -3 build_capture_index.py ingest-all "<path to a directory of capture zips>" [--pattern "*.zip"]
    py -3 build_capture_index.py list
    py -3 build_capture_index.py show <capture_id>
"""
import argparse
import io
import json
import re
import shutil
import sqlite3
import sys
import tempfile
import time
import zipfile
from pathlib import Path

import entity_profile

TOOLS_ROOT = Path(__file__).parent
DB_PATH = TOOLS_ROOT / "ffxi_zone_database.db"

# 2026-09-04: real content-category taxonomy (user-specified, matches BG Wiki's own category
# naming conventions -- e.g. "Events - Holiday", "Events - Temporary" are real wiki category
# names, not invented here). Stored in capture_tags as a many-to-many (a capture can be both
# "Notorious Monsters" and "Battlefields" at once, unlike the older single-value content_type
# column, kept as-is for backward compat with existing assault/unclassified rows). Sorted
# alphabetically ascending (user's explicit preference, 2026-09-04) -- keep this order when
# adding/removing entries rather than appending to the end.
CAPTURE_TAGS = [
    "Abyssea", "Assault", "Battle", "Battle Systems", "Battlefields", "Combat", "Conflict", "Escha",
    "Events", "Events - Holiday", "Events - Temporary", "Hobbies", "Missions", "NPC",
    "Notorious Monsters", "Quests", "Records of Eminence", "Research", "Salvage", "Shop",
    "Trust", "Uncategorized",
]


def init_db(con: sqlite3.Connection):
    con.executescript("""
        CREATE TABLE IF NOT EXISTS captures (
            capture_id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_path TEXT UNIQUE,
            capturer TEXT,
            capture_label TEXT,
            content_type TEXT,
            zones TEXT,
            mission_name TEXT,
            addons TEXT,
            client_build TEXT,
            is_retail INTEGER,
            start_time INTEGER,
            ingested_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS capture_npc_entries (
            capture_id INTEGER, zone_db TEXT, entity_id INTEGER, name TEXT, model_id INTEGER,
            x REAL, y REAL, z REAL, dir INTEGER, hpp INTEGER,
            legacy_flags INTEGER, legacy_status INTEGER, legacy_animation INTEGER,
            speed INTEGER, created_at INTEGER, updated_at INTEGER,
            PRIMARY KEY (capture_id, zone_db, entity_id)
        );
        CREATE INDEX IF NOT EXISTS idx_cne_entity ON capture_npc_entries(entity_id);
        CREATE TABLE IF NOT EXISTS capture_npc_history (
            capture_id INTEGER, zone_db TEXT, entity_id INTEGER, seq INTEGER,
            ts INTEGER, delta_json TEXT,
            PRIMARY KEY (capture_id, zone_db, entity_id, seq)
        );
        CREATE INDEX IF NOT EXISTS idx_cnh_entity ON capture_npc_history(entity_id);
        CREATE TABLE IF NOT EXISTS capture_npc_path (
            capture_id INTEGER, zone_db TEXT, entity_id INTEGER, leg INTEGER, step INTEGER,
            x REAL, y REAL, z REAL, dir INTEGER, delta INTEGER,
            PRIMARY KEY (capture_id, zone_db, entity_id, step)
        );
        CREATE INDEX IF NOT EXISTS idx_cnp_entity ON capture_npc_path(entity_id);
        CREATE TABLE IF NOT EXISTS capture_actions (
            capture_id INTEGER, action_key TEXT, actor INTEGER, actor_name TEXT,
            action_type TEXT, animation INTEGER, category INTEGER, message INTEGER, name TEXT,
            ts INTEGER,
            PRIMARY KEY (capture_id, action_key)
        );
        CREATE INDEX IF NOT EXISTS idx_ca_actor ON capture_actions(actor);
        CREATE TABLE IF NOT EXISTS capture_hp_events (
            capture_id INTEGER, seq INTEGER, mob_name TEXT, hp_low INTEGER, hp_high INTEGER,
            PRIMARY KEY (capture_id, seq)
        );
        CREATE TABLE IF NOT EXISTS capture_events (
            capture_id INTEGER, zone_db TEXT, seq INTEGER, direction TEXT,
            opcode TEXT, opcode_name TEXT, entity_id INTEGER, entity_name TEXT,
            event_hex TEXT, option INTEGER, message_id INTEGER, params_raw TEXT,
            PRIMARY KEY (capture_id, zone_db, seq)
        );
        CREATE INDEX IF NOT EXISTS idx_capture_events_entity ON capture_events(entity_id);
        CREATE TABLE IF NOT EXISTS capture_caplog_chat (
            capture_id INTEGER, seq INTEGER, ts TEXT, zone_db TEXT, text TEXT,
            PRIMARY KEY (capture_id, seq)
        );
        CREATE INDEX IF NOT EXISTS idx_capture_events_message ON capture_events(message_id);
        CREATE TABLE IF NOT EXISTS capture_ki_events (
            capture_id INTEGER, seq INTEGER, ts TEXT, event_type TEXT,
            keyitem_id INTEGER, keyitem_name TEXT, x REAL, y REAL, z REAL, zone_name TEXT,
            PRIMARY KEY (capture_id, seq)
        );
        CREATE INDEX IF NOT EXISTS idx_capture_ki_events_keyitem ON capture_ki_events(keyitem_id);
        CREATE TABLE IF NOT EXISTS capture_eventview (
            capture_id INTEGER, zone_db TEXT, seq INTEGER, ts TEXT, direction TEXT,
            opcode TEXT, packet_class TEXT, gp_command TEXT,
            entity_id INTEGER, mes_num INTEGER, message_number INTEGER, fields_json TEXT,
            PRIMARY KEY (capture_id, zone_db, seq)
        );
        CREATE INDEX IF NOT EXISTS idx_capture_eventview_entity ON capture_eventview(entity_id);
        CREATE INDEX IF NOT EXISTS idx_capture_eventview_mesnum ON capture_eventview(mes_num);
        CREATE TABLE IF NOT EXISTS capture_level_range (
            capture_id INTEGER, zone_db TEXT, entity_id INTEGER, name TEXT,
            level_min INTEGER, level_max INTEGER, act_index INTEGER,
            PRIMARY KEY (capture_id, zone_db, entity_id)
        );
        CREATE INDEX IF NOT EXISTS idx_capture_level_range_entity ON capture_level_range(entity_id);
        CREATE TABLE IF NOT EXISTS capture_attack_delay (
            capture_id INTEGER, zone_db TEXT, mob_name TEXT, hit_count INTEGER,
            delay_min INTEGER, delay_max INTEGER, delay_avg INTEGER, delay_median INTEGER,
            delay_stddev INTEGER, reverse_calc_delay INTEGER, reverse_calc_samples INTEGER,
            multihit_raw TEXT, slots_raw TEXT,
            PRIMARY KEY (capture_id, zone_db, mob_name)
        );
        CREATE INDEX IF NOT EXISTS idx_capture_attack_delay_name ON capture_attack_delay(mob_name);
        CREATE TABLE IF NOT EXISTS capture_pc_path (
            capture_id INTEGER, zone_db TEXT, leg INTEGER, step INTEGER,
            x REAL, y REAL, z REAL, dir INTEGER, delta INTEGER,
            PRIMARY KEY (capture_id, zone_db, step)
        );
        CREATE TABLE IF NOT EXISTS capture_source_files (
            capture_id INTEGER, filename TEXT, format_detected TEXT, ingested_at TEXT,
            row_count INTEGER, error TEXT,
            PRIMARY KEY (capture_id, filename)
        );
        CREATE TABLE IF NOT EXISTS capture_raw_packets (
            capture_id INTEGER, seq INTEGER, ts TEXT, direction TEXT, opcode TEXT, raw_hex TEXT,
            PRIMARY KEY (capture_id, seq)
        );
        CREATE TABLE IF NOT EXISTS capture_tags (
            capture_id INTEGER, tag TEXT,
            PRIMARY KEY (capture_id, tag)
        );
        CREATE INDEX IF NOT EXISTS idx_capture_tags_tag ON capture_tags(tag);
        CREATE INDEX IF NOT EXISTS idx_capture_raw_packets_opcode ON capture_raw_packets(capture_id, opcode);
        CREATE INDEX IF NOT EXISTS idx_capture_raw_packets_direction ON capture_raw_packets(capture_id, direction);
        CREATE INDEX IF NOT EXISTS idx_capture_raw_packets_opcode_global ON capture_raw_packets(opcode);
    """)
    # CREATE TABLE IF NOT EXISTS doesn't retrofit columns onto an already-existing table (same
    # trap hit earlier with sql_mob_pools/modelid) -- migrate captures explicitly so re-running
    # against the DB from before content_type/zones/mission_name existed doesn't silently no-op.
    existing_cols = {r[1] for r in con.execute("PRAGMA table_info(captures)")}
    for col, decl in [("content_type", "TEXT"), ("zones", "TEXT"), ("mission_name", "TEXT"),
                       ("video_url", "TEXT")]:
        if col not in existing_cols:
            con.execute(f"ALTER TABLE captures ADD COLUMN {col} {decl}")
    con.execute("CREATE INDEX IF NOT EXISTS idx_captures_content_type ON captures(content_type)")
    # legacy_look -- the real 20-byte look_t blob (see mmo.h) NPCLogger.db's `entries` table
    # carries per entity. model_id (above) is genuinely 0 for almost every real entity in this
    # addon's own output (confirmed against real capture bytes, not an ingestion bug) -- this is
    # the actual appearance data, previously read straight past and discarded. Stored as-is
    # (BLOB) rather than pre-decoded: the monster-model-id case (bytes[2:4], little-endian) is
    # verified against this project's own already-confirmed real examples, but the player-shaped
    # NPC gear-slot case is NOT yet verified against a real known-gear NPC -- decode on read, not
    # on ingest, so a later fix to the decoder doesn't need a re-ingest.
    existing_cne_cols = {r[1] for r in con.execute("PRAGMA table_info(capture_npc_entries)")}
    if "legacy_look" not in existing_cne_cols:
        con.execute("ALTER TABLE capture_npc_entries ADD COLUMN legacy_look BLOB")
    # Real NPCLogger.db columns audited 2026-09-04 (the user asked "is there other data we've
    # been omitting" after the legacy_look find) and confirmed genuinely populated in real capture
    # data, previously read straight past: DoorId (real door/trigger prop id), ActIndex (mission
    # act/objective index), Flags0-3 (four separate real flag words -- legacy_flags above is only
    # one merged field), legacy_flag (singular -- a DIFFERENT real field from legacy_flags,
    # plural), SubKind (entity subtype). Deliberately NOT added: ws_Level/ws_Type/ws_sName,
    # EndTime, Time (all zero across the real sample checked -- likely only populate under
    # specific conditions, not a gap worth chasing yet), id/version (internal bookkeeping, not
    # entity facts), and GrapIdTbl_1-9 (looked promising by name -- 8 nonzero slots suggested real
    # per-gear-slot ids -- but real values across different NPCs share a near-constant +4096
    # stride regardless of the NPC's actual look, so it does NOT look like per-entity equipment
    # data; not captured until its real meaning is confirmed against source, not a plausible name).
    for col, decl in [
        ("door_id", "INTEGER"), ("act_index", "INTEGER"),
        ("flags0", "INTEGER"), ("flags1", "INTEGER"), ("flags2", "INTEGER"), ("flags3", "INTEGER"),
        ("legacy_flag", "INTEGER"), ("sub_kind", "INTEGER"),
    ]:
        if col not in existing_cne_cols:
            con.execute(f"ALTER TABLE capture_npc_entries ADD COLUMN {col} {decl}")
    entity_profile.init_db(con)
    con.commit()


# ---------------------------------------------------------------- look_t decoding ------------
def decode_look_monster_model_id(look: bytes | None) -> int | None:
    """Real monster-model id out of a 20-byte look_t blob (Topaz's own struct, C:\\topaz\\src\\
    common\\mmo.h lines 100-112): `uint16 size; union { struct { uint8 face, race; }; uint16
    modelid; }; uint16 head, body, hands, legs, feet, main, sub, ranged;`. bytes[2:4], read
    little-endian, IS that union's `modelid` -- verified against multiple already-confirmed real
    examples already in npc_list.sql's own edit history (0x0000C70600... -> 1735, matches a
    real Qiqirn-family model id findable in this same file; 0x0000C10600... -> 1729, Giant Orobon;
    0x0000320000... -> 50, the generic invisible-placeholder model).

    Only meaningful for a MONSTER-shaped entity -- the same union, read as separate `face`/`race`
    bytes plus the 8 gear-slot uint16s that follow, is how a player-shaped NPC's look decodes
    instead, and that decode is NOT yet verified against a real known-gear NPC (a naive attempt
    produced implausible gear-slot values) -- deliberately not implemented here. Callers must
    already know (via mob_pools/npc_list cross-reference, not this blob alone) that the entity is
    a real monster before trusting this value; this function does not and cannot tell the two
    cases apart from the bytes alone."""
    if not look or len(look) < 4:
        return None
    return look[2] | (look[3] << 8)


# ---------------------------------------------------------------- source abstraction --------
class UnsupportedArchiveError(Exception):
    """A real archive/file was found but this tool has no way to read it -- distinct from
    "not found" or a parsing failure inside a real, readable bundle. Always carries a specific,
    actionable message (what was found, what to do about it), never a bare traceback -- this is
    what surfaces to the user on the Add Files / new-capture pages when their upload can't even be
    opened, as opposed to being opened but not matching any known internal log format."""


# Archive extensions seen in the wild for FFXI capture bundles that this tool deliberately does
# NOT support extracting, with a specific reason per format rather than one generic error --
# .rar needs an external unrar/unar binary this environment doesn't ship (rarfile is just a
# wrapper around one), and it's explicitly a "nice to have, not required" per 2026-09-05 --
# giving a clear, immediate rejection is the actual requirement, not silent support.
KNOWN_UNSUPPORTED_ARCHIVES = {
    ".rar": "RAR archives aren't supported (no unrar tool available in this environment) -- "
            "please re-compress as a .zip or .7z and re-upload.",
    ".tar": "Plain .tar archives aren't supported -- please re-compress as a .zip or .7z and re-upload.",
    ".gz": "Gzip archives aren't supported -- please re-compress as a .zip or .7z and re-upload.",
    ".tgz": "Gzip archives aren't supported -- please re-compress as a .zip or .7z and re-upload.",
    ".bz2": "Bzip2 archives aren't supported -- please re-compress as a .zip or .7z and re-upload.",
    ".xz": "XZ archives aren't supported -- please re-compress as a .zip or .7z and re-upload.",
}


class Source:
    """Uniform read access over a real folder, a .zip, or a .7z, keyed by forward-slash relative
    path so the same ingestion code works for all three without ever extracting a zip to disk
    (a .7z genuinely does get extracted to a temp dir first -- py7zr has no in-memory random-read
    API the way zipfile does -- and cleaned up in close())."""

    def __init__(self, path: Path):
        self.path = path
        self._zip = None
        self._extracted_tmp_dir = None
        suffix = path.suffix.lower() if path.is_file() else ""

        if path.is_file() and suffix == ".zip":
            self.is_zip = True
            try:
                self._zip = zipfile.ZipFile(path)
            except zipfile.BadZipFile as ex:
                raise UnsupportedArchiveError(
                    f"'{path.name}' has a .zip extension but isn't a valid zip file "
                    f"(corrupted download, or actually a different format?) -- {ex}"
                ) from ex
            # namelist() includes directory entries (real zip central-directory records with no
            # content, name ending in "/") alongside actual files -- confirmed live: a real
            # 25-entry capture zip (Bhaflau Remnants.zip) had exactly 15 such directory entries,
            # which without this filter got reported as 15 "not a recognized capture-log format"
            # failures on Add Files, even though every real file in the bundle ingested fine. The
            # .7z and real-folder branches below already filter to is_file()/p.is_file() -- this
            # keeps the zip branch consistent with both.
            self._names = [n for n in self._zip.namelist() if not n.endswith("/")]
        elif path.is_file() and suffix == ".7z":
            self.is_zip = False
            try:
                import py7zr
            except ImportError as ex:
                raise UnsupportedArchiveError(
                    "'.7z' support requires the py7zr package, which isn't installed in this "
                    "environment -- please re-compress as a .zip and re-upload."
                ) from ex
            tmp_dir = tempfile.mkdtemp(prefix="capture_7z_")
            try:
                with py7zr.SevenZipFile(path, mode="r") as archive:
                    archive.extractall(path=tmp_dir)
            except Exception as ex:
                raise UnsupportedArchiveError(
                    f"'{path.name}' has a .7z extension but couldn't be extracted "
                    f"(corrupted, encrypted, or an unsupported 7z variant) -- {ex}"
                ) from ex
            self._extracted_tmp_dir = Path(tmp_dir)
            self.path = self._extracted_tmp_dir
            self._names = [
                str(p.relative_to(self.path)).replace("\\", "/")
                for p in self.path.rglob("*") if p.is_file()
            ]
        elif path.is_dir():
            self.is_zip = False
            self._names = [
                str(p.relative_to(path)).replace("\\", "/")
                for p in path.rglob("*") if p.is_file()
            ]
        elif path.is_file() and suffix in KNOWN_UNSUPPORTED_ARCHIVES:
            raise UnsupportedArchiveError(
                f"'{path.name}': {KNOWN_UNSUPPORTED_ARCHIVES[suffix]}"
            )
        elif path.is_file():
            raise UnsupportedArchiveError(
                f"'{path.name}' isn't a recognized capture bundle -- expected a .zip, .7z, or a "
                f"real folder of capture logs (got a bare '{suffix or '(no extension)'}' file)."
            )
        else:
            raise UnsupportedArchiveError(f"'{path}' doesn't exist or isn't a file/folder this tool can read.")

    def find(self, suffix_pattern: str):
        """Return relative paths whose lowercased name matches a simple glob-ish suffix check."""
        rx = re.compile(suffix_pattern, re.I)
        return [n for n in self._names if rx.search(n)]

    def list_files(self) -> list[str]:
        """Every real file's relative path -- used to report which files a bundle contained that
        no known ingest pattern ever matched (see ingest_from_source's file_results)."""
        return list(self._names)

    def read_bytes(self, relname: str) -> bytes:
        if self.is_zip:
            return self._zip.read(relname)
        return (self.path / relname).read_bytes()

    def read_text(self, relname: str) -> str:
        return self.read_bytes(relname).decode("utf-8", "replace")

    def open_sqlite(self, relname: str):
        """sqlite3 needs a real file path -- for a zip member, spill to a temp file first.
        Returns (connection, tmp_path_or_None) so the caller knows whether to clean up."""
        if self.is_zip:
            tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
            tmp.write(self.read_bytes(relname))
            tmp.close()
            return sqlite3.connect(tmp.name), tmp.name
        return sqlite3.connect(str(self.path / relname)), None

    def close(self):
        if self._zip:
            self._zip.close()
        if self._extracted_tmp_dir:
            shutil.rmtree(self._extracted_tmp_dir, ignore_errors=True)


def close_sqlite(con, tmp_path):
    con.close()
    if tmp_path:
        try:
            Path(tmp_path).unlink()
        except OSError:
            pass


class SingleFileSource:
    """Same minimal interface as Source (read_bytes/read_text/open_sqlite/close), backed by one
    in-memory blob instead of a folder or zip. For a file dropped individually through the GUI
    there's no wrapping folder structure to key a relname off of, so every ingest_* function is
    called with `relname` fixed to this object's own display_name -- the existing per-format
    parsers only ever use relname for Path(relname).stem (the zone name) and to look themselves
    up in a zip/folder, and this object ignores the passed relname entirely, always serving its
    one held file. This lets every existing ingest_npc_db/ingest_kitrack/etc. be reused as-is."""

    def __init__(self, display_name: str, data: bytes):
        self.display_name = display_name
        self._data = data

    def read_bytes(self, relname: str) -> bytes:
        return self._data

    def read_text(self, relname: str) -> str:
        return self._data.decode("utf-8", "replace")

    def open_sqlite(self, relname: str):
        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp.write(self._data)
        tmp.close()
        return sqlite3.connect(tmp.name), tmp.name

    def close(self):
        pass


def sniff_sqlite_format(data: bytes) -> str | None:
    """Which capture table this SQLite blob is, by real column names -- the entries table shape
    is the only reliable signal once a bare .db file has no wrapping NPCLogger/ActionView/
    LevelRangeTrack folder to key off of."""
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.write(data)
    tmp.close()
    try:
        con = sqlite3.connect(tmp.name)
        try:
            cols = {r[1] for r in con.execute("PRAGMA table_info(entries)")}
        finally:
            con.close()
    except sqlite3.DatabaseError:
        return None
    finally:
        try:
            Path(tmp.name).unlink()
        except OSError:
            pass
    if not cols:
        return None
    if {"UniqueNo", "Hpp", "model_id"} <= cols:
        return "npclogger_db"
    if {"actor", "ActionType", "animation"} <= cols:
        return "actionview_db"
    if {"Level_min", "Level_max", "UniqueNo"} <= cols:
        return "levelrange_db"
    return None


def sniff_text_format(text: str) -> str | None:
    """Which capture log format this text file is, by real content signature -- a dropped file's
    own name can't be trusted to carry the addon folder it came from (idview/, KITrack/, etc.),
    so this looks at the first real content instead. Order matters: check the more specific
    signatures before the more generic ones."""
    head = text[:4000]
    if re.search(r'^(Incoming|Outgoing) Packet: 0x', head, re.MULTILINE):
        return "idview_simple"
    if IDVIEW2_HEADER_RE.search(head):
        # 2026-09-05: the newer block-format idview/eventview shape ("INCOMING < CS Event +
        # Params (0x034):  NPC: ..." then Event:/Params:/Option:/Message: lines) -- real content
        # confirmed identical whether it came from an "idview/simple" or "eventview/simple" folder
        # (see ingest_from_source's eventview/simple note), so a bare dropped file with this exact
        # header shape is unambiguous regardless of which folder it was dropped from.
        return "idview_simple"
    if ACTIONVIEW_SIMPLE_LINE_RE.search(head):
        return "actionview_simple"
    if re.search(r'^\[[\d\- :]+\]\s+(Lost KI|Obtained KI)\s*$', head, re.MULTILINE):
        return "kitrack"
    if re.search(r'^\[\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\]\s+(<<|>>)\s+\[0x[0-9A-Fa-f]{3}\]', head, re.MULTILINE):
        return "eventview"
    if re.search(r'\(\d+ hits\) - Delay: \d+-\d+', head):
        return "attackdelay"
    if re.search(r'^Defeated .+?:\s*\d+~\d+\s*HP\s*$', head, re.MULTILINE):
        return "hptrack"
    if re.match(r'^\s*leg,x,y,z,dir,delta\s*$', head, re.MULTILINE):
        return "pathlog_csv"
    if re.search(r"^\s*\[\d+\]\s*=\s*\{.*'id'.*=", head) or re.search(r"^\s*\[\d+\]\s*=\s*\{\['id'\]", head):
        return "npclogger_lua"
    return None


def ingest_single_file(con, capture_id: int, filename: str, data: bytes) -> dict:
    """Content-sniffs and ingests one arbitrarily-dropped file (no folder context) into an
    existing capture, records the attempt in capture_source_files regardless of outcome so the
    Add Files page can show a real history of what's been tried, and updates the capture's real
    zones list to reflect whatever just landed. Returns {"filename", "format", "rows", "error"}."""
    zone_db = Path(filename).stem.replace("_", " ")
    suffix = Path(filename).suffix.lower()
    fmt = None
    rows = 0
    error = None
    try:
        if suffix in (".db", ".sqlite", ".sqlite3"):
            fmt = sniff_sqlite_format(data)
            src = SingleFileSource(filename, data)
            if fmt == "npclogger_db":
                e, h = ingest_npc_db(con, capture_id, src, zone_db + ".db")
                rows = e + h
            elif fmt == "actionview_db":
                rows = ingest_actions_db(con, capture_id, src, "Actions.db")
            elif fmt == "levelrange_db":
                rows = ingest_level_range_db(con, capture_id, src, zone_db + ".db")
            else:
                error = "Unrecognized .db schema (not NPCLogger/ActionView/LevelRangeTrack entries shape)"
        elif suffix == ".csv":
            text = data.decode("utf-8", "replace")
            if re.match(r'^\s*leg,x,y,z,dir,delta\s*$', text[:200], re.MULTILINE):
                fmt = "pathlog_csv"
                # A real PathLog CSV's own filename is just the entity id (e.g. "17002517.csv")
                # -- the zone and NPC label live in its PARENT folders, which a single dropped
                # file has no way to carry. Rather than guess a zone, this format is honestly
                # only supported via a zip/folder upload (which preserves that path), not a bare
                # single-file drop.
                error = "PathLog CSVs need their real folder path (zone/NPC label) for zone context -- upload as part of a zip instead of a bare file"
            else:
                error = "CSV doesn't match PathLog's leg,x,y,z,dir,delta header"
        else:
            text = data.decode("utf-8", "replace")
            fmt = sniff_text_format(text)
            src = SingleFileSource(filename, data)
            if fmt == "idview_simple":
                rows = ingest_idview_simple(con, capture_id, src, zone_db + ".log")
            elif fmt == "kitrack":
                rows = ingest_kitrack(con, capture_id, src, zone_db + ".log")
            elif fmt == "eventview":
                rows = ingest_eventview(con, capture_id, src, "Capturer/" + zone_db + ".log")
            elif fmt == "attackdelay":
                rows = ingest_attackdelay(con, capture_id, src, zone_db + ".log")
            elif fmt == "hptrack":
                rows = ingest_hptrack(con, capture_id, src, zone_db + ".log")
            elif fmt == "npclogger_lua":
                e, p = ingest_npclogger_lua(con, capture_id, src, zone_db + ".lua")
                rows = e + p
            elif fmt == "actionview_simple":
                # Same redundancy risk as the zip-ingest path (see ingest_from_source) -- if an
                # ActionView.db has already been added to this capture, its rows already cover
                # this same real data; don't double-count under separate action_keys.
                has_db_actions = con.execute(
                    "SELECT 1 FROM capture_actions WHERE capture_id=? AND action_key NOT LIKE '%-simple-%' LIMIT 1",
                    (capture_id,)).fetchone()
                if has_db_actions:
                    error = "Skipped -- this capture already has ActionView.db-sourced actions, which cover the same real data as this text log"
                else:
                    rows = ingest_actionview_simple(con, capture_id, src, zone_db + ".log")
            else:
                error = "Unrecognized log format -- doesn't match idview/ActionView-simple/KITrack/EventView/AttackDelay/HPTrack/Npclogger-tables signatures"
    except Exception as ex:
        error = str(ex)

    con.execute("""INSERT OR REPLACE INTO capture_source_files
        (capture_id, filename, format_detected, ingested_at, row_count, error)
        VALUES (?,?,?,datetime('now'),?,?)""",
        (capture_id, filename, fmt, rows, error))
    recompute_zones(con, capture_id)
    con.commit()
    return {"filename": filename, "format": fmt, "rows": rows, "error": error}


def create_manual_capture(con, label: str, content_type: str, mission_name: str | None) -> int:
    """Starts a capture with no source file at all -- source_path is a synthetic manual:// marker
    (unique per creation timestamp) so it never collides with a real zip/folder path, and files
    get added to it one at a time afterward via ingest_single_file() or a real zip via
    ingest_from_source(). This is the "build a capture from scratch" entry point the GUI's
    /captures/new page uses."""
    source_path = f"manual://{label}#{int(time.time() * 1000)}"
    cur = con.execute("""INSERT INTO captures
        (source_path, capturer, capture_label, content_type, mission_name, addons,
         client_build, is_retail, start_time, zones)
        VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (source_path, None, label, content_type, mission_name or None, "[]", None, None, None, "[]"))
    con.commit()
    return cur.lastrowid


def set_capture_tags(con, capture_id: int, tags: list[str]):
    """Replaces this capture's real content-category tags (capture_tags, CAPTURE_TAGS' real
    taxonomy) wholesale -- delete-then-insert, same idiom as ingest_packetlogger's own
    replace-on-reingest, so re-saving the tag editor with a different set never leaves stale tags
    behind. Silently drops anything not in CAPTURE_TAGS rather than accepting arbitrary free text
    -- keeps the filter dropdown honest (every value shown there is guaranteed to have real rows)."""
    valid = set(CAPTURE_TAGS)
    con.execute("DELETE FROM capture_tags WHERE capture_id=?", (capture_id,))
    for tag in tags:
        if tag in valid:
            con.execute("INSERT OR IGNORE INTO capture_tags (capture_id, tag) VALUES (?,?)",
                        (capture_id, tag))
    con.commit()


def get_capture_tags(con, capture_id: int) -> list[str]:
    return [r[0] for r in con.execute(
        "SELECT tag FROM capture_tags WHERE capture_id=? ORDER BY tag", (capture_id,)).fetchall()]


# ---------------------------------------------------------------- manifest -------------------
def parse_manifest(text: str) -> dict:
    """manifest.txt is Lua-table-literal-shaped, not JSON. Good enough field extraction via
    regex rather than pulling in a Lua parser for four scalar fields and one list."""
    out = {}
    m = re.search(r'Version\s*=\s*"([^"]+)"', text)
    out["capturer_version"] = m.group(1) if m else None
    m = re.search(r'Build\s*=\s*"([^"]*)"', text, re.S)
    out["client_build"] = m.group(1).strip() if m else None
    m = re.search(r'IsRetail\s*=\s*(true|false)', text)
    out["is_retail"] = (m.group(1) == "true") if m else None
    m = re.search(r'StartTime\s*=\s*(\d+)', text)
    out["start_time"] = int(m.group(1)) if m else None
    out["addons"] = re.findall(r'"(\w+)"', text.split("Addons")[1].split("}")[0]) if "Addons" in text else []
    return out


CAPTURER_DIR_RE = re.compile(r'^([^/]+)/manifest\.txt$', re.I)


def find_capturer_root(src: Source) -> str | None:
    hits = src.find(r'manifest\.txt$')
    if not hits:
        return None
    m = CAPTURER_DIR_RE.match(hits[0])
    return m.group(1) if m else hits[0].rsplit("/", 1)[0]


# ---------------------------------------------------------------- ingestion -------------------
def ingest_npc_db(con, capture_id, src: Source, relname: str):
    zone_db = Path(relname).stem  # "Ilrusi Atoll.db" -> "Ilrusi Atoll"
    sub, tmp_path = src.open_sqlite(relname)
    try:
        tables = {r[0] for r in sub.execute("select name from sqlite_master where type='table'")}
        if "entries" not in tables:
            return 0, 0
        n_entries = n_hist = 0
        for row in sub.execute("""SELECT UniqueNo, Name, model_id, x, y, z, dir, Hpp,
                                          legacy_flags, legacy_status, legacy_animation, Speed,
                                          created_at, updated_at, legacy_look, DoorId, ActIndex,
                                          Flags0, Flags1, Flags2, Flags3, legacy_flag, SubKind
                                   FROM entries"""):
            (uid, name, model_id, x, y, z, d, hpp, lflags, lstatus, lanim, speed, cat, uat,
             look, door_id, act_index, flags0, flags1, flags2, flags3, legacy_flag,
             sub_kind) = row
            try:
                uid = int(uid)
            except (TypeError, ValueError):
                continue
            # legacy_look comes back as a str (NPCLogger stores it hex-encoded, per the real
            # samples checked -- e.g. "0001020210A5...") for some captures and already as raw
            # bytes (a real BLOB column) for others -- normalize to bytes so the decoder below
            # never has to care which.
            look_blob = None
            if look:
                if isinstance(look, (bytes, bytearray)):
                    look_blob = bytes(look)
                else:
                    try:
                        look_blob = bytes.fromhex(str(look))
                    except ValueError:
                        look_blob = None
            con.execute("""INSERT OR REPLACE INTO capture_npc_entries
                (capture_id, zone_db, entity_id, name, model_id, x, y, z, dir, hpp,
                 legacy_flags, legacy_status, legacy_animation, speed, created_at, updated_at,
                 legacy_look, door_id, act_index, flags0, flags1, flags2, flags3, legacy_flag,
                 sub_kind)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (capture_id, zone_db, uid, name, model_id, x, y, z, d, hpp,
                 lflags, lstatus, lanim, speed, cat, uat, look_blob, door_id, act_index,
                 flags0, flags1, flags2, flags3, legacy_flag, sub_kind))
            n_entries += 1
            record_entity_facts(con, uid, name, model_id, x, y, z, hpp, zone_db)
        if "history" in tables:
            for row in sub.execute("SELECT id, entry_id, time, delta FROM history"):
                seq, entry_id, ts, delta = row
                try:
                    eid = int(str(entry_id).split("-")[0])
                except (TypeError, ValueError):
                    continue
                con.execute("""INSERT OR REPLACE INTO capture_npc_history
                    (capture_id, zone_db, entity_id, seq, ts, delta_json)
                    VALUES (?,?,?,?,?,?)""", (capture_id, zone_db, eid, seq, ts, delta))
                n_hist += 1
        return n_entries, n_hist
    finally:
        close_sqlite(sub, tmp_path)


def ingest_level_range_db(con, capture_id, src: Source, relname: str) -> int:
    """LevelRangeTrack/<Zone>.db -- real observed mob level ranges (Level_min/Level_max), same
    NPCLogger-style SQLite entries/history shape but often empty (a real, valid state -- this
    addon only appears to write rows when some level-check feature actually triggers, not every
    capture has data here even in the newer format). Useful as an independent cross-check against
    sql_mob_groups.minLevel/maxLevel -- a real observed level range from a live client, not just
    what Topaz's own SQL says it should be."""
    zone_db = Path(relname).stem
    sub, tmp_path = src.open_sqlite(relname)
    try:
        tables = {r[0] for r in sub.execute("select name from sqlite_master where type='table'")}
        if "entries" not in tables:
            return 0
        n = 0
        for row in sub.execute("SELECT UniqueNo, sName, Level_min, Level_max, ActIndex FROM entries"):
            uid, name, lmin, lmax, act_index = row
            try:
                uid = int(uid)
            except (TypeError, ValueError):
                continue
            con.execute("""INSERT OR REPLACE INTO capture_level_range
                (capture_id, zone_db, entity_id, name, level_min, level_max, act_index)
                VALUES (?,?,?,?,?,?,?)""",
                (capture_id, zone_db, uid, name, lmin, lmax, act_index))
            n += 1
        return n
    finally:
        close_sqlite(sub, tmp_path)


WIDESCAN_LINE_RE = re.compile(
    r"\[(\d+)\]\s*=\s*\{\['id'\]=(\d+),\s*\['name'\]=\"([^\"]*)\",\s*\['index'\]=(-?\d+),\s*\['level'\]=(-?\d+)\}"
)


def ingest_widescan(con, capture_id, src: Source, relname: str) -> int:
    """npclogger/widescan/<Zone>.log -- real, confirmed 2026-09-04 -- a Lua-table-literal dump of
    every entity AutoWidescan observed (id/name/index/level), completely unhandled before this.
    Substantial real content in many captures (e.g. real mob ids/names/levels like
    17006593='Excaliace' level 75) -- present but silently unparsed, same shape of gap as
    idview/simple's second format and PathLog's PC_*.csv. Writes to TWO existing tables rather
    than inventing a new one: capture_npc_entries (id+name only, so entity resolution/links work
    the same as any other observed entity) via INSERT OR IGNORE (never overwrites a richer
    NPCLogger-sourced row -- widescan only ADDS entities NPCLogger never directly observed), and
    capture_level_range (level_min=level_max=the single real widescan level, matching that
    table's existing min/max shape from LevelRangeTrack) via INSERT OR REPLACE, since widescan is
    often the ONLY real level source for these specific ids."""
    zone_db = Path(relname).stem
    text = src.read_text(relname)
    n = 0
    for m in WIDESCAN_LINE_RE.finditer(text):
        key_id, uid, name, index, level = m.groups()
        uid = int(uid)
        index = int(index)
        level = int(level)
        con.execute("""INSERT OR IGNORE INTO capture_npc_entries
            (capture_id, zone_db, entity_id, name) VALUES (?,?,?,?)""",
            (capture_id, zone_db, uid, name))
        con.execute("""INSERT OR REPLACE INTO capture_level_range
            (capture_id, zone_db, entity_id, name, level_min, level_max, act_index)
            VALUES (?,?,?,?,?,?,?)""",
            (capture_id, zone_db, uid, name, level, level, index))
        n += 1
        if name:
            entity_profile.record_field(con, "npc", uid, "capture_name", "capture", name)
    return n


ATTACKDELAY_HEADER_RE = re.compile(r'^(.+?) \((\d+) hits\) - Delay: (\d+)-(\d+)\s*$', re.MULTILINE)
ATTACKDELAY_AVG_RE = re.compile(r'Avg:\s*(\d+)\s*\|\s*Med:\s*(\d+)\s*\|\s*StdDev:\s*(\d+)')
ATTACKDELAY_REVERSE_RE = re.compile(r'Reverse calculation:\s*(\d+)\s*\((\d+) samples\)')
ATTACKDELAY_MULTIHIT_RE = re.compile(r'Multi-hit:\s*(.+)$', re.MULTILINE)
ATTACKDELAY_SLOTS_RE = re.compile(r'Slots/rnd:\s*(.+)$', re.MULTILINE)


def ingest_attackdelay(con, capture_id, src: Source, relname: str) -> int:
    """AttackDelay/<Zone>.log -- real observed attack-timing statistics, aggregated per mob NAME
    across the whole zone (not per entity_id -- this addon doesn't track individual instances,
    just accumulates hit intervals by name). "Reverse calculation" is the addon's own estimate of
    the mob's real configured delay from the observed hit-interval distribution -- a genuine,
    independent cross-check against sql_mob_pools.cmbDelay, not derived from Topaz's SQL at all."""
    zone_db = Path(relname).stem.replace("_", " ")
    text = src.read_text(relname)
    headers = [(m.start(), m.group(1).strip(), int(m.group(2)), int(m.group(3)), int(m.group(4)))
               for m in ATTACKDELAY_HEADER_RE.finditer(text)]
    n = 0
    for i, (pos, name, hits, dmin, dmax) in enumerate(headers):
        end = headers[i + 1][0] if i + 1 < len(headers) else len(text)
        block = text[pos:end]
        avg_m = ATTACKDELAY_AVG_RE.search(block)
        rev_m = ATTACKDELAY_REVERSE_RE.search(block)
        mh_m = ATTACKDELAY_MULTIHIT_RE.search(block)
        slots_m = ATTACKDELAY_SLOTS_RE.search(block)
        con.execute("""INSERT OR REPLACE INTO capture_attack_delay
            (capture_id, zone_db, mob_name, hit_count, delay_min, delay_max, delay_avg,
             delay_median, delay_stddev, reverse_calc_delay, reverse_calc_samples,
             multihit_raw, slots_raw)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (capture_id, zone_db, name, hits, dmin, dmax,
             int(avg_m.group(1)) if avg_m else None, int(avg_m.group(2)) if avg_m else None,
             int(avg_m.group(3)) if avg_m else None,
             int(rev_m.group(1)) if rev_m else None, int(rev_m.group(2)) if rev_m else None,
             mh_m.group(1) if mh_m else None, slots_m.group(1) if slots_m else None))
        n += 1
    return n


def record_entity_facts(con, uid, name, model_id, x, y, z, hpp, zone_db):
    if name:
        entity_profile.record_field(con, "npc", uid, "capture_name", "capture", name)
    if model_id:
        entity_profile.record_field(con, "npc", uid, "capture_model_id", "capture", model_id)
    if x is not None and y is not None and z is not None:
        entity_profile.record_field(con, "npc", uid, "capture_position", "capture",
                                     f"({x:.3f}, {y:.3f}, {z:.3f}) [{zone_db}]")


ACTIONVIEW_DB_RE = re.compile(r'ActionView/[^/]+/Actions\.db$', re.I)
PATHLOG_NPC_RE = re.compile(r'PathLog/[^/]+/([^/]+)/([^/]+)/(\d+)\.csv$', re.I)

# actionview/simple/<Zone>.log -- real, confirmed 2026-09-05 (Blitzkrieg.zip) -- older
# Wiggo/capture-lib-era plain-text action log, one real observed ability/weaponskill/spell use per
# line: "[Actor: 17047710 (Molted Mamool Ja)] Doton: Ni > Cat: 4 ID: 330 Anim: 330 Msg: 31". Same
# real fields (actor id+name, category, ability id, animation id, message id) as the newer
# ActionView.db format ingest_actions_db already reads -- just from a text log instead of SQLite.
ACTIONVIEW_SIMPLE_LINE_RE = re.compile(
    r'^\[Actor:\s*(\d+)\s*(?:\(([^)]*)\))?\]\s*(.+?)\s*>\s*Cat:\s*(-?\d+)\s*ID:\s*(-?\d+)\s*'
    r'Anim:\s*(-?\d+)\s*Msg:\s*(-?\d+)\s*$', re.MULTILINE
)


def ingest_actionview_simple(con, capture_id, src: Source, relname: str) -> int:
    text = src.read_text(relname)
    n = 0
    for i, line in enumerate(text.splitlines()):
        m = ACTIONVIEW_SIMPLE_LINE_RE.match(line.strip())
        if not m:
            continue
        actor, actor_name, ability_name, cat, aid, anim, msg = m.groups()
        actor = int(actor)
        key = f"{actor}-simple-{i}"
        con.execute("""INSERT OR REPLACE INTO capture_actions
            (capture_id, action_key, actor, actor_name, action_type, animation, category,
             message, name, ts) VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (capture_id, key, actor, actor_name or None, None, int(anim), int(cat),
             int(msg), ability_name, None))
        n += 1
        if actor_name:
            entity_profile.record_field(con, "npc", actor, "capture_name", "capture", actor_name)
    return n


def ingest_actions_db(con, capture_id, src: Source, relname: str):
    sub, tmp_path = src.open_sqlite(relname)
    try:
        tables = {r[0] for r in sub.execute("select name from sqlite_master where type='table'")}
        if "entries" not in tables:
            return 0
        n = 0
        for row in sub.execute("""SELECT id, actor, actor_name, ActionType, animation, category,
                                          message, name, updated_at FROM entries"""):
            aid, actor, actor_name, atype, anim, cat, msg, name, ts = row
            key = f"{actor}-{aid}"
            con.execute("""INSERT OR REPLACE INTO capture_actions
                (capture_id, action_key, actor, actor_name, action_type, animation, category,
                 message, name, ts) VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (capture_id, key, actor, actor_name, atype, anim, cat, msg, name, ts))
            n += 1
        return n
    finally:
        close_sqlite(sub, tmp_path)


def ingest_pathlog(con, capture_id, src: Source, relname: str):
    m = PATHLOG_NPC_RE.search(relname)
    if not m:
        return 0
    zone_db, npc_label, entity_id = m.group(1), m.group(2), int(m.group(3))
    text = src.read_text(relname)
    lines = text.splitlines()
    if not lines:
        return 0
    n = 0
    for step, line in enumerate(lines[1:]):  # skip header
        parts = line.split(",")
        if len(parts) < 6:
            continue
        try:
            leg, x, y, z, d, delta = parts[:6]
            con.execute("""INSERT OR REPLACE INTO capture_npc_path
                (capture_id, zone_db, entity_id, leg, step, x, y, z, dir, delta)
                VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (capture_id, zone_db.replace("_", " "), entity_id, int(leg), step,
                 float(x), float(y), float(z), int(d), int(delta)))
            n += 1
        except ValueError:
            continue
    return n


PATHLOG_PC_RE = re.compile(r'PathLog/[^/]+/PC_([^/]+)\.csv$', re.I)


def ingest_pc_pathlog(con, capture_id, src: Source, relname: str) -> int:
    """PathLog/<capturer>/PC_<Zone>.csv -- real, confirmed 2026-09-04 -- the CAPTURING
    CHARACTER's own position trace per zone, same real (leg,x,y,z,dir,delta) shape as the
    per-NPC PathLog CSVs, just a different real filename convention (PC_<Zone> instead of
    <npc_label>/<numeric id>) that PATHLOG_NPC_RE's numeric-id-only pattern silently skipped.
    Kept in its own table (capture_pc_path) rather than folded into capture_npc_path -- there is
    no real numeric entity id here (the filename only carries the zone), and inventing one to
    reuse that table's schema would risk colliding with (or being mistaken for) a real NPC id."""
    m = PATHLOG_PC_RE.search(relname)
    if not m:
        return 0
    zone_db = m.group(1).replace("_", " ")
    text = src.read_text(relname)
    lines = text.splitlines()
    if not lines:
        return 0
    n = 0
    for step, line in enumerate(lines[1:]):  # skip header
        parts = line.split(",")
        if len(parts) < 6:
            continue
        try:
            leg, x, y, z, d, delta = parts[:6]
            con.execute("""INSERT OR REPLACE INTO capture_pc_path
                (capture_id, zone_db, leg, step, x, y, z, dir, delta)
                VALUES (?,?,?,?,?,?,?,?,?)""",
                (capture_id, zone_db, int(leg), step,
                 float(x), float(y), float(z), int(d), int(delta)))
            n += 1
        except ValueError:
            continue
    return n


HP_LINE_RE = re.compile(r'^Defeated (.+?):\s*(\d+)~(\d+)\s*HP\s*$')
# 2026-09-08: real bug -- this was the ONLY pattern ingest_hptrack ever tried, but a real, common
# HPTrack version (57 of 137 real HPTrack files sampled across the capture corpus, vs. 80 for the
# "Defeated" shape above) writes "[HP Track] Killed <id> (<name>): <min>~<max>HP[, Est.HP: ...]"
# instead -- confirmed real, not a guess (both shapes appear across many real captures, so this is
# two genuinely different real tool versions, not one replacing the other). Every real hptrack/
# simple/*.log file in this newer format was silently returning 0 rows -- not empty, just never
# matched. CAPLOG_HP_KILL_RE (defined below, same real "[HP Track] Killed ..." shape CapLog's own
# embedded HP Track lines use) already parses this exact format -- reused here, not duplicated.
# (CAPLOG_HP_KILL_RE is defined later in this file -- fine, Python resolves module-level names at
# call time, and this function is never called before the whole module finishes importing.)


def ingest_hptrack(con, capture_id, src: Source, relname: str):
    text = src.read_text(relname)
    n = 0
    for line in text.splitlines():
        line = line.strip()
        m = HP_LINE_RE.match(line)
        if m:
            mob_name, hp_low, hp_high = m.group(1), m.group(2), m.group(3)
        else:
            # The standalone file writes this tool's own "[HP Track] " tag inline (confirmed real,
            # unlike CapLog's embedded lines where the tag has already been split off by the time
            # CAPLOG_HP_KILL_RE sees it) -- strip it before matching the same real regex.
            untagged = line[len("[HP Track] "):] if line.startswith("[HP Track] ") else line
            m2 = CAPLOG_HP_KILL_RE.match(untagged)
            if not m2:
                continue
            mob_name, hp_low, hp_high = m2.group(1), m2.group(2), m2.group(3)
        n += 1
        con.execute("""INSERT OR REPLACE INTO capture_hp_events
            (capture_id, seq, mob_name, hp_low, hp_high) VALUES (?,?,?,?,?)""",
            (capture_id, n, mob_name, int(hp_low), int(hp_high)))
    return n


NPCLOGGER_LUA_LINE_RE = re.compile(r'^\s*\[(\d+)\]\s*=\s*\{(.*)\},?\s*$')
NPCLOGGER_LUA_FIELD_RE = re.compile(r"\['(\w+)'\]\s*=\s*(?:\"([^\"]*)\"|(-?[\d.]+))")


IDVIEW_LINE_RE = re.compile(
    r'^(Incoming|Outgoing) Packet: (0x[0-9A-Fa-f]{3}) \(([^)]+)\),\s*(.*)$'
)
IDVIEW_ENTITY_RE = re.compile(r'(?:NPC|Actor):\s*(\d+)\s*\(([^)]*)\)')
KI_HEADER_RE = re.compile(r'^\[([\d\- :]+)\]\s+(Lost KI|Obtained KI)\s*$', re.MULTILINE)
KI_PAIR_RE = re.compile(r'\{\s*"(\w+)"\s*,\s*"?([^"\n]*?)"?\s*\}', re.DOTALL)


def ingest_kitrack(con, capture_id, src: Source, relname: str) -> int:
    """KITrack/<capturer>.log -- real key-item acquisition/loss events (a custom brace-delimited
    text format, not JSON or a Lua table literal), one event per "[timestamp] Lost KI"/"Obtained
    KI" header followed by a {"Key", Value} block. Directly useful for this project's standing
    key-item id drift problem (LSB/retail ids drift for the large majority of key items, per
    id_bridge.py's own findings) -- this is a real observed (id, name, position, zone) triple for
    a key item actually picked up/lost in a real session, not a guess from wiki text."""
    text = src.read_text(relname)
    headers = [(m.start(), m.group(1), m.group(2)) for m in KI_HEADER_RE.finditer(text)]
    n = 0
    for i, (pos, ts, event_type) in enumerate(headers):
        end = headers[i + 1][0] if i + 1 < len(headers) else len(text)
        block = text[pos:end]
        fields = dict(KI_PAIR_RE.findall(block))
        if "ID" not in fields:
            continue
        try:
            keyitem_id = int(fields["ID"])
        except ValueError:
            continue

        def to_float(key):
            v = fields.get(key)
            try:
                return float(v) if v is not None else None
            except ValueError:
                return None

        con.execute("""INSERT OR REPLACE INTO capture_ki_events
            (capture_id, seq, ts, event_type, keyitem_id, keyitem_name, x, y, z, zone_name)
            VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (capture_id, n, ts, event_type, keyitem_id, fields.get("Name"),
             to_float("X"), to_float("Y"), to_float("Z"), fields.get("Zone")))
        n += 1
    return n


# 2026-09-08: real caplog/<Capturer>_<date>.txt format -- confirmed directly against the real
# addon source (reference_addons/wiggo-addons-1/capture/{caplog,npclogger,eventview,hptrack}.lua),
# not guessed from samples alone. CapLog itself only owns the plain in-game chat/system text it
# intercepts via windower.register_event("incoming text", caplog.checkMessage) -- every other
# [Tag]-prefixed line (NPCL/ID View/HP Track/PV/Capture) is a DIFFERENT sibling addon's own
# windower.add_to_chat("[Tag] message") call, which CapLog's chat-hook also captures and
# timestamps, merging every loaded "capture"-suite addon's output into one chronological file.
# Confirmed stable 2019-2025 across six real capturers (Bemused/Rabadaba/Giichi/Siknawz/Tacocat/
# Grievor) via direct sampling, not assumed from one file.
CAPLOG_HEADER_LINE_RE = re.compile(r'^\[(\d{2}:\d{2}:\d{2})\]\s?(.*)$')
CAPLOG_AREA_RE = re.compile(r'^===\s*Area:\s*(.+?)\s*===$')
CAPLOG_TAGGED_RE = re.compile(r'^\[(NPCL|ID View|HP Track|Capture|PV|AView|EView)\]\s*(.*)$')
# CapLog's own [ID View] rendering is a THIRD real shape, distinct from both idview/simple's two
# known formats (IDVIEW_LINE_RE / IDVIEW2_HEADER_RE elsewhere in this file) -- one line, comma-
# separated fields, and critically a DECIMAL Event number (confirmed live: "Event: 409", not
# "Event: 0x199") where IDVIEW_EVENT_RE expects hex -- so this needs its own regexes, not reuse of
# those, even though the eventual capture_events row shape (hex-formatted event_hex on store) stays
# consistent with how _ingest_idview_simple_v2 already normalizes its own decimal Event field.
CAPLOG_IDVIEW_HEADER_RE = re.compile(
    r'^(OUTGOING >|INCOMING <)\s+(.+?)\s*\((0x[0-9A-Fa-f]{3})\):\s*(.*)$'
)
CAPLOG_EVENT_RE = re.compile(r'Event:\s*(\d+)')
CAPLOG_OPTION_RE = re.compile(r'Option:\s*(-?\d+)')
CAPLOG_MESSAGE_RE = re.compile(r'Message:\s*(\d+)')
CAPLOG_PARAMS_RE = re.compile(r'Params:\s*(.*)$')
# hptrack.lua's real "[HP Track] Killed <id> (<name>): <min>~<max>HP" line -- Est.HP/Mthd suffix is
# genuinely optional (only appended when hptrack.lua's own interval-estimate math produces a value
# inside the observed min/max range, confirmed in its real processDeath() source).
CAPLOG_HP_KILL_RE = re.compile(
    r'^Killed \d+ \((.+?)\):\s*(\d+)~(\d+)HP(?:,\s*Est\.HP:\s*\d+\s*\(Mthd:\s*\w\))?$'
)
# Real capture-tool startup/status bookkeeping lines (see caplog.lua/capture-lib.lua's own
# lib.msg/notice calls) -- never real game text, so excluded from the chat table rather than
# stored as if they were.
CAPLOG_BOOKKEEPING_RE = re.compile(
    r'^(Logging started:|Always auto-widescanning!|Capture started!|Capture stopped\.)'
)
# 2026-09-08: a real THIRD CapLog variant, confirmed live across 88 real captures (a "Thris"
# capturer) and consistent across every one sampled -- a titlecase "CapLog" folder (not lowercase
# "caplog") whose [EView] tag carries the SAME real EventView packet taxonomy build_eventview's own
# EVENTVIEW_HEADER_RE already knows (CMessageSpecialPacket/CEventPacket/CEventPacket*/
# CMessageTextPacket/CEntityAnimationPacket/CEntityVisualPacket/CReleasePacket/CEventUpdatePacket,
# real GP_SERV_COMMAND_*/GP_CLI_COMMAND_* constants) -- but a genuinely different physical shape:
# a short time-only "[HH:MM:SS][EView] << [0xNNN] ClassName (COMMAND)" header (vs. EventView's own
# standalone-file full-datetime header with no tag) immediately followed by ONE comma-separated
# "Key: value, Key: value" field line (vs. EventView's own brace-delimited Lua-table-literal body)
# -- confirmed by direct content comparison, not assumed from the shared "EView"/"EventView" name.
# Field names also genuinely differ (EventPara/EventNum/EndPara/Mode, not MesNum/MessageNumber) --
# deliberately NOT mapped onto capture_eventview's mes_num/message_number columns without a
# confirmed real equivalence (per this project's standing never-fabricate-ids rule); the full real
# fields still land losslessly in fields_json regardless.
CAPLOG_EVIEW_HEADER_RE = re.compile(
    r'^(<<|>>)\s+\[(0x[0-9A-Fa-f]{3})\]\s+(\w+)\*?\s+\((\w+)\)\s*$'
)


def _parse_caplog_eview_fields(line: str) -> dict[str, str]:
    """'Key: val, Key2: val2, num: {1, 2, 3}' -> {"Key": "val", ...} -- top-level-comma split only
    (brace-depth tracked, same idea as split_sql_values' quote tracking above) so a comma inside a
    real array field like 'num: {46, -1, 0, ...}' never breaks a field boundary."""
    fields: dict[str, str] = {}
    depth = 0
    buf = []
    parts = []
    for ch in line:
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
        if ch == "," and depth == 0:
            parts.append("".join(buf))
            buf = []
            continue
        buf.append(ch)
    if buf:
        parts.append("".join(buf))
    for part in parts:
        if ":" not in part:
            continue
        key, val = part.split(":", 1)
        fields[key.strip()] = val.strip()
    return fields
# A fixed, deliberately-unrealistic seq offset for rows this ingester writes into capture_events/
# capture_hp_events -- both tables are also written by OTHER real ingesters (ingest_idview_simple,
# ingest_hptrack) for the SAME capture_id/zone_db when a capture bundle has both a standalone file
# AND a caplog file for the same session (confirmed real: the Bhaflau Remnants/Foxmulder fixture
# has both eventview/simple/Bhaflau Remnants.log -- 92 real rows via ingest_idview_simple -- and a
# caplog file, both wanting to write capture_events rows for zone_db="Bhaflau Remnants"). Without
# this offset, both ingesters' independent 0-based seq counters would collide on the same real
# primary key and silently overwrite each other's rows. A no-collision-by-construction offset
# (rather than a MAX(seq)+1 query) also keeps re-importing the same caplog file idempotent -- the
# same line always maps to the same seq, so INSERT OR REPLACE cleanly updates rather than
# appending duplicates on a second import.
CAPLOG_SEQ_BASE = 10_000_000


def ingest_caplog(con, capture_id, src: Source, relname: str) -> tuple[int, int, int, int]:
    """caplog/<Capturer>_<date>.txt -- see the real-format notes on the regexes above. Four real,
    distinct kinds of value get extracted, each into its existing home table so downstream pages
    see this data alongside the same kind of data from other formats:
      1. [ID View] event/CS/dialogue lines -> capture_events (same table ingest_idview_simple uses).
      2. [HP Track] kill lines -> capture_hp_events (same table ingest_hptrack uses).
      3. [EView] packet header + field-line blocks (a real third CapLog variant, "Thris" capturer)
         -> capture_eventview (same table ingest_eventview uses).
      4. Real untagged in-game chat/system text -> capture_caplog_chat (new table -- genuinely
         unique data: item drops, mission announcements, combat log, Records of Eminence progress,
         not carried by any other format in this project's capture pipeline).

    [NPCL]'s own "New: <id> (<name>)"/"...saved to database"/"...Widescan..." lines are
    deliberately NOT persisted as structured rows -- they carry strictly less real information (no
    position/model_id/etc) than this same session's real NPCLogger tables/database .lua files
    already ingest, so storing them again here would just be a weaker duplicate, not new data.

    zone_db (needed for capture_events'/capture_eventview's real primary keys) comes from tracking
    the most recent "=== Area: <Zone> ===" marker CapLog itself writes on every real zone
    transition. Any [ID View]/[EView] line seen BEFORE the first Area marker (capture-tool startup,
    before the player has even zoned in) has no real zone to attribute to and is skipped rather
    than guessed, per this project's standing never-fabricate-ids rule -- HP Track kills carry no
    zone_db column at all (matching ingest_hptrack's own table shape) so they're recorded
    regardless."""
    lines = text.splitlines() if (text := src.read_text(relname)) else []
    events_n = hp_n = eview_n = chat_n = 0
    zone_db = None
    event_local = hp_local = eview_local = 0

    i, n_lines = 0, len(lines)
    while i < n_lines:
        line = lines[i].strip()
        i += 1
        if not line:
            continue
        header_m = CAPLOG_HEADER_LINE_RE.match(line)
        if not header_m:
            continue
        ts, rest = header_m.groups()
        rest = rest.strip()
        if not rest:
            continue

        area_m = CAPLOG_AREA_RE.match(rest)
        if area_m:
            zone_db = area_m.group(1).strip()
            continue

        tag_m = CAPLOG_TAGGED_RE.match(rest)
        if tag_m:
            tag, body = tag_m.groups()
            if tag == "EView" and zone_db is not None:
                ev_m = CAPLOG_EVIEW_HEADER_RE.match(body)
                # The real field-value line is the NEXT physical line (confirmed live: always
                # present, no blank line between header and body in every real sample seen) --
                # peeking ahead rather than requiring it match any particular shape itself, since
                # its own content (comma-separated Key: value pairs) has no line-level marker of
                # its own to detect independently.
                if ev_m and i < n_lines:
                    direction, opcode, packet_class, gp_command = ev_m.groups()
                    field_line = lines[i].strip()
                    i += 1
                    fields = _parse_caplog_eview_fields(field_line)
                    # Real field values here look like "16998996 (Runic Seal)" -- a leading
                    # integer id, optionally followed by a parenthesized real name -- not a bare
                    # int the way EventView's own brace-delimited body stores UniqueNo, so this
                    # reuses IDVIEW_ENTITY_RE's real id+name extraction shape instead of int().
                    entity_id = entity_name = None
                    for k in EVENTVIEW_ENTITY_KEYS:
                        if k in fields:
                            em = re.match(r'(\d+)\s*(?:\(([^)]*)\))?', fields[k])
                            if em and int(em.group(1)):
                                entity_id, entity_name = int(em.group(1)), em.group(2) or None
                                break
                    con.execute("""INSERT OR REPLACE INTO capture_eventview
                        (capture_id, zone_db, seq, ts, direction, opcode, packet_class, gp_command,
                         entity_id, mes_num, message_number, fields_json)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                        (capture_id, zone_db, CAPLOG_SEQ_BASE + eview_local, ts, direction, opcode,
                         packet_class, gp_command, entity_id, None, None, json.dumps(fields)))
                    eview_local += 1
                    eview_n += 1
                    if entity_id and entity_name:
                        entity_profile.record_field(con, "npc", entity_id, "capture_name",
                                                      "capture", entity_name)
            elif tag == "ID View" and zone_db is not None:
                ev_m = CAPLOG_IDVIEW_HEADER_RE.match(body)
                if ev_m:
                    direction_word, opcode_name, opcode, ev_rest = ev_m.groups()
                    direction = "Outgoing" if direction_word.startswith("OUTGOING") else "Incoming"
                    entity_id = entity_name = None
                    em = IDVIEW_ENTITY_RE.search(ev_rest)
                    if em:
                        entity_id, entity_name = int(em.group(1)), em.group(2) or None
                    event_m = CAPLOG_EVENT_RE.search(ev_rest)
                    event_hex = f"0x{int(event_m.group(1)):04X}" if event_m else None
                    option_m = CAPLOG_OPTION_RE.search(ev_rest)
                    option = int(option_m.group(1)) if option_m else None
                    message_m = CAPLOG_MESSAGE_RE.search(ev_rest)
                    message_id = int(message_m.group(1)) if message_m else None
                    params_m = CAPLOG_PARAMS_RE.search(ev_rest)
                    params_raw = params_m.group(1).strip() if params_m else None

                    con.execute("""INSERT OR REPLACE INTO capture_events
                        (capture_id, zone_db, seq, direction, opcode, opcode_name, entity_id,
                         entity_name, event_hex, option, message_id, params_raw)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                        (capture_id, zone_db, CAPLOG_SEQ_BASE + event_local, direction, opcode,
                         opcode_name, entity_id, entity_name, event_hex, option, message_id,
                         params_raw))
                    event_local += 1
                    events_n += 1
                    if entity_id and entity_name:
                        entity_profile.record_field(con, "npc", entity_id, "capture_name",
                                                      "capture", entity_name)
            elif tag == "HP Track":
                hp_m = CAPLOG_HP_KILL_RE.match(body)
                if hp_m:
                    mob_name, hp_low, hp_high = hp_m.groups()
                    con.execute("""INSERT OR REPLACE INTO capture_hp_events
                        (capture_id, seq, mob_name, hp_low, hp_high) VALUES (?,?,?,?,?)""",
                        (capture_id, CAPLOG_SEQ_BASE + hp_local, mob_name, int(hp_low), int(hp_high)))
                    hp_local += 1
                    hp_n += 1
            # NPCL/Capture/PV/AView: deliberately not persisted, see docstring.
            continue

        if CAPLOG_BOOKKEEPING_RE.match(rest):
            continue

        # Everything else is real, untagged in-game chat/system text.
        con.execute("""INSERT OR REPLACE INTO capture_caplog_chat
            (capture_id, seq, ts, zone_db, text) VALUES (?,?,?,?,?)""",
            (capture_id, chat_n, ts, zone_db, rest))
        chat_n += 1

    return events_n, hp_n, eview_n, chat_n


EVENTVIEW_HEADER_RE = re.compile(
    r'^\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\]\s+(<<|>>)\s+\[(0x[0-9A-Fa-f]{3})\]\s+(\w+)\*?\s+\((\w+)\)\s*$',
    re.MULTILINE)
EVENTVIEW_KV_RE = re.compile(r'^(\w+)\s*=\s*(.+?),?\s*$')
EVENTVIEW_ENTITY_KEYS = ("UniqueNo", "UniqueNoCas", "UniqueNoTar", "UniqueNo1", "UniqueNo2")
EVENTVIEW_MESNUM_KEYS = ("MesNum", "MesNum1", "MesNum2")
EVENTVIEW_MSGNUM_KEYS = ("MessageNumber", "MessageNumber1", "MessageNumber2")


def _parse_eventview_body(body_lines: list[str]) -> dict:
    """Real top-level key=value pairs from an EventView block's Lua-table-literal body -- nested
    tables (header={...}, num={...}/Num1={...}/etc) are skipped by brace-depth counting rather
    than parsed, since none of this project's actual uses need them: the fields worth extracting
    (UniqueNo*, MesNum*, MessageNumber*) are always top-level scalars in every real sample seen."""
    kv = {}
    depth = 0
    i, n = 0, len(body_lines)
    while i < n:
        stripped = body_lines[i].strip()
        if depth == 0:
            m = EVENTVIEW_KV_RE.match(stripped)
            if m:
                key, val = m.group(1), m.group(2)
                if val == "{":
                    depth = 1
                    i += 1
                    while i < n and depth > 0:
                        depth += body_lines[i].count("{") - body_lines[i].count("}")
                        i += 1
                    continue
                kv[key] = val.strip('"')
        i += 1
    return kv


def ingest_eventview(con, capture_id, src: Source, relname: str) -> int:
    """EventView/<capturer>/<Zone>.log -- real, already-decoded packet dumps (the capture tool's
    own field names, not a hex blob): real packet class (CMessageSpecialPacket etc.), the real
    GP_SERV_COMMAND_* constant, and a Lua-table-literal body with the actual field values
    (UniqueNo/UniqueNoCas/UniqueNoTar as real entity ids, MesNum/MessageNumber as real dialog
    message ids). This is genuinely richer than idview/simple (real timestamps, no hand-decoding
    needed) -- kept as its own table rather than merged into capture_events since the two formats
    don't share a schema (EventView has real per-packet-type field names, idview normalizes to a
    handful of generic ones)."""
    zone_db = Path(relname).stem.replace("_", " ")
    text = src.read_text(relname)
    headers = [(m.start(), m.end(), m.group(1), m.group(2), m.group(3), m.group(4), m.group(5))
               for m in EVENTVIEW_HEADER_RE.finditer(text)]
    n = 0
    for hstart, hend, ts, direction, opcode, packet_class, gp_command in headers:
        rest = text[hend:]
        brace_pos = rest.find("{")
        if brace_pos == -1:
            continue
        depth = 0
        j = brace_pos
        while j < len(rest):
            if rest[j] == "{":
                depth += 1
            elif rest[j] == "}":
                depth -= 1
                if depth == 0:
                    break
            j += 1
        else:
            continue  # unterminated block -- skip rather than mis-parse
        body = rest[brace_pos + 1:j]
        fields = _parse_eventview_body(body.splitlines())

        entity_id = None
        for k in EVENTVIEW_ENTITY_KEYS:
            if k in fields:
                try:
                    v = int(fields[k])
                except ValueError:
                    continue
                if v:  # a real observed 0 (no target) isn't a useful entity_id
                    entity_id = v
                    break
        mes_num = next((int(fields[k]) for k in EVENTVIEW_MESNUM_KEYS if k in fields and fields[k].lstrip("-").isdigit()), None)
        msg_number = next((int(fields[k]) for k in EVENTVIEW_MSGNUM_KEYS if k in fields and fields[k].lstrip("-").isdigit()), None)

        con.execute("""INSERT OR REPLACE INTO capture_eventview
            (capture_id, zone_db, seq, ts, direction, opcode, packet_class, gp_command,
             entity_id, mes_num, message_number, fields_json)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (capture_id, zone_db, n, ts, direction, opcode, packet_class, gp_command,
             entity_id, mes_num, msg_number, json.dumps(fields)))
        n += 1
    return n


PACKETLOGGER_HEADER_RE = re.compile(
    r'\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\]'
)
PACKETLOGGER_HEXROW_RE = re.compile(
    r'^\s*\d+ \|((?:\s+[0-9A-Fa-f]{2}|\s+--){1,16})\s+\d+ \|', re.MULTILINE
)


def parse_packetlogger_log(text: str, opcode: str) -> list[tuple[str, str]]:
    """One opcode's raw hex dump, one block per observed packet: '[timestamp]' header (older
    PacketViewer captures) or '[timestamp] Packet 0xNNN' (newer PacketLogger captures -- the
    'Packet 0xNNN' suffix, when present, is ignored rather than parsed, since the file's OWN name
    is always the real opcode for either format and trusting one source is simpler than
    reconciling two that should never disagree within a single file anyway), then a 16-column hex
    grid (real row-labeled offsets, '--' padding on a short last row). Every opcode gets its own
    file, so this is the most complete real capture format available -- covers battle/item/shop/
    quest packets none of the other formats (idview/EventView/KITrack) ever touch, at the cost of
    needing packet_decode.py to make sense of the raw bytes (done lazily at view time, not here,
    since decoding tens of thousands of packets per capture up front would be slow for rows a
    user may never look at). Returns (ts, compact_hex) tuples in FILE order (this single opcode's
    own chronological order) -- the caller merges across all opcode files by real ts to get one
    true per-capture chronological sequence, something no other capture format here actually has
    (capture_events/eventview only have a per-format seq, not a shared clock)."""
    out = []
    headers = [(m.start(), m.end(), m.group(1)) for m in PACKETLOGGER_HEADER_RE.finditer(text)]
    for i, (hstart, hend, ts) in enumerate(headers):
        block_end = headers[i + 1][0] if i + 1 < len(headers) else len(text)
        block = text[hend:block_end]
        hex_bytes = []
        for rowmatch in PACKETLOGGER_HEXROW_RE.finditer(block):
            for tok in rowmatch.group(1).split():
                if tok != "--":
                    hex_bytes.append(tok)
        if hex_bytes:
            out.append((ts, "".join(hex_bytes)))
    return out


def ingest_packetlogger(con, capture_id, src: Source, relnames: list[str]) -> int:
    """Ingests every PacketLogger|PacketViewer/{incoming,outgoing}/0xNNN.log file for one capture
    into capture_raw_packets, one real chronological sequence merged across ALL opcodes by their
    real timestamps (see parse_packetlogger_log's own note on why this is the only format here
    with a true shared per-capture clock). direction is read off the file's own path
    (.../incoming/... or .../outgoing/...), opcode off the filename -- neither guessed. Handles
    both the newer 'PacketLogger' folder name (per-block 'Packet 0xNNN' header, redundant with
    the filename) and the older 'PacketViewer' folder name (bare '[timestamp]' header, no per-
    block opcode at all) -- confirmed 2026-09-04 that roughly half of all real captures in this
    corpus (45 of 84) predate PacketLogger and only have PacketViewer, so skipping this older
    format would have silently left over half the corpus with zero raw packet coverage."""
    all_packets = []
    for relname in relnames:
        direction = "incoming" if "/incoming/" in relname.lower() else (
            "outgoing" if "/outgoing/" in relname.lower() else "unknown")
        opcode = Path(relname).stem.upper()
        text = src.read_text(relname)
        for ts, hexstr in parse_packetlogger_log(text, opcode):
            all_packets.append((ts, direction, opcode, hexstr))

    all_packets.sort(key=lambda p: p[0])

    con.execute("DELETE FROM capture_raw_packets WHERE capture_id=?", (capture_id,))
    for seq, (ts, direction, opcode, hexstr) in enumerate(all_packets):
        con.execute("""INSERT OR REPLACE INTO capture_raw_packets
            (capture_id, seq, ts, direction, opcode, raw_hex) VALUES (?,?,?,?,?,?)""",
            (capture_id, seq, ts, direction, opcode, hexstr))
    return len(all_packets)


IDVIEW_EVENT_RE = re.compile(r'Event:\s*(0x[0-9A-Fa-f]+)')
IDVIEW_OPTION_RE = re.compile(r'Option:\s*(\d+)')
IDVIEW_MESSAGE_RE = re.compile(r'Message:\s*(\d+)')
IDVIEW_PARAMS_RE = re.compile(r'Params:\s*(.*)$')

# 2026-09-04: real SECOND idview/simple format found (confirmed against a real capture, id 52 --
# 0 capture_events rows despite genuinely rich source content) -- a different, newer idview tool
# version renders each packet as a multi-line block instead of format 1's single comma-joined
# line: 'INCOMING < CS Event + Params (0x034):  NPC: 16982179 (Sorrowful Sage)' followed by
# separate 'Event:'/'Params:'/'Option:'/'Message:' lines, blocks separated by a blank line. Same
# real facts, different rendering -- confirmed by comparing the SAME zone/NPC/CSID appearing in
# both a working format-1 capture (id 53, 'Wiggo Captures' folder name) and this format-2 one
# (id 52): format 1's 'Event: 0x0116' and format 2's 'Event: 278' are the same real CSID (278
# decimal == 0x116 hex) for the same NPC (Sorrowful Sage). Event is rendered in DECIMAL here
# (format 1 uses hex with a 0x prefix) -- normalized to the same '0xNNNN' hex string on insert so
# event_hex stays comparable across both formats' captures.
IDVIEW2_HEADER_RE = re.compile(
    r'^(INCOMING|OUTGOING)\s*[<>]\s*(.+?)\s*\((0x[0-9A-Fa-f]{3})\):\s*(.*)$', re.MULTILINE
)
IDVIEW2_EVENT_RE = re.compile(r'^Event:\s*(\d+)\s*$', re.MULTILINE)
IDVIEW2_OPTION_RE = re.compile(r'^Option:\s*(-?\d+)\s*$', re.MULTILINE)
IDVIEW2_MESSAGE_RE = re.compile(r'^Message:\s*(\d+)\s*$', re.MULTILINE)
IDVIEW2_PARAMS_RE = re.compile(r'^Params:\s*(.*)$', re.MULTILINE)


def ingest_idview_simple(con, capture_id, src: Source, relname: str) -> int:
    """idview/simple/<Zone>.log -- real, structured per-packet dialogue/CS-event data (Incoming/
    Outgoing, opcode, opcode name, NPC/Actor id+name, Event hex, Option, Message, or raw Params
    depending on packet type) from the older idview capture tool. No timestamps, but every entry
    is a real observed CS-event/dialogue packet -- exactly the "does this NPC really fire this
    CSID" and "what message id does this NPC really send" evidence this project has historically
    had to read out of raw hex dumps by hand. idview/raw carries the same facts plus a redundant
    hex dump; simple is parsed here since it already has everything structured.

    Two real rendering formats exist across the corpus (confirmed 2026-09-04, see IDVIEW2_* note
    above) -- detected from the file's own first non-blank line rather than assumed, so either
    real shape parses correctly instead of one silently returning zero rows."""
    zone_db = Path(relname).stem
    text = src.read_text(relname)

    first_line = next((l.strip() for l in text.splitlines() if l.strip()), "")
    if IDVIEW2_HEADER_RE.match(first_line):
        return _ingest_idview_simple_v2(con, capture_id, zone_db, text)

    n = 0
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        m = IDVIEW_LINE_RE.match(line)
        if not m:
            continue
        direction, opcode, opcode_name, rest = m.groups()

        entity_id = entity_name = None
        em = IDVIEW_ENTITY_RE.search(rest)
        if em:
            entity_id, entity_name = int(em.group(1)), em.group(2) or None

        event_m = IDVIEW_EVENT_RE.search(rest)
        event_hex = event_m.group(1) if event_m else None
        option_m = IDVIEW_OPTION_RE.search(rest)
        option = int(option_m.group(1)) if option_m else None
        message_m = IDVIEW_MESSAGE_RE.search(rest)
        message_id = int(message_m.group(1)) if message_m else None
        params_m = IDVIEW_PARAMS_RE.search(rest)
        params_raw = params_m.group(1).strip() if params_m else None

        con.execute("""INSERT OR REPLACE INTO capture_events
            (capture_id, zone_db, seq, direction, opcode, opcode_name, entity_id, entity_name,
             event_hex, option, message_id, params_raw)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (capture_id, zone_db, n, direction, opcode, opcode_name, entity_id, entity_name,
             event_hex, option, message_id, params_raw))
        n += 1

        if entity_id and entity_name:
            entity_profile.record_field(con, "npc", entity_id, "capture_name", "capture", entity_name)
    return n


def _ingest_idview_simple_v2(con, capture_id, zone_db, text: str) -> int:
    n = 0
    for block in re.split(r'\n\s*\n', text):
        block = block.strip()
        if not block:
            continue
        lines = block.splitlines()
        m = IDVIEW2_HEADER_RE.match(lines[0].strip())
        if not m:
            continue
        direction_word, opcode_name, opcode, header_rest = m.groups()
        direction = "Incoming" if direction_word == "INCOMING" else "Outgoing"

        entity_id = entity_name = None
        em = IDVIEW_ENTITY_RE.search(header_rest)
        if em:
            entity_id, entity_name = int(em.group(1)), em.group(2) or None

        body = "\n".join(lines[1:])
        event_m = IDVIEW2_EVENT_RE.search(body)
        event_hex = f"0x{int(event_m.group(1)):04X}" if event_m else None
        option_m = IDVIEW2_OPTION_RE.search(body)
        option = int(option_m.group(1)) if option_m else None
        message_m = IDVIEW2_MESSAGE_RE.search(body)
        message_id = int(message_m.group(1)) if message_m else None
        params_m = IDVIEW2_PARAMS_RE.search(body)
        params_raw = params_m.group(1).strip() if params_m else None

        con.execute("""INSERT OR REPLACE INTO capture_events
            (capture_id, zone_db, seq, direction, opcode, opcode_name, entity_id, entity_name,
             event_hex, option, message_id, params_raw)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (capture_id, zone_db, n, direction, opcode, opcode_name, entity_id, entity_name,
             event_hex, option, message_id, params_raw))
        n += 1

        if entity_id and entity_name:
            entity_profile.record_field(con, "npc", entity_id, "capture_name", "capture", entity_name)
    return n


def ingest_npclogger_lua(con, capture_id, src: Source, relname: str, leg: int = 1) -> tuple[int, int]:
    """Older capture tool format (idview/Wiggo-era) -- Npclogger/tables/<Zone>.lua, an append-log
    of raw entity-update packet snapshots (one line per observed update, same id repeated as it
    moves), NOT the newer NPCLogger.db SQLite format. No timestamps and no dedicated leg/history
    tables here, so every line becomes one capture_npc_path point in file order (a real, if
    coarser, position trace) and capture_npc_entries gets the LAST-seen values per id (INSERT OR
    REPLACE naturally keeps the latest since the file is append-ordered). No model_id or hpp
    field exists in this format -- left NULL rather than guessed.

    leg: capture_npc_path's real primary key is (capture_id, zone_db, entity_id, leg, step), and
    `step` restarts at 0 for every file processed here -- a real, confirmed second real source,
    'npclogger/database/<Zone>.lua' (a fuller entity census, distinct content from 'tables', not
    a duplicate -- confirmed 2026-09-05 on a real Bhaflau Remnants capture: 'database' had the
    Armoury Crate's real position, 'tables' didn't), would silently collide step-for-step with
    'tables' under the same leg and corrupt both traces via INSERT OR REPLACE. Callers processing
    more than one such file for the same zone_db MUST pass a distinct leg per file."""
    zone_db = Path(relname).stem
    text = src.read_text(relname)
    n_entries = n_path = 0
    seen_ids = set()
    for step, line in enumerate(text.splitlines()):
        m = NPCLOGGER_LUA_LINE_RE.match(line)
        if not m:
            continue
        entity_id = int(m.group(1))
        fields = {}
        for fm in NPCLOGGER_LUA_FIELD_RE.finditer(m.group(2)):
            key, str_val, num_val = fm.group(1), fm.group(2), fm.group(3)
            fields[key] = str_val if str_val is not None else float(num_val)
        if "x" not in fields or "z" not in fields:
            continue

        x, y, z = fields.get("x"), fields.get("y", 0.0), fields.get("z")
        dir_ = int(fields.get("r", 0))
        con.execute("""INSERT OR REPLACE INTO capture_npc_path
            (capture_id, zone_db, entity_id, leg, step, x, y, z, dir, delta)
            VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (capture_id, zone_db, entity_id, leg, step, x, y, z, dir_, 0))
        n_path += 1

        con.execute("""INSERT OR REPLACE INTO capture_npc_entries
            (capture_id, zone_db, entity_id, name, model_id, x, y, z, dir, hpp,
             legacy_flags, legacy_status, legacy_animation, speed, created_at, updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (capture_id, zone_db, entity_id, fields.get("name"), None, x, y, z, dir_, None,
             int(fields.get("flags", 0)), int(fields.get("status", 0)),
             int(fields.get("animation", 0)), int(fields.get("speed", 0)), None, None))
        if entity_id not in seen_ids:
            seen_ids.add(entity_id)
            n_entries += 1
            record_entity_facts(con, entity_id, fields.get("name"), None, x, y, z, None, zone_db)

    return n_entries, n_path


CONTENT_TYPES = ("instances", "overworld", "unclassified")
LABEL_MISSION_RE = re.compile(r'^.+?\s-\s(.+?)\s*\(')  # "<Zone> - <Mission> (Thris Nov2025)"


def resolve_mission_name(con, label: str) -> str | None:
    """Best-effort match of a capture's filename against assault_missions.name -- exact match on
    the parsed segment first, substring fallback. Returns None rather than guessing when neither
    matches; a capture is allowed to have no resolved mission (e.g. content_type != assault, or a
    label that doesn't follow the "<Zone> - <Mission> (...)" convention)."""
    m = LABEL_MISSION_RE.match(label)
    guess = m.group(1).strip() if m else label
    row = con.execute("SELECT name FROM assault_missions WHERE name = ?", (guess,)).fetchone()
    if row:
        return row[0]
    row = con.execute("SELECT name FROM assault_missions WHERE name LIKE ?", (f"%{guess}%",)).fetchone()
    return row[0] if row else None


def list_top_level_dirs(path_str: str) -> list[str]:
    """Real top-level directory names inside a folder or zip -- used to detect a "batch" bundle
    (many separate capture sessions zipped together under one folder each, e.g. blitz_1, blitz_2,
    ...) versus a normal single-capture bundle."""
    src = Source(Path(path_str))
    try:
        return sorted({n.split("/")[0] for n in src._names if n.strip("/")})
    finally:
        src.close()


def ingest(con, path_str: str, content_type: str = "instances", subroot: str | None = None,
           mission_name_override: str | None = None) -> int:
    """content_type tags what kind of content this capture is FROM, not just where the file
    happens to live -- explicit and stored per-row rather than assumed from folder structure, so
    a future non-Assault capture (regular field mobs, Dynamis, whatever) ingested into the same
    tables can never get silently treated as instanced-mission data just because that's the only
    kind that existed when this tool was first built. "instances" (renamed from "assault"
    2026-09-04) deliberately covers more than just Assault -- Nyzul Isle, Salvage, and any other
    real instance-based mission type the corpus grows to include, not just the 50 Assault
    missions specifically. Default stays "instances" only because every capture on disk right now
    IS instanced-mission content -- pass --content-type explicitly for anything else (e.g.
    "overworld" for regular field captures).

    subroot: when a bundle is really many separate capture sessions zipped under one top-level
    folder each (real example: Blitzkrieg.zip holds 14 independently-named attempts, blitz_1
    through blitz_14, each a full capturer folder) -- ingest one subroot as its own capture row
    rather than merging every session's entities into one fictitious combined capture. See
    ingest_batch() below, which discovers subroots and calls this once per one.
    mission_name_override: set explicitly when the real mission is known (confirmed against
    assault_missions' own zone text) but the source filename/subroot name doesn't match the
    "<Zone> - <Mission> (...)" pattern resolve_mission_name() expects -- never guessed."""
    path = Path(path_str)
    if not path.exists():
        raise SystemExit(f"not found: {path}")
    src = Source(path)
    try:
        source_path = f"{path}::{subroot}" if subroot else str(path)
        existing = con.execute("SELECT capture_id FROM captures WHERE source_path=?",
                                (source_path,)).fetchone()
        if existing:
            print(f"already ingested as capture_id={existing[0]} ({path.name}"
                  f"{f'::{subroot}' if subroot else ''}) -- skipping. "
                  f"Delete its rows first if you want to re-ingest.")
            return existing[0]

        def sfind(pattern):
            hits = src.find(pattern)
            return hits if subroot is None else [h for h in hits if h.startswith(subroot + "/")]

        manifest_hits = sfind(r'manifest\.txt$')
        meta = {}
        capturer = None
        if manifest_hits:
            meta = parse_manifest(src.read_text(manifest_hits[0]))
            manifest_parts = manifest_hits[0].split("/")
            # manifest.txt sometimes sits at the bundle root with no wrapping capturer folder --
            # only trust a parent segment as the capturer name when one actually exists.
            capturer = manifest_parts[-2] if len(manifest_parts) >= 2 else None

        label = f"{path.stem} :: {subroot}" if subroot else path.stem
        if mission_name_override:
            mission_name = mission_name_override
        elif content_type == "instances":
            # resolve_mission_name only matches against the real 50-entry assault_missions
            # table -- a genuine no-op (mission_name stays None) for Nyzul/Salvage/any other
            # real instance type "instances" now also covers, not an error.
            mission_name = resolve_mission_name(con, subroot or path.stem)
        else:
            mission_name = None

        cur = con.execute("""INSERT INTO captures
            (source_path, capturer, capture_label, content_type, mission_name, addons,
             client_build, is_retail, start_time)
            VALUES (?,?,?,?,?,?,?,?,?)""",
            (source_path, capturer, label, content_type, mission_name,
             json.dumps(meta.get("addons", [])), meta.get("client_build"),
             int(bool(meta.get("is_retail"))) if meta.get("is_retail") is not None else None,
             meta.get("start_time")))
        capture_id = cur.lastrowid

        counts = ingest_from_source(con, capture_id, src, subroot=subroot)
        recompute_zones(con, capture_id)

        con.commit()
        zones = json.loads(con.execute("SELECT zones FROM captures WHERE capture_id=?", (capture_id,)).fetchone()[0] or "[]")
        print(f"[{capture_id}] {label}: {counts['npc_entries']} npc entries, {counts['npc_hist']} history "
              f"deltas, {counts['path']} path points, {counts['actions']} actions, {counts['hp']} hp events, "
              f"{counts['events']} idview events, {counts['ki']} ki events, {counts['eventview']} eventview packets, "
              f"{counts['level_range']} level-range entries, {counts['attack_delay']} attack-delay entries -- "
              f"content_type={content_type} zones={zones} mission={mission_name!r} "
              f"(capturer={capturer}, build={meta.get('client_build', '?')!r})")
        return capture_id
    finally:
        src.close()


def ingest_from_source(con, capture_id, src: "Source", subroot: str | None = None,
                        file_results: list[dict] | None = None) -> dict:
    """Runs every known bundle-format ingester (NPCLogger, ActionView, PathLog, HPTrack, idview,
    KITrack, EventView, LevelRangeTrack, AttackDelay, and the older Npclogger/tables/*.lua
    fallback) against one Source, into one existing capture_id. Factored out of ingest() so the
    same dispatch logic can also run when a zip gets uploaded onto an already-existing (manually
    created) capture via the GUI, not just at capture-creation time.

    file_results, when passed, is appended in place with one {"filename", "rows", "error"} dict
    per real file the Source contains: "error": None for a file that matched a known format and
    ingested cleanly, a real exception message for one that matched but the ingester itself threw
    (a corrupt/truncated log shouldn't silently abort the whole bundle -- every OTHER recognized
    file in it still gets ingested), and "not a recognized capture-log format" for a file that
    matched none of the patterns below at all. This is what lets the GUI's Add Files page show a
    real per-file pass/fail breakdown instead of one opaque bundle-wide row."""
    def sfind(pattern):
        hits = src.find(pattern)
        return hits if subroot is None else [h for h in hits if h.startswith(subroot + "/")]

    matched_names: set[str] = set()

    def run1(relname, fn, *args):
        """For an ingester returning a single row count."""
        matched_names.add(relname)
        try:
            rows = fn(*args)
        except Exception as ex:
            if file_results is not None:
                file_results.append({"filename": relname, "rows": 0, "error": str(ex)})
            return 0
        if file_results is not None:
            file_results.append({"filename": relname, "rows": rows, "error": None})
        return rows

    def run2(relname, fn, *args):
        """For an ingester returning a (a, b) row-count tuple."""
        matched_names.add(relname)
        try:
            a, b = fn(*args)
        except Exception as ex:
            if file_results is not None:
                file_results.append({"filename": relname, "rows": 0, "error": str(ex)})
            return 0, 0
        if file_results is not None:
            file_results.append({"filename": relname, "rows": a + b, "error": None})
        return a, b

    def run3(relname, fn, *args):
        """For an ingester returning an (a, b, c) row-count tuple."""
        matched_names.add(relname)
        try:
            a, b, c = fn(*args)
        except Exception as ex:
            if file_results is not None:
                file_results.append({"filename": relname, "rows": 0, "error": str(ex)})
            return 0, 0, 0
        if file_results is not None:
            file_results.append({"filename": relname, "rows": a + b + c, "error": None})
        return a, b, c

    def run4(relname, fn, *args):
        """For an ingester returning an (a, b, c, d) row-count tuple."""
        matched_names.add(relname)
        try:
            a, b, c, d = fn(*args)
        except Exception as ex:
            if file_results is not None:
                file_results.append({"filename": relname, "rows": 0, "error": str(ex)})
            return 0, 0, 0, 0
        if file_results is not None:
            file_results.append({"filename": relname, "rows": a + b + c + d, "error": None})
        return a, b, c, d

    counts = {"npc_entries": 0, "npc_hist": 0, "actions": 0, "path": 0, "hp": 0, "events": 0,
              "ki": 0, "eventview": 0, "level_range": 0, "attack_delay": 0, "raw_packets": 0,
              "pc_path": 0, "widescan": 0, "caplog_chat": 0}
    npc_db_files = sfind(r'NPCLogger/[^/]+\.db$')
    for relname in npc_db_files:
        e, h = run2(relname, ingest_npc_db, con, capture_id, src, relname)
        counts["npc_entries"] += e
        counts["npc_hist"] += h
    actionview_db_files = sfind(ACTIONVIEW_DB_RE.pattern)
    for relname in actionview_db_files:
        counts["actions"] += run1(relname, ingest_actions_db, con, capture_id, src, relname)
    if not actionview_db_files:
        # ActionView/simple/<Zone>.log is a real but STRICTLY REDUNDANT text rendering of the same
        # rows already in ActionView/*/Actions.db when both exist in a capture (confirmed 2026-09-05:
        # every ability use in Ilrusi Atoll - Bellerophon's Bliss's simple.log matches an existing
        # db row for the same actor/ability/category/animation/message) -- ingesting both would
        # double-count real actions under separate action_keys. Only fall back to the text log when
        # no .db was found, same gating pattern as the npclogger_lua fallback below.
        for relname in sfind(r'[Aa]ctionview/simple/[^/]+\.log$'):
            counts["actions"] += run1(relname, ingest_actionview_simple, con, capture_id, src, relname)
    for relname in sfind(r'PathLog/.+/\d+\.csv$'):
        counts["path"] += run1(relname, ingest_pathlog, con, capture_id, src, relname)
    for relname in sfind(r'PathLog/[^/]+/PC_[^/]+\.csv$'):
        counts["pc_path"] += run1(relname, ingest_pc_pathlog, con, capture_id, src, relname)
    for relname in sfind(r'[Nn]pclogger/widescan/[^/]+\.log$'):
        counts["widescan"] += run1(relname, ingest_widescan, con, capture_id, src, relname)
    for relname in sfind(r'HPTrack/.+\.log$'):
        counts["hp"] += run1(relname, ingest_hptrack, con, capture_id, src, relname)
    for relname in sfind(r'[Ii]dview/simple/[^/]+\.log$'):
        counts["events"] += run1(relname, ingest_idview_simple, con, capture_id, src, relname)
    # 2026-09-05: real Wiggo/capture-lib-era captures (e.g. Blitzkrieg.zip) use a folder literally
    # named "eventview/simple/<Zone>.log" for the EXACT SAME block-per-blank-line
    # "INCOMING < ... (0xNNN): NPC: id (name)" / Event: / Params: / Option: / Message: text shape
    # idview/simple's format-2 already parses -- confirmed by direct content inspection, not
    # assumed from the name. There's also a combined top-level "eventview/simple.log" per capturer
    # (all zones concatenated) -- confirmed it is NOT a strict subset of the per-zone files (it
    # carries real records for an earlier zone the capturer passed through, e.g. an event tied to
    # "Runic Seal" absent from the per-zone Mamool Ja Training Grounds.log). Deliberately NOT
    # ingesting that combined file: ingest_idview_simple keys zone_db off the filename stem, and
    # "simple.log" has no real zone name to attach to its rows -- tagging it with a guessed/blank
    # zone_db would be fabricating data per [[topaz_never_fabricate_ids]]'s discipline. The
    # per-zone files are ingested per capture instead; any capture whose only per-zone eventview
    # data predates its first per-zone split stays a real, visible gap rather than a silently wrong
    # zone_db.
    # 2026-09-06: real Foxmulder-capturer capture (Bhaflau Remnants) nests this one folder deeper
    # than the pattern used to require -- eventview/<capturer>/simple/<zone>.log instead of the
    # capturer-less eventview/simple/<zone>.log -- same real per-capturer nesting the
    # npclogger/(capturer)/tables fix below already handles. The bare capturer-less form stays
    # matched too (empty optional group).
    for relname in sfind(r'[Ee]ventview/(?:[^/]+/)?simple/[^/]+\.log$'):
        counts["events"] += run1(relname, ingest_idview_simple, con, capture_id, src, relname)
    for relname in sfind(r'KITrack/.+\.log$'):
        counts["ki"] += run1(relname, ingest_kitrack, con, capture_id, src, relname)
    # 2026-09-08: real bug -- this only ever matched a literal lowercase "caplog" folder and a
    # ".txt" extension. A real, separate capturer ("Thris", 88 real captures sampled) uses a
    # titlecase "CapLog" folder with a ".log" extension instead -- same real underlying tool
    # family (see ingest_caplog's own docstring on the [EView] variant), just different real
    # casing/extension, confirmed by direct content inspection of multiple real Thris captures.
    for relname in sfind(r'[Cc]ap[Ll]og/[^/]+\.(?:txt|log)$'):
        events_n, hp_n, eview_n, chat_n = run4(relname, ingest_caplog, con, capture_id, src, relname)
        counts["events"] += events_n
        counts["hp"] += hp_n
        counts["eventview"] += eview_n
        counts["caplog_chat"] += chat_n
    # 2026-09-08: real bug -- this pattern (EventView/<capturer>/<Zone>.log) and the idview/simple
    # pattern above (eventview/(?:<capturer>/)?simple/<Zone>.log) both have exactly 2 path segments
    # after "eventview/", so this one was ALSO matching eventview/simple/<Zone>.log and
    # eventview/raw/<Zone>.log (treating "simple"/"raw" as if they were a capturer name), silently
    # double-processing the same file through the wrong parser -- confirmed live: a real Tacocat
    # capture (Arrapago Remnants) had its real 74-row eventview/simple/<Zone>.log ingested correctly
    # once via ingest_idview_simple, then a SECOND time via ingest_eventview (which doesn't
    # understand idview's plain-text format and silently returns 0), showing as a confusing
    # duplicate "0 rows" row right after the real "74 rows" one for the exact same file. Excluding
    # the two reserved subfolder names here (already claimed by more specific patterns above) fixes
    # it without narrowing this pattern's real intended match (a capturer name is never literally
    # "simple" or "raw" in any real sample seen).
    for relname in sfind(r'[Ee]ventview/(?!(?:[Ss]imple|[Rr]aw)/)[^/]+/[^/]+\.log$'):
        counts["eventview"] += run1(relname, ingest_eventview, con, capture_id, src, relname)
    for relname in sfind(r'LevelRangeTrack/[^/]+\.db$'):
        counts["level_range"] += run1(relname, ingest_level_range_db, con, capture_id, src, relname)
    for relname in sfind(r'AttackDelay/[^/]+\.log$'):
        counts["attack_delay"] += run1(relname, ingest_attackdelay, con, capture_id, src, relname)
    pl_files = sfind(r'Packet(?:Logger|Viewer)/(incoming|outgoing)/0x[0-9A-Fa-f]{3}\.log$')
    if pl_files:
        matched_names.update(pl_files)
        try:
            pl_rows = ingest_packetlogger(con, capture_id, src, pl_files)
        except Exception as ex:
            pl_rows = 0
            if file_results is not None:
                for relname in pl_files:
                    file_results.append({"filename": relname, "rows": 0, "error": str(ex)})
        else:
            if file_results is not None:
                # One combined call across every raw-packet-log file -- rows aren't attributable
                # to any single file, so report the real total once (against the first file) and
                # the rest as "ok" with no per-file row count, rather than fabricating a split.
                for i, relname in enumerate(pl_files):
                    file_results.append({"filename": relname, "rows": pl_rows if i == 0 else None, "error": None})
        counts["raw_packets"] += pl_rows
    if not npc_db_files:
        # No NPCLogger.db in this bundle -- fall back to the older Npclogger/tables/<Zone>.lua
        # append-log format (idview/Wiggo-era captures). Gated on the newer format's absence so a
        # mixed bundle never has thinner lua-table data overwrite richer SQLite data.
        # Pattern allows an optional capturer-name folder between npclogger/ and tables/ --
        # confirmed real 2026-09-05: some captures nest it there (npclogger/<capturer>/tables/...)
        # instead of at the capture root, which the old capturer-less-only pattern silently missed
        # (a real Bhaflau Remnants capture ingested 0 npc entries because of exactly this).
        for relname in sfind(r'[Nn]pclogger/(?:[^/]+/)?tables/[^/]+\.lua$'):
            e, p = run2(relname, ingest_npclogger_lua, con, capture_id, src, relname, 1)
            counts["npc_entries"] += e
            counts["path"] += p
        # npclogger/database/<Zone>.lua -- same real lua-table-literal format, but a genuinely
        # DIFFERENT real snapshot (confirmed 2026-09-05: real Bhaflau Remnants capture's
        # 'database' file had the Armoury Crate's real position, entirely absent from that same
        # capture's 'tables' file) -- not a duplicate to skip. leg=2 keeps its path points from
        # colliding step-for-step with 'tables' under the same (capture_id, zone_db, entity_id,
        # leg, step) primary key (see ingest_npclogger_lua's leg param docstring).
        for relname in sfind(r'[Nn]pclogger/(?:[^/]+/)?database/[^/]+\.lua$'):
            e, p = run2(relname, ingest_npclogger_lua, con, capture_id, src, relname, 2)
            counts["npc_entries"] += e
            counts["path"] += p

    # The tools that write NPCLogger/ActionView/EventView bundles also write their own redundant
    # secondary views alongside the real per-event data those tools' primary format already
    # ingests above -- confirmed by direct content inspection, not assumed (2026-09-06, real
    # Bhaflau Remnants/Foxmulder capture): each of these three carries EXACTLY the same real
    # entries/events as a sibling file already ingested above, just rendered differently, so
    # there's no new data to extract. Recognized here (rather than falling through to "not a
    # recognized capture-log format" below) so Add Files doesn't report a false failure for a file
    # that was correctly read and correctly found to add nothing new.
    for relname in (
        sfind(r'[Aa]ctionview/category/[^/]+\.lua$')      # static ability id->name/animation/message
        + sfind(r'[Aa]ctionview/zone/[^/]+\.lua$')          # catalog ActionView writes locally --
        # ^ per-mob dedup of moves seen, redundant with actionview/simple's real per-use rows
        + sfind(r'[Ee]ventview/(?:[^/]+/)?raw/[^/]+\.log$')  # same events as the simple/ sibling
        # ^ above, plus a raw packet hex dump -- no additional real data
        # Capturer folder made optional (2026-09-08, real Tacocat-capturer capture:
        # npclogger/logs/<Zone>.log with no capturer folder between npclogger/ and logs/) --
        # mirrors the same real fix tables/database already got above for the identical reason.
        + sfind(r'[Nn]pclogger/(?:[^/]+/)?logs/[^/]+\.log$')  # human-readable rendering of the SAME
        # ^ NPC entries already in this capturer's tables/ or database/ .lua sibling
        # 2026-09-08, real Tacocat-capturer capture (Leujaoam Sanctum): eventview/raw.log and
        # eventview/simple.log (bare, directly under eventview/ or eventview/<capturer>/ -- NOT
        # the per-zone eventview/.../raw/<zone>.log / .../simple/<zone>.log already ingested above)
        # are a whole-SESSION combined dump, confirmed by real content inspection to carry real
        # records this capture's per-zone split doesn't have (e.g. an event tied to an earlier zone
        # the capturer passed through). Genuinely NOT ingested -- same reasoning as
        # ingest_idview_simple's own note a few lines up about the analogous combined
        # eventview/simple.log: there's no real zone_db to attach these whole-session rows to, and
        # guessing one would be fabricating data per this project's standing
        # never-fabricate-ids rule. Recognized here so it reports "ok, not ingested" instead of a
        # false "not a recognized capture-log format" failure -- the exclusion is deliberate, not
        # a coverage gap.
        + sfind(r'[Ee]ventview/(?:[^/]+/)?(?:raw|simple)\.log$')
        # 2026-09-08, same real Tacocat capture: packetviewer/full.log, incoming.log, outgoing.log
        # (bare, directly under packetviewer/) are a whole-session concatenation of the exact same
        # packets already ingested per-opcode from packetviewer/incoming/0x*.log and
        # packetviewer/outgoing/0x*.log (confirmed live: this capture had both packetviewer/incoming/
        # with 63 real per-opcode files AND this flat incoming.log side by side) -- redundant, not
        # new data, same bucket as the actionview/npclogger redundant views above.
        + sfind(r'[Pp]acket(?:[Ll]ogger|[Vv]iewer)/(?:full|incoming|outgoing)\.log$')
    ):
        matched_names.add(relname)
        if file_results is not None:
            file_results.append({"filename": relname, "rows": 0, "error": None})

    if file_results is not None:
        # Real files present in the bundle that no pattern above ever looked at -- a capture-log
        # format this toolkit doesn't recognize, or a genuinely unrelated file that got swept up
        # in the upload. Known-benign non-data files (manifest.txt, OS-generated cruft) are
        # reported "ok, not data" rather than "failed", since neither is a real import problem.
        BENIGN_BASENAMES = {"manifest.txt", "thumbs.db", "desktop.ini", ".ds_store"}
        for relname in sorted(src.list_files() if subroot is None
                               else [n for n in src.list_files() if n.startswith(subroot + "/")]):
            if relname in matched_names:
                continue
            basename = relname.rsplit("/", 1)[-1].lower()
            if basename in BENIGN_BASENAMES:
                file_results.append({"filename": relname, "rows": 0, "error": None})
            else:
                # 2026-09-08: a path that matches no known pattern above is ambiguous between two
                # very different real causes -- "a genuinely new capture-tool format/layout this
                # toolkit has never seen" vs "a real, already-supported format whose CONTENT this
                # toolkit would recognize, just sitting at a folder depth/name none of the path
                # patterns above anticipated" (exactly what happened to npclogger/logs/ before this
                # same session's fix -- real npclogger content, wrong-shaped path). Sniffing the
                # file's own content against each known parser's real signature (deliberately not
                # attempting to actually ingest it this way -- the file's path is often the ONLY
                # source for context a parser needs, like which zone a per-zone log belongs to, and
                # guessing that from content alone risks fabricating an attribution per this
                # project's standing never-fabricate-ids rule) turns a bare "not recognized" into
                # an actionable "this looks like a real <format>, the path pattern needs updating"
                # -- much faster to diagnose than re-deriving it from scratch next time, the same
                # gap this whole test/fixture effort is about closing.
                guess = _sniff_known_format(src, relname)
                error = "not a recognized capture-log format"
                if guess:
                    # Deliberately doesn't claim an existing path pattern just needs updating --
                    # true for a format like NPCLogger that IS ingested elsewhere under a
                    # different path shape, but false for a format like CapLog that has no
                    # ingestion support at all yet (confirmed real gap, not a path mismatch).
                    # Both cases get the same actionable next step either way.
                    error += (f" (content looks like a real {guess} file -- may need a parser "
                               f"added, or an existing one's path pattern updated to match this "
                               f"layout)")
                file_results.append({"filename": relname, "rows": 0, "error": error})
    return counts


def _sniff_known_format(src: "Source", relname: str) -> str | None:
    """Best-effort content-only guess at which KNOWN real format an unmatched file's content
    resembles -- deliberately conservative (checks a handful of already-proven, distinctive real
    line shapes reused directly from each format's own real parser/regex above, not a broad
    heuristic classifier) and deliberately NEVER used to actually ingest data, only to make an
    unrecognized-path failure more actionable. Returns None (not a guess) for anything binary,
    unreadable, or that doesn't clearly match one of these signatures."""
    try:
        text = src.read_text(relname)
    except Exception:
        return None
    sample = text[:4000]

    if NPCLOGGER_LUA_LINE_RE.search(sample):
        return "NPCLogger table/database Lua"
    if IDVIEW_LINE_RE.search(sample) or EVENTVIEW_HEADER_RE.search(sample):
        return "EventView/IDView packet log"
    if HP_LINE_RE.search(sample):
        return "HPTrack"
    if KI_HEADER_RE.search(sample):
        return "KITrack"
    if PACKETLOGGER_HEXROW_RE.search(sample):
        return "PacketLogger/PacketViewer raw hex dump"
    if re.search(r'^\[\d{2}:\d{2}:\d{2}\]\s+\[Capture\]', sample, re.MULTILINE):
        return "CapLog"
    return None


# Every real table keyed by capture_id -- kept as one list so delete_capture() can never miss one
# as new tables get added (a table added to init_db() but forgotten here would leave orphaned rows
# behind on every future delete, silently). Deliberately NOT derived by introspecting sqlite_master
# for tables with a capture_id column: several real tables (capture_source_files, capture_tags)
# have no data-quality reason to auto-discover, and an explicit list is easier to audit against
# init_db() by eye than trusting a DB introspection query to get it right.
CAPTURE_CHILD_TABLES = [
    "capture_npc_entries", "capture_npc_history", "capture_npc_path", "capture_actions",
    "capture_hp_events", "capture_events", "capture_ki_events", "capture_eventview",
    "capture_level_range", "capture_attack_delay", "capture_pc_path", "capture_source_files",
    "capture_raw_packets", "capture_tags", "capture_caplog_chat",
]


def delete_capture(con, capture_id: int) -> dict:
    """Permanently removes one capture and every real row it owns across every child table --
    there is no soft-delete/undo, so the GUI route gates this behind an explicit confirm page
    rather than a single click. Returns {table: rows_deleted} for whatever confirmation message
    the caller wants to show."""
    counts = {}
    for t in CAPTURE_CHILD_TABLES:
        cur = con.execute(f"DELETE FROM {t} WHERE capture_id=?", (capture_id,))
        counts[t] = cur.rowcount
    cur = con.execute("DELETE FROM captures WHERE capture_id=?", (capture_id,))
    counts["captures"] = cur.rowcount
    con.commit()
    return counts


def recompute_zones(con, capture_id: int):
    zones = [r[0] for r in con.execute(
        "SELECT DISTINCT zone_db FROM capture_npc_entries WHERE capture_id=? ORDER BY 1",
        (capture_id,))]
    con.execute("UPDATE captures SET zones=? WHERE capture_id=?", (json.dumps(zones), capture_id))
    con.commit()


def ingest_batch(con, path_str: str, content_type: str = "instances",
                  mission_name_override: str | None = None) -> list[int]:
    """One capture per top-level subfolder in a bundle (see ingest()'s subroot docstring) --
    real example: Blitzkrieg.zip's 14 separately-named attempts."""
    subroots = list_top_level_dirs(path_str)
    print(f"{Path(path_str).name}: {len(subroots)} subfolder(s) -- ingesting each as its own capture")
    ids = []
    for sub in subroots:
        try:
            ids.append(ingest(con, path_str, content_type=content_type, subroot=sub,
                               mission_name_override=mission_name_override))
        except Exception as ex:
            print(f"  FAILED {sub}: {ex}")
    return ids


def ingest_all(con, dir_str: str, pattern: str, content_type: str = "instances"):
    d = Path(dir_str)
    zips = sorted(d.rglob(pattern))
    if not zips:
        print(f"no files matching {pattern!r} under {d}")
        return
    print(f"found {len(zips)} capture file(s) under {d}")
    for z in zips:
        try:
            ingest(con, str(z), content_type=content_type)
        except Exception as ex:
            print(f"  FAILED {z.name}: {ex}")


def cmd_list(con, content_type: str | None = None):
    q = """SELECT c.capture_id, c.capture_label, c.content_type, c.zones, c.mission_name,
                  (SELECT COUNT(*) FROM capture_npc_entries WHERE capture_id=c.capture_id) AS n_npc,
                  (SELECT COUNT(*) FROM capture_npc_history WHERE capture_id=c.capture_id) AS n_hist
           FROM captures c"""
    params = ()
    if content_type:
        q += " WHERE c.content_type=?"
        params = (content_type,)
    q += " ORDER BY c.content_type, c.capture_id"
    rows = con.execute(q, params).fetchall()
    if not rows:
        print("(no captures ingested yet)")
        return
    for r in rows:
        zones = ",".join(json.loads(r[3])) if r[3] else "?"
        print(f"[{r[0]:>3}] {r[1]:<50} type={(r[2] or '?'):<14} zones={zones:<28} "
              f"mission={r[4] or '(unresolved)':<28} npc={r[5]:<4} history={r[6]}")


def get_entity_path(con, capture_id: int, entity_id: int) -> list[tuple]:
    """Real (x, z, t) points for one entity in one capture, for plotting -- capture_npc_path
    (PathLog's purpose-built leg/x/y/z/dir trace) when present, since it's cleaner than
    reconstructing motion from state deltas; falls back to capture_npc_history's raw x/y/z deltas
    (present on the *other* zone's NPCLogger.db in a capture, or when PathLog didn't cover this
    entity) otherwise. x/z are the ground-plane axes FFXI actually plots on a 2D map; y is height.
    """
    rows = con.execute(
        """SELECT x, z, step FROM capture_npc_path
           WHERE capture_id=? AND entity_id=? ORDER BY step""",
        (capture_id, entity_id)).fetchall()
    if rows:
        return [(x, z, i) for x, z, i in rows]

    rows = con.execute(
        """SELECT delta_json, ts FROM capture_npc_history
           WHERE capture_id=? AND entity_id=? ORDER BY seq""",
        (capture_id, entity_id)).fetchall()
    points = []
    for delta_json, ts in rows:
        try:
            d = json.loads(delta_json)
        except (TypeError, ValueError):
            continue
        if "x" in d and "z" in d:
            points.append((d["x"], d["z"], ts))
    return points


def get_pc_path(con, capture_id: int, zone_db: str) -> list[tuple]:
    """Real (x, z, t) points for the CAPTURING CHARACTER's own trace in one zone of one capture
    (capture_pc_path, from PathLog/.../PC_<Zone>.csv -- see ingest_pc_pathlog). Same (x,z,step)
    shape as get_entity_path so it can reuse the same plotting routes/templates, just keyed by
    zone_db instead of entity_id since there's no real NPC/entity id for the capturer here."""
    rows = con.execute(
        """SELECT x, z, step FROM capture_pc_path
           WHERE capture_id=? AND zone_db=? ORDER BY step""",
        (capture_id, zone_db)).fetchall()
    return [(x, z, i) for x, z, i in rows]


def get_pc_path_zones(con, capture_id: int) -> list[str]:
    """Distinct zone_db values this capture has a real PC path for."""
    rows = con.execute(
        "SELECT DISTINCT zone_db FROM capture_pc_path WHERE capture_id=? ORDER BY zone_db",
        (capture_id,)).fetchall()
    return [r[0] for r in rows]


def get_capture_entity_ids_with_path(con, capture_id: int, zone_db: str | None = None) -> list[tuple[int, str | None]]:
    """Every (entity_id, name) in this capture that has real path data (capture_npc_path or
    capture_npc_history with x/z), for a multi-entity plot -- an entity with only a single
    NPCLogger snapshot row and no path/history still gets included (a lone point is a real,
    if minimal, position sample), a pure name-only/no-position row does not."""
    q = """SELECT DISTINCT e.entity_id, e.name FROM capture_npc_entries e
           WHERE e.capture_id=? AND (
               EXISTS (SELECT 1 FROM capture_npc_path p WHERE p.capture_id=e.capture_id AND p.entity_id=e.entity_id)
               OR EXISTS (SELECT 1 FROM capture_npc_history h WHERE h.capture_id=e.capture_id AND h.entity_id=e.entity_id)
               OR (e.x IS NOT NULL AND e.z IS NOT NULL)
           )"""
    params = [capture_id]
    if zone_db:
        q += " AND e.zone_db=?"
        params.append(zone_db)
    q += " ORDER BY e.entity_id"
    return con.execute(q, params).fetchall()


def cmd_show(con, capture_id: int):
    row = con.execute("SELECT * FROM captures WHERE capture_id=?", (capture_id,)).fetchone()
    if not row:
        print("no such capture_id")
        return
    cols = [d[0] for d in con.execute("SELECT * FROM captures WHERE capture_id=?", (capture_id,)).description]
    for c, v in zip(cols, row):
        print(f"  {c}: {v}")
    print("\nNPC entries (top 15 by name):")
    for r in con.execute("""SELECT entity_id, name, model_id, x, y, z, hpp, zone_db
                             FROM capture_npc_entries WHERE capture_id=? ORDER BY name LIMIT 15""",
                          (capture_id,)):
        eid, name, model_id, x, y, z, hpp, zone_db = r
        pos = f"({x:.1f},{y:.1f},{z:.1f})" if x is not None else "(?)"
        print(f"  {eid:>10}  {(name or '?'):<20} model={model_id if model_id is not None else '?':<6} "
              f"pos={pos} hp%={hpp if hpp is not None else '?':<4} zone_db={zone_db}")
    n = con.execute("SELECT COUNT(*) FROM capture_npc_entries WHERE capture_id=?", (capture_id,)).fetchone()[0]
    if n > 15:
        print(f"  ... and {n - 15} more")


def backfill_npc_fields(con):
    """Populates capture_npc_entries.legacy_look plus the door_id/act_index/flags0-3/legacy_flag/
    sub_kind columns for every already-ingested capture whose real source zip/folder is still on
    disk, without a full re-ingest -- same pattern used for KITrack/EventView/LevelRangeTrack/
    AttackDelay when those were added after captures already existed. Skips captures with no
    NPCLogger.db (the older idview/Wiggo-era format never had any of these fields -- not a gap to
    backfill, a real absence) and captures whose source file has since moved/been deleted
    (reported, not treated as an error worth stopping the run over)."""
    rows = con.execute("SELECT capture_id, source_path FROM captures").fetchall()
    n_captures = n_updated_total = 0
    for capture_id, source_path in rows:
        if not source_path or source_path.startswith("manual://"):
            continue
        # Multi-session bundles (ingest_batch) store "<real path>::<subroot>" -- see the same
        # convention at the source_path = f"{path}::{subroot}" line elsewhere in this file.
        real_path, sep, subroot = source_path.partition("::")
        p = Path(real_path)
        if not p.exists():
            print(f"  capture #{capture_id}: source not found on disk ({real_path}) -- skipped")
            continue
        src = Source(p)
        try:
            def sfind(pattern, _subroot=(subroot if sep else None)):
                hits = src.find(pattern)
                return hits if _subroot is None else [h for h in hits if h.startswith(_subroot + "/")]
            npc_db_files = sfind(r'NPCLogger/[^/]+\.db$')
            if not npc_db_files:
                continue
            n_updated = 0
            for relname in npc_db_files:
                zone_db = Path(relname).stem
                sub, tmp_path = src.open_sqlite(relname)
                try:
                    cols = {r[1] for r in sub.execute("PRAGMA table_info(entries)")}
                    if "UniqueNo" not in cols:
                        continue
                    select_cols = ["UniqueNo"]
                    for c in ("legacy_look", "DoorId", "ActIndex", "Flags0", "Flags1", "Flags2",
                              "Flags3", "legacy_flag", "SubKind"):
                        select_cols.append(c if c in cols else "NULL")
                    sql = f"SELECT {', '.join(select_cols)} FROM entries"
                    for (uid, look, door_id, act_index, flags0, flags1, flags2, flags3,
                         legacy_flag, sub_kind) in sub.execute(sql):
                        try:
                            uid = int(uid)
                        except (TypeError, ValueError):
                            continue
                        look_blob = look if isinstance(look, (bytes, bytearray)) else None
                        if look_blob is None and look:
                            try:
                                look_blob = bytes.fromhex(str(look))
                            except ValueError:
                                look_blob = None
                        if look_blob is not None:
                            look_blob = bytes(look_blob)
                        cur = con.execute(
                            """UPDATE capture_npc_entries SET
                                 legacy_look=COALESCE(?, legacy_look),
                                 door_id=COALESCE(?, door_id), act_index=COALESCE(?, act_index),
                                 flags0=COALESCE(?, flags0), flags1=COALESCE(?, flags1),
                                 flags2=COALESCE(?, flags2), flags3=COALESCE(?, flags3),
                                 legacy_flag=COALESCE(?, legacy_flag), sub_kind=COALESCE(?, sub_kind)
                               WHERE capture_id=? AND zone_db=? AND entity_id=?""",
                            (look_blob, door_id, act_index, flags0, flags1, flags2, flags3,
                             legacy_flag, sub_kind, capture_id, zone_db, uid))
                        n_updated += cur.rowcount
                finally:
                    close_sqlite(sub, tmp_path)
            if n_updated:
                print(f"  capture #{capture_id}: {n_updated} entities backfilled")
            n_captures += 1
            n_updated_total += n_updated
        finally:
            src.close()
    con.commit()
    print(f"Done -- {n_updated_total} entities backfilled across {n_captures} capture(s) with a real NPCLogger.db.")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p1 = sub.add_parser("ingest", help="ingest one capture folder or .zip")
    p1.add_argument("path")
    p1.add_argument("--content-type", default="instances", choices=CONTENT_TYPES,
                     help="what kind of content this capture is from (default: assault -- "
                          "everything ingested so far). Pass 'unclassified' for anything else "
                          "until this tool learns a more specific type.")

    p2 = sub.add_parser("ingest-all", help="ingest every matching file under a directory")
    p2.add_argument("path")
    p2.add_argument("--pattern", default="*.zip")
    p2.add_argument("--content-type", default="instances", choices=CONTENT_TYPES)

    p5 = sub.add_parser("ingest-batch", help="ingest each top-level subfolder of a bundle as its own capture")
    p5.add_argument("path")
    p5.add_argument("--content-type", default="instances", choices=CONTENT_TYPES)
    p5.add_argument("--mission-name", default=None, help="explicit mission_name for every session ingested")

    p3 = sub.add_parser("list", help="list ingested captures")
    p3.add_argument("--content-type", default=None, choices=CONTENT_TYPES,
                     help="filter to one content type (default: show all)")

    p4 = sub.add_parser("show", help="show one capture's ingested contents")
    p4.add_argument("capture_id", type=int)

    sub.add_parser("backfill-look", help="backfill legacy_look + door_id/act_index/flags0-3/"
                                          "legacy_flag/sub_kind for already-ingested captures "
                                          "whose source zip/folder is still on disk, without a "
                                          "full re-ingest")

    args = ap.parse_args()
    con = sqlite3.connect(str(DB_PATH))
    init_db(con)

    if args.cmd == "ingest":
        ingest(con, args.path, content_type=args.content_type)
    elif args.cmd == "ingest-all":
        ingest_all(con, args.path, args.pattern, content_type=args.content_type)
    elif args.cmd == "ingest-batch":
        ingest_batch(con, args.path, content_type=args.content_type, mission_name_override=args.mission_name)
    elif args.cmd == "list":
        cmd_list(con, content_type=args.content_type)
    elif args.cmd == "show":
        cmd_show(con, args.capture_id)
    elif args.cmd == "backfill-look":
        backfill_npc_fields(con)

    con.close()


if __name__ == "__main__":
    main()
