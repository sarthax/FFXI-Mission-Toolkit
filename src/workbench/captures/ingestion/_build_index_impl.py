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
    py -3 -m workbench.captures.ingestion.build_index ingest "<path to a capture folder or .zip>"
    py -3 -m workbench.captures.ingestion.build_index ingest-all "<path to a directory of capture zips>" [--pattern "*.zip"]
    py -3 build_capture_index.py list
    py -3 build_capture_index.py show <capture_id>
"""
import argparse
import bisect
import csv
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
from workbench.core.services import capture_integrity
from workbench.core.services import raw_packet_ingest
from workbench.core.services import capture_chat
from workbench.core.services import pcap_ingest

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
    "Abyssea", "Assault", "Ballista", "Battle", "Battle Systems", "Battlefields", "Besieged", "Brenner",
    "Campaign", "Colonization", "Combat", "Conflict", "Escha", "Events", "Events - Holiday",
    "Events - Temporary", "Expeditionary Force", "Garrison", "Hobbies", "Missions", "NPC",
    "Notorious Monsters", "Quests", "Records of Eminence", "Research", "Salvage", "Shop",
    "Trust", "Uncategorized",
]
# 2026-10-03: tags are FREE-FORM (set_capture_tags accepts any text). CAPTURE_TAGS above is only the
# suggested default set. Convention: a TYPE tag (Conflict, Assault, Salvage, Abyssea, Events...)
# mirroring the Discord category, plus a KIND tag mirroring the channel (Campaign, Ballista, Besieged,
# Brenner, Colonization, Expeditionary Force, Garrison) -- e.g. Conflict + Campaign + Battle.


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
            PRIMARY KEY (capture_id, zone_db, entity_id, leg, step)
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
        CREATE TABLE IF NOT EXISTS capture_chat_observations (
            capture_id INTEGER, seq INTEGER, ts TEXT, direction TEXT,
            zone_id INTEGER, zone_db TEXT, text TEXT,
            source_format TEXT, source_native_id TEXT,
            PRIMARY KEY (capture_id, seq)
        );
        CREATE INDEX IF NOT EXISTS idx_capture_chat_source
            ON capture_chat_observations(capture_id,source_format,source_native_id);
        CREATE INDEX IF NOT EXISTS idx_capture_chat_zone
            ON capture_chat_observations(capture_id,zone_id,zone_db);
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
            zone_id INTEGER, packet_size INTEGER, sync_id INTEGER,
            is_injected INTEGER, is_blocked INTEGER,
            source_format TEXT, source_native_id TEXT,
            PRIMARY KEY (capture_id, seq)
        );
        CREATE TABLE IF NOT EXISTS capture_structured_records (
            capture_id INTEGER NOT NULL,
            source_file TEXT NOT NULL,
            family TEXT NOT NULL,
            record_key TEXT NOT NULL,
            record_type TEXT,
            ts TEXT,
            zone TEXT,
            entity_id INTEGER,
            entity_name TEXT,
            item_id INTEGER,
            item_name TEXT,
            price INTEGER,
            payload_json TEXT NOT NULL,
            PRIMARY KEY (capture_id, source_file, family, record_key)
        );
        CREATE TABLE IF NOT EXISTS capture_network_flows (
            capture_id INTEGER NOT NULL,
            source_file TEXT NOT NULL,
            flow_id TEXT NOT NULL,
            transport TEXT NOT NULL,
            endpoint_a_ip TEXT,
            endpoint_a_port INTEGER,
            endpoint_b_ip TEXT,
            endpoint_b_port INTEGER,
            first_ts TEXT,
            last_ts TEXT,
            frame_count INTEGER NOT NULL,
            payload_frame_count INTEGER NOT NULL,
            metadata_json TEXT NOT NULL,
            PRIMARY KEY (capture_id, source_file, flow_id)
        );
        CREATE INDEX IF NOT EXISTS idx_capture_network_flows_transport
            ON capture_network_flows(capture_id,transport);
        CREATE TABLE IF NOT EXISTS capture_network_ranges (
            capture_id INTEGER NOT NULL,
            source_file TEXT NOT NULL,
            flow_id TEXT NOT NULL,
            direction TEXT NOT NULL,
            range_index INTEGER NOT NULL,
            seq_start INTEGER NOT NULL,
            seq_end INTEGER NOT NULL,
            first_ts TEXT,
            last_ts TEXT,
            payload_hex TEXT NOT NULL,
            frame_numbers_json TEXT NOT NULL,
            anomalies_json TEXT NOT NULL,
            PRIMARY KEY (capture_id, source_file, flow_id, direction, range_index)
        );
        CREATE TABLE IF NOT EXISTS capture_network_messages (
            capture_id INTEGER NOT NULL,
            source_file TEXT NOT NULL,
            flow_id TEXT NOT NULL,
            protocol_family TEXT NOT NULL,
            direction TEXT NOT NULL,
            range_index INTEGER NOT NULL,
            message_index INTEGER NOT NULL,
            seq_start INTEGER NOT NULL,
            seq_end INTEGER NOT NULL,
            command INTEGER,
            command_name TEXT,
            validation_status TEXT NOT NULL,
            raw_hex TEXT NOT NULL,
            fields_json TEXT NOT NULL,
            provenance_json TEXT NOT NULL,
            PRIMARY KEY (
                capture_id, source_file, flow_id, direction, range_index, message_index
            )
        );
        CREATE INDEX IF NOT EXISTS idx_capture_network_messages_protocol
            ON capture_network_messages(capture_id,protocol_family,command);
        CREATE INDEX IF NOT EXISTS idx_capture_network_ranges_flow
            ON capture_network_ranges(capture_id,source_file,flow_id,direction);
        CREATE INDEX IF NOT EXISTS idx_capture_structured_family
            ON capture_structured_records(capture_id, family);
        CREATE INDEX IF NOT EXISTS idx_capture_structured_entity
            ON capture_structured_records(entity_id);
        CREATE INDEX IF NOT EXISTS idx_capture_structured_item
            ON capture_structured_records(item_id);
        CREATE TABLE IF NOT EXISTS capture_video_observations (
            capture_id INTEGER,
            observation_id TEXT,
            ocr_run_id TEXT,
            section TEXT,
            frame TEXT,
            video_ts REAL,
            source_url TEXT,
            observation_type TEXT,
            direction TEXT,
            opcode TEXT,
            gp_command TEXT,
            packet_class TEXT,
            fields_json TEXT,
            raw_text TEXT,
            corrected_text TEXT,
            ocr_confidence REAL,
            provenance_json TEXT,
            PRIMARY KEY (capture_id, observation_id)
        );
        CREATE TABLE IF NOT EXISTS capture_tags (
            capture_id INTEGER, tag TEXT,
            PRIMARY KEY (capture_id, tag)
        );
        CREATE INDEX IF NOT EXISTS idx_capture_tags_tag ON capture_tags(tag);
        CREATE INDEX IF NOT EXISTS idx_capture_raw_packets_opcode ON capture_raw_packets(capture_id, opcode);
        CREATE INDEX IF NOT EXISTS idx_capture_raw_packets_direction ON capture_raw_packets(capture_id, direction);
        CREATE INDEX IF NOT EXISTS idx_capture_raw_packets_opcode_global ON capture_raw_packets(opcode);
        CREATE INDEX IF NOT EXISTS idx_capture_video_obs_opcode ON capture_video_observations(capture_id, opcode);
        CREATE INDEX IF NOT EXISTS idx_capture_video_obs_time ON capture_video_observations(capture_id, video_ts);
        CREATE INDEX IF NOT EXISTS idx_capture_video_obs_run ON capture_video_observations(ocr_run_id, section);
    """)
    # CREATE TABLE IF NOT EXISTS doesn't retrofit columns onto an already-existing table (same
    # trap hit earlier with sql_mob_pools/modelid) -- migrate captures explicitly so re-running
    # against the DB from before content_type/zones/mission_name existed doesn't silently no-op.
    existing_cols = {r[1] for r in con.execute("PRAGMA table_info(captures)")}
    for col, decl in [("content_type", "TEXT"), ("zones", "TEXT"), ("mission_name", "TEXT"),
                       ("video_url", "TEXT"), ("ocr_run_id", "TEXT")]:
        if col not in existing_cols:
            con.execute(f"ALTER TABLE captures ADD COLUMN {col} {decl}")
    con.execute("CREATE INDEX IF NOT EXISTS idx_captures_content_type ON captures(content_type)")
    existing_raw_cols = {r[1] for r in con.execute("PRAGMA table_info(capture_raw_packets)")}
    for col, decl in [
        ("zone_id", "INTEGER"), ("packet_size", "INTEGER"), ("sync_id", "INTEGER"),
        ("is_injected", "INTEGER"), ("is_blocked", "INTEGER"),
        ("source_format", "TEXT"), ("source_native_id", "TEXT"),
    ]:
        if col not in existing_raw_cols:
            con.execute(f"ALTER TABLE capture_raw_packets ADD COLUMN {col} {decl}")
    con.execute("""CREATE INDEX IF NOT EXISTS idx_capture_raw_packet_source
                   ON capture_raw_packets(capture_id,source_format,source_native_id)""")
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
    # capture_npc_path historically declared leg but accidentally omitted it from the
    # primary key. The legacy Lua ingester deliberately uses leg=1 for tables/ and leg=2 for
    # database/, so the old PK still let those sources overwrite one another step-for-step.
    # Migrate existing DBs in place so both independently observed path legs can coexist.
    path_pk = [
        row[1] for row in sorted(
            (row for row in con.execute("PRAGMA table_info(capture_npc_path)") if int(row[5] or 0) > 0),
            key=lambda row: int(row[5]),
        )
    ]
    if path_pk == ["capture_id", "zone_db", "entity_id", "step"]:
        con.execute("SAVEPOINT capture_npc_path_pk_migration")
        try:
            con.execute("ALTER TABLE capture_npc_path RENAME TO capture_npc_path_legacy_pk")
            con.execute("""CREATE TABLE capture_npc_path (
                capture_id INTEGER, zone_db TEXT, entity_id INTEGER, leg INTEGER, step INTEGER,
                x REAL, y REAL, z REAL, dir INTEGER, delta INTEGER,
                PRIMARY KEY (capture_id, zone_db, entity_id, leg, step)
            )""")
            con.execute("""INSERT OR IGNORE INTO capture_npc_path
                (capture_id,zone_db,entity_id,leg,step,x,y,z,dir,delta)
                SELECT capture_id,zone_db,entity_id,COALESCE(leg,1),step,x,y,z,dir,delta
                FROM capture_npc_path_legacy_pk""")
            con.execute("DROP TABLE capture_npc_path_legacy_pk")
            con.execute("CREATE INDEX IF NOT EXISTS idx_cnp_entity ON capture_npc_path(entity_id)")
            con.execute("RELEASE SAVEPOINT capture_npc_path_pk_migration")
        except Exception:
            con.execute("ROLLBACK TO SAVEPOINT capture_npc_path_pk_migration")
            con.execute("RELEASE SAVEPOINT capture_npc_path_pk_migration")
            raise

    entity_profile.init_db(con)
    capture_integrity.init_db(con)
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



AUX_STRUCTURED_FORMATS = {
    "missiontrack", "shopstock_buy_db", "shopstock_sell_db", "guildstock_db",
    "weathertrack_db", "poitrack_db", "spawntrack_csv", "checkparam_csv",
    "crafttrack_csv", "conquesttrack_csv", "stattrack_csv", "puppet_stattrack_csv",
    "pricelog_simple", "pricelog_lua",
}


def _safe_int(value):
    try:
        if value is None or value == "":
            return None
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _structured_insert(
    con, capture_id: int, source_file: str, family: str, record_key: str, payload: dict,
    *, record_type=None, ts=None, zone=None, entity_id=None, entity_name=None,
    item_id=None, item_name=None, price=None,
):
    con.execute(
        """INSERT OR REPLACE INTO capture_structured_records
           (capture_id,source_file,family,record_key,record_type,ts,zone,entity_id,entity_name,
            item_id,item_name,price,payload_json)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            capture_id, source_file, family, str(record_key), record_type,
            None if ts is None else str(ts), zone, _safe_int(entity_id), entity_name,
            _safe_int(item_id), item_name, _safe_int(price),
            json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str),
        ),
    )


def _ingest_structured_sqlite(con, capture_id: int, src: Source, relname: str, family: str) -> int:
    source_bytes = src.read_bytes(relname)
    source_sha256 = capture_integrity.sha256_bytes(source_bytes)
    con.execute(
        "DELETE FROM capture_row_locators WHERE capture_id=? AND filename=? "
        "AND target_table='capture_structured_records'",
        (capture_id, relname),
    )
    sub, tmp_path = src.open_sqlite(relname)
    try:
        sub.row_factory = sqlite3.Row
        tables = {r[0] for r in sub.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if "entries" not in tables:
            return 0
        rows = sub.execute("SELECT rowid AS __rowid__, * FROM entries ORDER BY rowid").fetchall()
        n = 0
        for row in rows:
            payload = dict(row)
            source_rowid = payload.pop("__rowid__", None)
            source_id = payload.get("id")
            record_key = str(source_id if source_id is not None else source_rowid)
            subtype = None
            if family == "shopstock_buy_db":
                subtype = "NPC_BUY"
            elif family == "shopstock_sell_db":
                subtype = "NPC_SELL"
            elif family == "guildstock_db":
                lower = relname.lower()
                subtype = "GUILD_BUY" if "buylist" in lower else ("GUILD_SELL" if "selllist" in lower else "GUILD_STOCK")
            _structured_insert(
                con, capture_id, relname, family, record_key, payload,
                record_type=subtype,
                ts=payload.get("created_at") or payload.get("StartTime"),
                zone=payload.get("NpcZone") or payload.get("ZoneName"),
                entity_id=payload.get("NpcUniqueNo") or payload.get("uniqueId"),
                entity_name=payload.get("NpcName") or payload.get("name"),
                item_id=payload.get("ItemNo"),
                item_name=payload.get("ItemName"),
                price=payload.get("ItemPrice") if payload.get("ItemPrice") is not None else payload.get("Price"),
            )
            capture_integrity.record_row_locator(
                con, capture_id, relname, "capture_structured_records",
                json.dumps({"source_file": relname, "family": family, "record_key": record_key}, sort_keys=True),
                "sqlite-row", source_sha256=source_sha256,
                details={
                    "source_table": "entries",
                    "source_rowid": source_rowid,
                    "source_id": source_id,
                    "family": family,
                },
            )
            n += 1
        return n
    finally:
        sub.close()
        try:
            Path(tmp_path).unlink()
        except OSError:
            pass


def _ingest_structured_csv(con, capture_id: int, src: Source, relname: str, family: str) -> int:
    source_bytes = src.read_bytes(relname)
    text = source_bytes.decode("utf-8-sig", "replace")
    byte_offsets_exact = text.encode("utf-8") == source_bytes
    source_sha256 = capture_integrity.sha256_bytes(source_bytes)
    raw_lines = text.splitlines(keepends=True)
    reader = csv.DictReader(io.StringIO(text))
    con.execute(
        "DELETE FROM capture_row_locators WHERE capture_id=? AND filename=? "
        "AND target_table='capture_structured_records'",
        (capture_id, relname),
    )
    n = 0
    char_offsets = []
    pos = 0
    for raw in raw_lines:
        char_offsets.append(pos)
        pos += len(raw)
    for row_number, row in enumerate(reader, start=2):
        payload = {str(k): v for k, v in row.items() if k is not None}
        record_key = str(row_number - 1)
        zone = payload.get("Zone") or payload.get("ZoneName")
        entity_id = payload.get("UniqueNo") or payload.get("NpcUniqueNo")
        entity_name = payload.get("MobName") or payload.get("NpcName")
        item_id = payload.get("ItemNo")
        item_name = payload.get("ItemNo_Name") or payload.get("ItemName")
        ts = payload.get("Timestamp") or payload.get("timestamp") or payload.get("recvTime") or payload.get("SpawnedAt")
        record_type = family.replace("_csv", "").upper()
        _structured_insert(
            con, capture_id, relname, family, record_key, payload,
            record_type=record_type, ts=ts, zone=zone, entity_id=entity_id,
            entity_name=entity_name, item_id=item_id, item_name=item_name,
            price=payload.get("Price") or payload.get("ItemPrice"),
        )
        start_char = char_offsets[row_number - 1] if row_number - 1 < len(char_offsets) else None
        end_char = (char_offsets[row_number] if row_number < len(char_offsets) else len(text))
        capture_integrity.record_row_locator(
            con, capture_id, relname, "capture_structured_records",
            json.dumps({"source_file": relname, "family": family, "record_key": record_key}, sort_keys=True),
            "csv-row", source_sha256=source_sha256,
            start_line=row_number, end_line=row_number,
            start_offset=(len(text[:start_char].encode("utf-8")) if byte_offsets_exact and start_char is not None else None),
            end_offset=(len(text[:end_char].encode("utf-8")) if byte_offsets_exact else None),
            details={"family": family, "csv_row": row_number},
        )
        n += 1
    return n


MISSIONTRACK_HEADER_RE = re.compile(r"^\[([^\]]+)\]\s+(.+)$", re.MULTILINE)
MISSIONTRACK_PAIR_RE = re.compile(
    r"\{\s*[\"']([^\"']+)[\"']\s*,\s*(?:[\"']([^\"']*)[\"']|(-?\d+(?:\.\d+)?)|true|false)\s*\}"
)
PRICELOG_SIMPLE_RE = re.compile(
    r"Incoming:\s*0x03D\s*\(Price Response\),\s*Item:\s*(\d+)\s*\((.*?)\)\s*"
    r"Price:\s*(\d+)\s*Character:\s*(.*?)\s*Zone:\s*(.*?)\s*NPC:\s*(.*?)(?:\r?\n|$)",
    re.IGNORECASE,
)
PRICELOG_LUA_RE = re.compile(
    r"\[(\d+)\]\s*=\s*\{[^}]*?\bname\s*=\s*[\"']([^\"']*)[\"'][^}]*?"
    r"\bprice\s*=\s*(\d+)[^}]*?\bchar\s*=\s*[\"']([^\"']*)[\"'][^}]*?"
    r"\bzone\s*=\s*[\"']([^\"']*)[\"'][^}]*?\bnpc\s*=\s*[\"']([^\"']*)[\"'][^}]*?\}",
    re.IGNORECASE | re.DOTALL,
)


def ingest_missiontrack(con, capture_id: int, src: Source, relname: str) -> int:
    source_bytes = src.read_bytes(relname)
    text = source_bytes.decode("utf-8", "replace")
    exact = text.encode("utf-8") == source_bytes
    sha = capture_integrity.sha256_bytes(source_bytes)
    headers = list(MISSIONTRACK_HEADER_RE.finditer(text))
    con.execute(
        "DELETE FROM capture_row_locators WHERE capture_id=? AND filename=? "
        "AND target_table='capture_structured_records'",
        (capture_id, relname),
    )
    n = 0
    for i, m in enumerate(headers):
        end = headers[i + 1].start() if i + 1 < len(headers) else len(text)
        block = text[m.start():end].rstrip()
        pairs = {}
        for pm in MISSIONTRACK_PAIR_RE.finditer(block):
            key = pm.group(1)
            value = pm.group(2) if pm.group(2) is not None else pm.group(3)
            pairs[key] = value
        payload = {"title": m.group(2).strip(), "fields": pairs, "raw": block}
        record_key = str(i + 1)
        _structured_insert(
            con, capture_id, relname, "missiontrack", record_key, payload,
            record_type=m.group(2).strip(), ts=m.group(1).strip(),
            zone=pairs.get("Zone"), entity_id=None,
        )
        capture_integrity.record_row_locator(
            con, capture_id, relname, "capture_structured_records",
            json.dumps({"source_file": relname, "family": "missiontrack", "record_key": record_key}, sort_keys=True),
            "block", source_sha256=sha,
            start_line=text.count("\n", 0, m.start()) + 1,
            end_line=text.count("\n", 0, end) + (0 if end and text[end - 1:end] == "\n" else 1),
            start_offset=len(text[:m.start()].encode("utf-8")) if exact else None,
            end_offset=len(text[:end].encode("utf-8")) if exact else None,
            details={"family": "missiontrack", "timestamp": m.group(1).strip(), "title": m.group(2).strip()},
        )
        n += 1
    return n


def ingest_pricelog_simple(con, capture_id: int, src: Source, relname: str) -> int:
    source_bytes = src.read_bytes(relname)
    text = source_bytes.decode("utf-8", "replace")
    exact = text.encode("utf-8") == source_bytes
    sha = capture_integrity.sha256_bytes(source_bytes)
    con.execute(
        "DELETE FROM capture_row_locators WHERE capture_id=? AND filename=? "
        "AND target_table='capture_structured_records'",
        (capture_id, relname),
    )
    n = 0
    for m in PRICELOG_SIMPLE_RE.finditer(text):
        n += 1
        item_id, item_name, price, character, zone, npc = m.groups()
        payload = {
            "opcode": "0x03D", "item_id": int(item_id), "item_name": item_name,
            "price": int(price), "character": character.strip(), "zone": zone.strip(),
            "npc": npc.strip(),
        }
        key = str(n)
        _structured_insert(
            con, capture_id, relname, "pricelog_simple", key, payload,
            record_type="NPC_RESALE", zone=zone.strip(), entity_name=npc.strip(),
            item_id=item_id, item_name=item_name, price=price,
        )
        capture_integrity.record_row_locator(
            con, capture_id, relname, "capture_structured_records",
            json.dumps({"source_file": relname, "family": "pricelog_simple", "record_key": key}, sort_keys=True),
            "block", source_sha256=sha,
            start_line=text.count("\n", 0, m.start()) + 1,
            end_line=text.count("\n", 0, m.end()) + 1,
            start_offset=len(text[:m.start()].encode("utf-8")) if exact else None,
            end_offset=len(text[:m.end()].encode("utf-8")) if exact else None,
            details={"family": "pricelog_simple", "opcode": "0x03D"},
        )
    return n


def ingest_pricelog_lua(con, capture_id: int, src: Source, relname: str) -> int:
    source_bytes = src.read_bytes(relname)
    text = source_bytes.decode("utf-8", "replace")
    exact = text.encode("utf-8") == source_bytes
    sha = capture_integrity.sha256_bytes(source_bytes)
    con.execute(
        "DELETE FROM capture_row_locators WHERE capture_id=? AND filename=? "
        "AND target_table='capture_structured_records'",
        (capture_id, relname),
    )
    n = 0
    for m in PRICELOG_LUA_RE.finditer(text):
        item_id, item_name, price, character, zone, npc = m.groups()
        payload = {
            "item_id": int(item_id), "item_name": item_name, "price": int(price),
            "character": character, "zone": zone, "npc": npc,
        }
        key = str(item_id)
        _structured_insert(
            con, capture_id, relname, "pricelog_lua", key, payload,
            record_type="NPC_RESALE_DB", zone=zone, entity_name=npc,
            item_id=item_id, item_name=item_name, price=price,
        )
        capture_integrity.record_row_locator(
            con, capture_id, relname, "capture_structured_records",
            json.dumps({"source_file": relname, "family": "pricelog_lua", "record_key": key}, sort_keys=True),
            "block", source_sha256=sha,
            start_line=text.count("\n", 0, m.start()) + 1,
            end_line=text.count("\n", 0, m.end()) + 1,
            start_offset=len(text[:m.start()].encode("utf-8")) if exact else None,
            end_offset=len(text[:m.end()].encode("utf-8")) if exact else None,
            details={"family": "pricelog_lua", "item_id": int(item_id)},
        )
        n += 1
    return n


def ingest_aux_structured(con, capture_id: int, src: Source, relname: str, fmt: str) -> int:
    if fmt in {"shopstock_buy_db", "shopstock_sell_db", "guildstock_db", "weathertrack_db", "poitrack_db"}:
        return _ingest_structured_sqlite(con, capture_id, src, relname, fmt)
    if fmt in {"spawntrack_csv", "checkparam_csv", "crafttrack_csv", "conquesttrack_csv"}:
        return _ingest_structured_csv(con, capture_id, src, relname, fmt)
    if fmt == "missiontrack":
        return ingest_missiontrack(con, capture_id, src, relname)
    if fmt == "pricelog_simple":
        return ingest_pricelog_simple(con, capture_id, src, relname)
    if fmt == "pricelog_lua":
        return ingest_pricelog_lua(con, capture_id, src, relname)
    raise ValueError(f"unsupported auxiliary capture format: {fmt}")


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
            tables = {str(r[0]).upper() for r in con.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )}
            if "PACKETS" in tables:
                packet_cols = {str(r[1]).upper() for r in con.execute("PRAGMA table_info(PACKETS)")}
            else:
                packet_cols = set()
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
    if {"PACKET_ID","RECEIVED_DT","DIRECTION","ZONE_ID","PACKET_TYPE",
        "PACKET_SIZE","PACKET_SYNC","PACKET_DATA"} <= packet_cols:
        return "packetdb"
    if not cols:
        return None
    if {"UniqueNo", "Hpp", "model_id"} <= cols:
        return "npclogger_db"
    if {"actor", "ActionType", "animation"} <= cols:
        return "actionview_db"
    if {"Level_min", "Level_max", "UniqueNo"} <= cols:
        return "levelrange_db"
    if {"NpcUniqueNo", "NpcName", "NpcZone", "ItemNo", "ItemName", "Count", "Max", "Price"} <= cols:
        return "guildstock_db"
    # Earliest persisted GuildStock generation predated NPC identity and Hidden columns.
    if {"ItemNo", "ItemName", "Count", "Max", "Price"} <= cols:
        return "guildstock_db"
    if {"NpcUniqueNo", "NpcName", "NpcZone", "GuildInfo", "ItemNo", "ItemName", "ItemPrice", "ShopIndex", "Skill"} <= cols:
        return "shopstock_buy_db"
    if {"NpcUniqueNo", "NpcName", "NpcZone", "ItemNo", "ItemName", "Price"} <= cols:
        return "shopstock_sell_db"
    if {"ZoneNo", "ZoneName", "PreviousWeatherNumber", "WeatherNumber", "StartTime", "WeatherOffsetTime"} <= cols:
        return "weathertrack_db"
    if {"uniqueId", "name", "x", "y", "z"} <= cols:
        return "poitrack_db"
    return None


WINDOWER_LOGGER_FILENAME_RE = re.compile(
    r'(?i)(?:^|/)logs/([^/]+)_(\d{4})\.(\d{2})\.(\d{2})\.log$'
)
WINDOWER_LOGGER_BASENAME_RE = re.compile(
    r'(?i)^([^/]+)_(\d{4})\.(\d{2})\.(\d{2})\.log$'
)
WINDOWER_LOGGER_TIME_RE = re.compile(r'^(\d{2}:\d{2}:\d{2})(.*)$')


def ingest_windower_logger(con, capture_id: int, src: Source, relname: str) -> int:
    """Ingest Windower Logger daily chat files into canonical chat observations.

    Logger timestamps are optional and default to HH:MM:SS without a separator before the text.
    The filename supplies the date. Untimestamped lines retain ts=NULL.
    """
    data = src.read_bytes(relname)
    text = data.decode("utf-8", "replace")
    exact = text.encode("utf-8") == data
    sha = capture_integrity.sha256_bytes(data)
    base = relname.rsplit("/", 1)[-1]
    m = WINDOWER_LOGGER_BASENAME_RE.match(base)
    if not m:
        raise ValueError("Windower Logger filename must be <player>_YYYY.MM.DD.log")
    player, year, month, day = m.groups()

    old_rows = con.execute(
        """SELECT row_key FROM capture_row_locators
           WHERE capture_id=? AND filename=? AND target_table='capture_chat_observations'""",
        (capture_id, relname),
    ).fetchall()
    for (row_key_raw,) in old_rows:
        try:
            seq = json.loads(row_key_raw).get("seq")
        except Exception:
            seq = None
        if seq is not None:
            con.execute(
                "DELETE FROM capture_chat_observations WHERE capture_id=? AND seq=?",
                (capture_id, int(seq)),
            )
    con.execute(
        """DELETE FROM capture_row_locators
           WHERE capture_id=? AND filename=? AND target_table='capture_chat_observations'""",
        (capture_id, relname),
    )

    count = 0
    char_pos = 0
    for line_number, raw_line in enumerate(text.splitlines(keepends=True), start=1):
        content = raw_line.rstrip("\r\n")
        start_char = char_pos
        char_pos += len(raw_line)
        if not content:
            continue
        tm = WINDOWER_LOGGER_TIME_RE.match(content)
        if tm:
            clock, message = tm.groups()
            ts = f"{year}-{month}-{day} {clock}"
        else:
            message = content
            ts = None
        if not message:
            continue
        capture_chat.insert_chat_observation(
            con, capture_id,
            ts=ts,
            direction=None,
            zone_id=None,
            zone_db=None,
            text=message,
            source_format="windower_logger",
            source_native_id=f"{relname}:line:{line_number}",
            filename=relname,
            source_sha256=sha,
            locator_basis="line",
            start_line=line_number,
            end_line=line_number,
            start_offset=(len(text[:start_char].encode("utf-8")) if exact else None),
            end_offset=(len(text[:char_pos].encode("utf-8")) if exact else None),
            details={
                "player_from_filename": player,
                "date_from_filename": f"{year}-{month}-{day}",
                "timestamp_present": bool(tm),
            },
        )
        count += 1
    return count


def sniff_text_format(text: str) -> str | None:
    """Which capture log format this text file is, by real content signature -- a dropped file's
    own name can't be trusted to carry the addon folder it came from (idview/, KITrack/, etc.),
    so this looks at the first real content instead. Order matters: check the more specific
    signatures before the more generic ones."""
    head = text[:4000]
    if re.search(r'\[(?:S->C|C->S)\].*PacketId:\s*[0-9A-Fa-f]{1,4}', head, re.IGNORECASE):
        return "packeteer"
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
    if re.search(r"^\[[^\]]+\]\s+.+\n\{", head, re.MULTILINE):
        return "missiontrack"
    if PRICELOG_SIMPLE_RE.search(head):
        return "pricelog_simple"
    if "local resale_database" in head and re.search(r"\bprice\s*=", head):
        return "pricelog_lua"
    return None



def sniff_csv_format(text: str) -> str | None:
    first = next(csv.reader(io.StringIO(text.lstrip("\ufeff"))), [])
    cols = {str(x).strip() for x in first}
    if {"MobName","UniqueNo","DefeatedAt","SpawnedAt","XSpawn","YSpawn","ZSpawn"} <= cols:
        return "spawntrack_csv"
    if {"recvTime","acc","atk","offacc","offatk","rangeacc","rangeatk","eva","def"} <= cols:
        # syncId was added after the first persisted CheckParam format.
        return "checkparam_csv"
    if {"Timestamp","Result","Grade","ItemNo","CrystalNo","MaterialNo_1","Effect_Type"} <= cols:
        return "crafttrack_csv"
    if {"Timestamp","Balance","Alliance","CurSandy","CurBastok","CurWindy","NextTally","CP","CurBeastmen"} <= cols:
        return "conquesttrack_csv"
    lower_cols = {x.lower() for x in cols}
    if {"timestamp","hpmax","mpmax","mjob_no","mjob_lv","sjob_no","sjob_lv",
        "str","dex","vit","agi","int","mnd","chr"} <= lower_cols:
        return "stattrack_csv"
    if {"timestamp","maxhp","maxmp","maxmelee","maxranged","maxmagic",
        "str","dex","vit","agi","int","mnd","chr"} <= lower_cols:
        return "puppet_stattrack_csv"
    if {"leg","x","y","z","dir","delta"} <= lower_cols:
        return "pathlog_csv"
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
        if suffix in (".pcap", ".pcapng") or pcap_ingest.sniff_pcap_format(data):
            fmt = pcap_ingest.sniff_pcap_format(data)
            src = SingleFileSource(filename, data)
            if fmt:
                frames, chunks, flows, ranges, messages = pcap_ingest.ingest_pcap(con, capture_id, src, filename)
                rows = frames + chunks + flows + ranges + messages
            else:
                error = "Unrecognized packet-capture container"
        elif suffix in (".db", ".sqlite", ".sqlite3"):
            fmt = sniff_sqlite_format(data)
            src = SingleFileSource(filename, data)
            if fmt == "packetdb":
                rows = raw_packet_ingest.ingest_packetdb(con, capture_id, src, filename)
            elif fmt == "npclogger_db":
                e, h = ingest_npc_db(con, capture_id, src, zone_db + ".db")
                rows = e + h
            elif fmt == "actionview_db":
                rows = ingest_actions_db(con, capture_id, src, "Actions.db")
            elif fmt == "levelrange_db":
                rows = ingest_level_range_db(con, capture_id, src, zone_db + ".db")
            elif fmt in AUX_STRUCTURED_FORMATS:
                rows = ingest_aux_structured(con, capture_id, src, filename, fmt)
            else:
                error = "Unrecognized .db schema"
        elif suffix == ".csv":
            text = data.decode("utf-8-sig", "replace")
            fmt = sniff_csv_format(text)
            src = SingleFileSource(filename, data)
            if fmt == "pathlog_csv":
                error = "PathLog CSVs need their real folder path (zone/NPC label) for zone context -- upload as part of a zip instead of a bare file"
            elif fmt in AUX_STRUCTURED_FORMATS:
                rows = ingest_aux_structured(con, capture_id, src, filename, fmt)
            else:
                error = "Unrecognized CSV schema"
        else:
            text = data.decode("utf-8", "replace")
            basename = Path(filename).name.lower()
            if WINDOWER_LOGGER_BASENAME_RE.match(basename):
                fmt = "windower_logger"
            elif basename == "simple.log" and IDVIEW2_HEADER_RE.search(text):
                fmt = "eventview_session_simple"
            elif basename == "raw.log" and IDVIEW2_HEADER_RE.search(text) and PACKETLOGGER_HEXROW_RE.search(text):
                fmt = "eventview_session_raw"
            else:
                fmt = sniff_text_format(text)
            src = SingleFileSource(filename, data)
            if fmt == "packeteer":
                rows = raw_packet_ingest.ingest_packeteer(con, capture_id, src, filename)
            elif fmt == "windower_logger":
                rows = ingest_windower_logger(con, capture_id, src, filename)
            elif fmt == "idview_simple":
                rows = ingest_idview_simple(con, capture_id, src, zone_db + ".log")
            elif fmt == "eventview_session_simple":
                rows = ingest_eventview_session_simple(con, capture_id, src, filename)
            elif fmt == "eventview_session_raw":
                rows = ingest_eventview_session_raw(con, capture_id, src, filename)
            elif fmt == "kitrack":
                rows = ingest_kitrack(con, capture_id, src, zone_db + ".log")
            elif fmt == "eventview":
                rows = ingest_eventview(
                    con, capture_id, src, "Capturer/" + zone_db + ".log",
                    source_filename=filename,
                )
            elif fmt == "attackdelay":
                rows = ingest_attackdelay(con, capture_id, src, zone_db + ".log")
            elif fmt == "hptrack":
                rows = ingest_hptrack(con, capture_id, src, zone_db + ".log")
            elif fmt == "npclogger_lua":
                e, p = ingest_npclogger_lua(con, capture_id, src, zone_db + ".lua")
                rows = e + p
            elif fmt in AUX_STRUCTURED_FORMATS:
                rows = ingest_aux_structured(con, capture_id, src, filename, fmt)
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
    capture_integrity.record_source_file(
        con, capture_id, filename, data,
        format_detected=fmt, parser_name=fmt, row_count=rows, error=error,
    )
    recompute_zones(con, capture_id)
    con.commit()
    return {"filename": filename, "format": fmt, "rows": rows, "error": error}


def replace_video_ocr_observations(
    con: sqlite3.Connection,
    capture_id: int,
    ocr_run_id: str,
    observations,
) -> int:
    """Replace one OCR run's derived observations for a capture.

    These rows are intentionally separate from capture_raw_packets: VIDEO_OCR can identify
    an on-screen opcode/field rendering, but it does not possess the underlying packet bytes.
    """
    con.execute(
        "DELETE FROM capture_video_observations WHERE capture_id=? AND ocr_run_id=?",
        (capture_id, ocr_run_id),
    )
    count = 0
    for row in observations:
        con.execute(
            """INSERT INTO capture_video_observations
            (capture_id,observation_id,ocr_run_id,section,frame,video_ts,source_url,
             observation_type,direction,opcode,gp_command,packet_class,fields_json,
             raw_text,corrected_text,ocr_confidence,provenance_json)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                capture_id,
                row["observation_id"],
                ocr_run_id,
                row.get("section"),
                row.get("frame"),
                row.get("video_timestamp_seconds"),
                row.get("source_url"),
                row.get("observation_type") or "OCR_TEXT",
                row.get("direction"),
                row.get("opcode"),
                row.get("gp_command"),
                row.get("packet_class"),
                json.dumps(row.get("fields"), sort_keys=True) if row.get("fields") else None,
                row.get("raw_text"),
                row.get("corrected_text"),
                row.get("confidence"),
                json.dumps(row.get("provenance") or {}, sort_keys=True),
            ),
        )
        count += 1
    con.commit()
    return count


def create_manual_capture(con, label: str, content_type: str, mission_name: str | None,
                           video_url: str | None = None, ocr_run_id: str | None = None,
                           start_time: float | None = None) -> int:
    """Starts a capture with no source file at all -- source_path is a synthetic manual:// marker
    (unique per creation timestamp) so it never collides with a real zip/folder path, and files
    get added to it one at a time afterward via ingest_single_file() or a real zip via
    ingest_from_source(). This is the "build a capture from scratch" entry point the GUI's
    /captures/new page uses, and also what /ocr/{run_id}/create_capture uses to seed a capture
    from an OCR run's video_url/upload-date/run_id -- an OCR run has no logger files of its own,
    so this is the only real data it can hand off; ocr_run_id is how the capture links back to its
    transcript/frames under mission_reports_v2/_ocr_runs/<run_id>/."""
    source_path = f"manual://{label}#{int(time.time() * 1000)}"
    cur = con.execute("""INSERT INTO captures
        (source_path, capturer, capture_label, content_type, mission_name, addons,
         client_build, is_retail, start_time, zones, video_url, ocr_run_id)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
        (source_path, None, label, content_type, mission_name or None, "[]", None, None,
         start_time, "[]", video_url or None, ocr_run_id or None))
    con.commit()
    return cur.lastrowid


def set_capture_tags(con, capture_id: int, tags: list[str]):
    """Replaces this capture's tags wholesale (delete-then-insert). Tags are free-form: any
    non-empty text is kept (trimmed, case-insensitively de-duplicated, 60 chars max); a tag
    that matches a known/existing tag case-insensitively reuses that spelling."""
    known = {t.lower(): t for t in all_tag_choices(con)}
    con.execute("DELETE FROM capture_tags WHERE capture_id=?", (capture_id,))
    seen = set()
    for tag in tags:
        tag = re.sub(r"\s+", " ", (tag or "")).strip()[:60]
        if not tag or tag.lower() in seen:
            continue
        seen.add(tag.lower())
        con.execute("INSERT OR IGNORE INTO capture_tags (capture_id, tag) VALUES (?,?)",
                    (capture_id, known.get(tag.lower(), tag)))
    con.commit()


def all_tag_choices(con) -> list[str]:
    """Suggested defaults plus every tag actually in use, sorted."""
    used = [r[0] for r in con.execute("SELECT DISTINCT tag FROM capture_tags")]
    return sorted(set(CAPTURE_TAGS) | set(used), key=str.lower)


def split_tags(raw: str) -> list[str]:
    return [t for t in re.split(r"[,;\n]", raw or "") if t.strip()]


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
    source_bytes = src.read_bytes(relname)
    source_sha256 = capture_integrity.sha256_bytes(source_bytes)
    con.execute(
        """DELETE FROM capture_row_locators
           WHERE capture_id=? AND filename=?
             AND target_table IN ('capture_npc_entries','capture_npc_history')""",
        (capture_id, relname),
    )
    sub, tmp_path = src.open_sqlite(relname)
    try:
        tables = {r[0] for r in sub.execute("select name from sqlite_master where type='table'")}
        if "entries" not in tables:
            return 0, 0
        n_entries = n_hist = 0
        for row in sub.execute("""SELECT rowid, UniqueNo, Name, model_id, x, y, z, dir, Hpp,
                                          legacy_flags, legacy_status, legacy_animation, Speed,
                                          created_at, updated_at, legacy_look, DoorId, ActIndex,
                                          Flags0, Flags1, Flags2, Flags3, legacy_flag, SubKind
                                   FROM entries"""):
            (source_rowid, uid, name, model_id, x, y, z, d, hpp, lflags, lstatus, lanim, speed,
             cat, uat, look, door_id, act_index, flags0, flags1, flags2, flags3, legacy_flag,
             sub_kind) = row
            try:
                uid = int(uid)
            except (TypeError, ValueError):
                continue
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
            capture_integrity.record_row_locator(
                con, capture_id, relname, "capture_npc_entries",
                json.dumps({"zone_db": zone_db, "entity_id": uid}, sort_keys=True),
                "sqlite-row",
                source_sha256=source_sha256,
                details={
                    "source": "npclogger_db", "source_table": "entries",
                    "source_rowid": source_rowid, "UniqueNo": uid,
                },
            )
            n_entries += 1
            record_entity_facts(con, uid, name, model_id, x, y, z, hpp, zone_db)
        if "history" in tables:
            for row in sub.execute("SELECT rowid, id, entry_id, time, delta FROM history"):
                source_rowid, source_id, entry_id, ts, delta = row
                try:
                    eid = int(str(entry_id).split("-")[0])
                except (TypeError, ValueError):
                    continue
                con.execute("""INSERT OR REPLACE INTO capture_npc_history
                    (capture_id, zone_db, entity_id, seq, ts, delta_json)
                    VALUES (?,?,?,?,?,?)""", (capture_id, zone_db, eid, source_id, ts, delta))
                capture_integrity.record_row_locator(
                    con, capture_id, relname, "capture_npc_history",
                    json.dumps(
                        {"zone_db": zone_db, "entity_id": eid, "seq": source_id},
                        sort_keys=True,
                    ),
                    "sqlite-row",
                    source_sha256=source_sha256,
                    details={
                        "source": "npclogger_db", "source_table": "history",
                        "source_rowid": source_rowid, "source_id": source_id,
                        "entry_id": entry_id,
                    },
                )
                n_hist += 1
        return n_entries, n_hist
    finally:
        close_sqlite(sub, tmp_path)

def ingest_level_range_db(con, capture_id, src: Source, relname: str) -> int:
    """LevelRangeTrack SQLite rows with exact source-table/rowid provenance."""
    zone_db = Path(relname).stem
    source_bytes = src.read_bytes(relname)
    source_sha256 = capture_integrity.sha256_bytes(source_bytes)
    con.execute(
        """DELETE FROM capture_row_locators
           WHERE capture_id=? AND filename=? AND target_table='capture_level_range'""",
        (capture_id, relname),
    )
    sub, tmp_path = src.open_sqlite(relname)
    try:
        tables = {r[0] for r in sub.execute("select name from sqlite_master where type='table'")}
        if "entries" not in tables:
            return 0
        n = 0
        for row in sub.execute(
            "SELECT rowid, UniqueNo, sName, Level_min, Level_max, ActIndex FROM entries"
        ):
            source_rowid, uid, name, lmin, lmax, act_index = row
            try:
                uid = int(uid)
            except (TypeError, ValueError):
                continue
            con.execute("""INSERT OR REPLACE INTO capture_level_range
                (capture_id, zone_db, entity_id, name, level_min, level_max, act_index)
                VALUES (?,?,?,?,?,?,?)""",
                (capture_id, zone_db, uid, name, lmin, lmax, act_index))
            capture_integrity.record_row_locator(
                con, capture_id, relname, "capture_level_range",
                json.dumps({"zone_db": zone_db, "entity_id": uid}, sort_keys=True),
                "sqlite-row",
                source_sha256=source_sha256,
                details={
                    "source": "levelrange_db", "source_table": "entries",
                    "source_rowid": source_rowid, "UniqueNo": uid,
                },
            )
            n += 1
        return n
    finally:
        close_sqlite(sub, tmp_path)

WIDESCAN_LINE_RE = re.compile(
    r"\[(\d+)\]\s*=\s*\{\['id'\]=(\d+),\s*\['name'\]=\"([^\"]*)\",\s*\['index'\]=(-?\d+),\s*\['level'\]=(-?\d+)\}"
)


def ingest_widescan(con, capture_id, src: Source, relname: str) -> int:
    """Ingest widescan rows with exact physical-line provenance."""
    zone_db = Path(relname).stem
    source_bytes = src.read_bytes(relname)
    text = source_bytes.decode("utf-8", "replace")
    byte_offsets_exact = text.encode("utf-8") == source_bytes
    source_sha256 = capture_integrity.sha256_bytes(source_bytes)
    raw_lines = text.splitlines(keepends=True)
    con.execute(
        """DELETE FROM capture_row_locators
           WHERE capture_id=? AND filename=?
             AND target_table IN ('capture_npc_entries','capture_level_range')""",
        (capture_id, relname),
    )
    n = 0
    char_pos = 0
    for line_no, raw_line in enumerate(raw_lines, start=1):
        line = raw_line.rstrip("\r\n")
        line_start = char_pos
        char_pos += len(raw_line)
        for m in WIDESCAN_LINE_RE.finditer(line):
            key_id, uid, name, index, level = m.groups()
            uid = int(uid)
            index = int(index)
            level = int(level)
            cur = con.execute("""INSERT OR IGNORE INTO capture_npc_entries
                (capture_id, zone_db, entity_id, name) VALUES (?,?,?,?)""",
                (capture_id, zone_db, uid, name))
            if cur.rowcount:
                capture_integrity.record_row_locator(
                    con, capture_id, relname, "capture_npc_entries",
                    json.dumps({"zone_db": zone_db, "entity_id": uid}, sort_keys=True),
                    "line", source_sha256=source_sha256,
                    start_line=line_no, end_line=line_no,
                    start_offset=len(text[:line_start].encode("utf-8")) if byte_offsets_exact else None,
                    end_offset=len(text[:char_pos].encode("utf-8")) if byte_offsets_exact else None,
                    details={"source": "widescan", "source_key": int(key_id), "index": index, "level": level},
                )
            con.execute("""INSERT OR REPLACE INTO capture_level_range
                (capture_id, zone_db, entity_id, name, level_min, level_max, act_index)
                VALUES (?,?,?,?,?,?,?)""",
                (capture_id, zone_db, uid, name, level, level, index))
            capture_integrity.record_row_locator(
                con, capture_id, relname, "capture_level_range",
                json.dumps({"zone_db": zone_db, "entity_id": uid}, sort_keys=True),
                "line", source_sha256=source_sha256,
                start_line=line_no, end_line=line_no,
                start_offset=len(text[:line_start].encode("utf-8")) if byte_offsets_exact else None,
                end_offset=len(text[:char_pos].encode("utf-8")) if byte_offsets_exact else None,
                details={"source": "widescan", "source_key": int(key_id), "index": index, "level": level},
            )
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
    """Ingest aggregated attack-delay blocks with exact source-block provenance."""
    zone_db = Path(relname).stem.replace("_", " ")
    source_bytes = src.read_bytes(relname)
    text = source_bytes.decode("utf-8", "replace")
    byte_offsets_exact = text.encode("utf-8") == source_bytes
    source_sha256 = capture_integrity.sha256_bytes(source_bytes)
    headers = [(m.start(), m.group(1).strip(), int(m.group(2)), int(m.group(3)), int(m.group(4)))
               for m in ATTACKDELAY_HEADER_RE.finditer(text)]
    con.execute(
        """DELETE FROM capture_row_locators
           WHERE capture_id=? AND filename=? AND target_table='capture_attack_delay'""",
        (capture_id, relname),
    )
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
        capture_integrity.record_row_locator(
            con, capture_id, relname, "capture_attack_delay",
            json.dumps({"zone_db": zone_db, "mob_name": name}, sort_keys=True),
            "block", source_sha256=source_sha256,
            start_line=text.count("\n", 0, pos) + 1,
            end_line=text.count("\n", 0, end) + (0 if end > 0 and text[end - 1:end] == "\n" else 1),
            start_offset=len(text[:pos].encode("utf-8")) if byte_offsets_exact else None,
            end_offset=len(text[:end].encode("utf-8")) if byte_offsets_exact else None,
            details={"source": "attackdelay", "mob_name": name, "hit_count": hits},
        )
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
    source_bytes = src.read_bytes(relname)
    text = source_bytes.decode("utf-8", "replace")
    byte_offsets_exact = text.encode("utf-8") == source_bytes
    source_sha256 = capture_integrity.sha256_bytes(source_bytes)
    raw_lines = text.splitlines(keepends=True)
    con.execute(
        "DELETE FROM capture_row_locators WHERE capture_id=? AND filename=? AND target_table='capture_actions'",
        (capture_id, relname),
    )
    n = 0
    char_pos = 0
    for i, raw_line in enumerate(raw_lines):
        line = raw_line.rstrip("\r\n")
        m = ACTIONVIEW_SIMPLE_LINE_RE.match(line.strip())
        start_char = char_pos
        char_pos += len(raw_line)
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
        capture_integrity.record_row_locator(
            con, capture_id, relname, "capture_actions",
            json.dumps({"action_key": key}, sort_keys=True), "line",
            source_sha256=source_sha256,
            start_line=i + 1, end_line=i + 1,
            start_offset=len(text[:start_char].encode("utf-8")) if byte_offsets_exact else None,
            end_offset=len(text[:char_pos].encode("utf-8")) if byte_offsets_exact else None,
            details={"source": "actionview_simple", "actor": actor, "ability_name": ability_name,
                     "category": int(cat), "ability_id": int(aid)},
        )
        n += 1
        if actor_name:
            entity_profile.record_field(con, "npc", actor, "capture_name", "capture", actor_name)
    return n


def ingest_actions_db(con, capture_id, src: Source, relname: str):
    source_bytes = src.read_bytes(relname)
    source_sha256 = capture_integrity.sha256_bytes(source_bytes)
    con.execute(
        """DELETE FROM capture_row_locators
           WHERE capture_id=? AND filename=? AND target_table='capture_actions'""",
        (capture_id, relname),
    )
    sub, tmp_path = src.open_sqlite(relname)
    try:
        tables = {r[0] for r in sub.execute("select name from sqlite_master where type='table'")}
        if "entries" not in tables:
            return 0
        n = 0
        for row in sub.execute("""SELECT rowid, id, actor, actor_name, ActionType, animation,
                                          category, message, name, updated_at FROM entries"""):
            source_rowid, aid, actor, actor_name, atype, anim, cat, msg, name, ts = row
            key = f"{actor}-{aid}"
            con.execute("""INSERT OR REPLACE INTO capture_actions
                (capture_id, action_key, actor, actor_name, action_type, animation, category,
                 message, name, ts) VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (capture_id, key, actor, actor_name, atype, anim, cat, msg, name, ts))
            capture_integrity.record_row_locator(
                con, capture_id, relname, "capture_actions",
                json.dumps({"action_key": key}, sort_keys=True),
                "sqlite-row",
                source_sha256=source_sha256,
                details={
                    "source": "actionview_db", "source_table": "entries",
                    "source_rowid": source_rowid, "source_id": aid, "actor": actor,
                },
            )
            n += 1
        return n
    finally:
        close_sqlite(sub, tmp_path)

def ingest_pathlog(con, capture_id, src: Source, relname: str):
    m = PATHLOG_NPC_RE.search(relname)
    if not m:
        return 0
    zone_db, npc_label, entity_id = m.group(1), m.group(2), int(m.group(3))
    zone_db = zone_db.replace("_", " ")
    source_bytes = src.read_bytes(relname)
    text = source_bytes.decode("utf-8", "replace")
    byte_offsets_exact = text.encode("utf-8") == source_bytes
    source_sha256 = capture_integrity.sha256_bytes(source_bytes)
    raw_lines = text.splitlines(keepends=True)
    if not raw_lines:
        return 0
    con.execute(
        """DELETE FROM capture_row_locators
           WHERE capture_id=? AND filename=? AND target_table='capture_npc_path'""",
        (capture_id, relname),
    )
    n = 0
    char_pos = len(raw_lines[0])
    for step, raw_line in enumerate(raw_lines[1:]):
        line = raw_line.rstrip("\r\n")
        start_char = char_pos
        char_pos += len(raw_line)
        parts = line.split(",")
        if len(parts) < 6:
            continue
        try:
            leg, x, y, z, d, delta = parts[:6]
            leg_i = int(leg)
            con.execute("""INSERT OR REPLACE INTO capture_npc_path
                (capture_id, zone_db, entity_id, leg, step, x, y, z, dir, delta)
                VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (capture_id, zone_db, entity_id, leg_i, step,
                 float(x), float(y), float(z), int(d), int(delta)))
            capture_integrity.record_row_locator(
                con, capture_id, relname, "capture_npc_path",
                json.dumps(
                    {"zone_db": zone_db, "entity_id": entity_id, "leg": leg_i, "step": step},
                    sort_keys=True,
                ),
                "csv-row", source_sha256=source_sha256,
                start_line=step + 2, end_line=step + 2,
                start_offset=len(text[:start_char].encode("utf-8")) if byte_offsets_exact else None,
                end_offset=len(text[:char_pos].encode("utf-8")) if byte_offsets_exact else None,
                details={"source": "pathlog_csv", "npc_label": npc_label},
            )
            n += 1
        except ValueError:
            continue
    return n

PATHLOG_PC_RE = re.compile(r'PathLog/[^/]+/PC_([^/]+)\.csv$', re.I)


def ingest_pc_pathlog(con, capture_id, src: Source, relname: str) -> int:
    """Ingest the capturer's PathLog CSV with exact CSV-row provenance."""
    m = PATHLOG_PC_RE.search(relname)
    if not m:
        return 0
    zone_db = m.group(1).replace("_", " ")
    source_bytes = src.read_bytes(relname)
    text = source_bytes.decode("utf-8", "replace")
    byte_offsets_exact = text.encode("utf-8") == source_bytes
    source_sha256 = capture_integrity.sha256_bytes(source_bytes)
    raw_lines = text.splitlines(keepends=True)
    if not raw_lines:
        return 0
    con.execute(
        """DELETE FROM capture_row_locators
           WHERE capture_id=? AND filename=? AND target_table='capture_pc_path'""",
        (capture_id, relname),
    )
    n = 0
    char_pos = len(raw_lines[0])
    for step, raw_line in enumerate(raw_lines[1:]):
        line = raw_line.rstrip("\r\n")
        start_char = char_pos
        char_pos += len(raw_line)
        parts = line.split(",")
        if len(parts) < 6:
            continue
        try:
            leg, x, y, z, d, delta = parts[:6]
            leg_i = int(leg)
            con.execute("""INSERT OR REPLACE INTO capture_pc_path
                (capture_id, zone_db, leg, step, x, y, z, dir, delta)
                VALUES (?,?,?,?,?,?,?,?,?)""",
                (capture_id, zone_db, leg_i, step,
                 float(x), float(y), float(z), int(d), int(delta)))
            capture_integrity.record_row_locator(
                con, capture_id, relname, "capture_pc_path",
                json.dumps({"zone_db": zone_db, "step": step}, sort_keys=True),
                "csv-row", source_sha256=source_sha256,
                start_line=step + 2, end_line=step + 2,
                start_offset=len(text[:start_char].encode("utf-8")) if byte_offsets_exact else None,
                end_offset=len(text[:char_pos].encode("utf-8")) if byte_offsets_exact else None,
                details={"source": "pc_pathlog_csv", "leg": leg_i},
            )
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
    source_bytes = src.read_bytes(relname)
    text = source_bytes.decode("utf-8", "replace")
    byte_offsets_exact = text.encode("utf-8") == source_bytes
    source_sha256 = capture_integrity.sha256_bytes(source_bytes)
    raw_lines = text.splitlines(keepends=True)
    con.execute(
        "DELETE FROM capture_row_locators WHERE capture_id=? AND filename=? AND target_table='capture_hp_events'",
        (capture_id, relname),
    )
    n = 0
    char_pos = 0
    for i, raw_line in enumerate(raw_lines):
        line = raw_line.rstrip("\r\n").strip()
        start_char = char_pos
        char_pos += len(raw_line)
        m = HP_LINE_RE.match(line)
        if m:
            mob_name, hp_low, hp_high = m.group(1), m.group(2), m.group(3)
        else:
            untagged = line[len("[HP Track] "):] if line.startswith("[HP Track] ") else line
            m2 = CAPLOG_HP_KILL_RE.match(untagged)
            if not m2:
                continue
            mob_name, hp_low, hp_high = m2.group(1), m2.group(2), m2.group(3)
        n += 1
        con.execute("""INSERT OR REPLACE INTO capture_hp_events
            (capture_id, seq, mob_name, hp_low, hp_high) VALUES (?,?,?,?,?)""",
            (capture_id, n, mob_name, int(hp_low), int(hp_high)))
        capture_integrity.record_row_locator(
            con, capture_id, relname, "capture_hp_events",
            json.dumps({"seq": n}, sort_keys=True), "line",
            source_sha256=source_sha256,
            start_line=i + 1, end_line=i + 1,
            start_offset=len(text[:start_char].encode("utf-8")) if byte_offsets_exact else None,
            end_offset=len(text[:char_pos].encode("utf-8")) if byte_offsets_exact else None,
            details={"source": "hptrack", "mob_name": mob_name},
        )
    return n


NPCLOGGER_LUA_LINE_RE = re.compile(r'^\s*\[(\d+)\]\s*=\s*\{(.*)\},?\s*$')
NPCLOGGER_LUA_FIELD_RE = re.compile(r"\['(\w+)'\]\s*=\s*(?:\"([^\"]*)\"|(-?[\d.]+))")

def _npclogger_lua_look_blob(value) -> bytes | None:
    """Convert a genuinely-present legacy Lua look hex string to the same BLOB shape as .db."""
    if value in (None, ""):
        return None
    if isinstance(value, (bytes, bytearray)):
        return bytes(value)
    try:
        return bytes.fromhex(str(value).strip())
    except (TypeError, ValueError):
        return None


def _npclogger_lua_optional_int(fields: dict, *keys: str) -> int | None:
    """Return a captured integer only when one of the named source fields is actually present."""
    for key in keys:
        if key not in fields:
            continue
        try:
            return int(fields[key])
        except (TypeError, ValueError):
            return None
    return None


def _npclogger_lua_optional_fields(fields: dict) -> tuple:
    """Optional legacy-Lua entity values. Missing source fields deliberately remain NULL."""
    return (
        _npclogger_lua_look_blob(fields.get("look")),
        _npclogger_lua_optional_int(fields, "door_id", "doorid"),
        _npclogger_lua_optional_int(fields, "act_index", "actindex"),
        _npclogger_lua_optional_int(fields, "flags0"),
        _npclogger_lua_optional_int(fields, "flags1"),
        _npclogger_lua_optional_int(fields, "flags2"),
        _npclogger_lua_optional_int(fields, "flags3"),
        _npclogger_lua_optional_int(fields, "legacy_flag"),
        _npclogger_lua_optional_int(fields, "sub_kind", "subkind"),
    )



IDVIEW_LINE_RE = re.compile(
    r'^(Incoming|Outgoing) Packet: (0x[0-9A-Fa-f]{3}) \(([^)]+)\),\s*(.*)$'
)
IDVIEW_ENTITY_RE = re.compile(r'(?:NPC|Actor):\s*(\d+)\s*\(([^)]*)\)')
KI_HEADER_RE = re.compile(r'^\[([\d\- :]+)\]\s+(Lost KI|Obtained KI)\s*$', re.MULTILINE)
KI_PAIR_RE = re.compile(r'\{\s*"(\w+)"\s*,\s*"?([^"\n]*?)"?\s*\}', re.DOTALL)


def ingest_kitrack(con, capture_id, src: Source, relname: str) -> int:
    """KITrack key-item events with exact header-delimited source block provenance."""
    source_bytes = src.read_bytes(relname)
    text = source_bytes.decode("utf-8", "replace")
    byte_offsets_exact = text.encode("utf-8") == source_bytes
    source_sha256 = capture_integrity.sha256_bytes(source_bytes)
    headers = [(m.start(), m.group(1), m.group(2)) for m in KI_HEADER_RE.finditer(text)]
    con.execute(
        "DELETE FROM capture_row_locators WHERE capture_id=? AND filename=? AND target_table='capture_ki_events'",
        (capture_id, relname),
    )
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
        capture_integrity.record_row_locator(
            con, capture_id, relname, "capture_ki_events",
            json.dumps({"seq": n}, sort_keys=True), "block",
            source_sha256=source_sha256,
            start_line=text.count("\n", 0, pos) + 1,
            end_line=text.count("\n", 0, end) + (0 if end > 0 and text[end - 1:end] == "\n" else 1),
            start_offset=len(text[:pos].encode("utf-8")) if byte_offsets_exact else None,
            end_offset=len(text[:end].encode("utf-8")) if byte_offsets_exact else None,
            details={"source": "kitrack", "timestamp": ts, "event_type": event_type,
                     "keyitem_id": keyitem_id, "keyitem_name": fields.get("Name")},
        )
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
    """Ingest CapLog while preserving exact physical source spans for every emitted row."""
    source_bytes = src.read_bytes(relname)
    text = source_bytes.decode("utf-8", "replace")
    byte_offsets_exact = text.encode("utf-8") == source_bytes
    source_sha256 = capture_integrity.sha256_bytes(source_bytes)
    raw_lines = text.splitlines(keepends=True)
    lines = [raw.rstrip("\r\n") for raw in raw_lines]
    line_starts = []
    char_pos = 0
    for raw in raw_lines:
        line_starts.append(char_pos)
        char_pos += len(raw)

    def locator_span(start_idx: int, end_idx: int) -> dict:
        start_char = line_starts[start_idx]
        end_char = line_starts[end_idx] + len(raw_lines[end_idx])
        return {
            "start_line": start_idx + 1,
            "end_line": end_idx + 1,
            "start_offset": len(text[:start_char].encode("utf-8")) if byte_offsets_exact else None,
            "end_offset": len(text[:end_char].encode("utf-8")) if byte_offsets_exact else None,
        }

    con.execute(
        """DELETE FROM capture_row_locators
           WHERE capture_id=? AND filename=? AND target_table IN
           ('capture_events','capture_eventview','capture_hp_events','capture_caplog_chat',
            'capture_chat_observations')""",
        (capture_id, relname),
    )

    events_n = hp_n = eview_n = chat_n = 0
    zone_db = None
    event_local = hp_local = eview_local = 0

    i, n_lines = 0, len(lines)
    while i < n_lines:
        source_line_idx = i
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
                if ev_m and i < n_lines:
                    field_line_idx = i
                    direction, opcode, packet_class, gp_command = ev_m.groups()
                    field_line = lines[i].strip()
                    i += 1
                    fields = _parse_caplog_eview_fields(field_line)
                    entity_id = entity_name = None
                    for k in EVENTVIEW_ENTITY_KEYS:
                        if k in fields:
                            em = re.match(r'(\d+)\s*(?:\(([^)]*)\))?', fields[k])
                            if em and int(em.group(1)):
                                entity_id, entity_name = int(em.group(1)), em.group(2) or None
                                break
                    seq = CAPLOG_SEQ_BASE + eview_local
                    con.execute("""INSERT OR REPLACE INTO capture_eventview
                        (capture_id, zone_db, seq, ts, direction, opcode, packet_class, gp_command,
                         entity_id, mes_num, message_number, fields_json)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                        (capture_id, zone_db, seq, ts, direction, opcode,
                         packet_class, gp_command, entity_id, None, None, json.dumps(fields)))
                    capture_integrity.record_row_locator(
                        con, capture_id, relname, "capture_eventview",
                        json.dumps({"zone_db": zone_db, "seq": seq}, sort_keys=True), "block",
                        source_sha256=source_sha256,
                        details={"source": "caplog", "tag": tag, "timestamp": ts,
                                 "opcode": opcode, "packet_class": packet_class,
                                 "gp_command": gp_command},
                        **locator_span(source_line_idx, field_line_idx),
                    )
                    eview_local += 1
                    eview_n += 1
                    if entity_id and entity_name:
                        entity_profile.record_field(
                            con, "npc", entity_id, "capture_name", "capture", entity_name
                        )
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
                    seq = CAPLOG_SEQ_BASE + event_local
                    con.execute("""INSERT OR REPLACE INTO capture_events
                        (capture_id, zone_db, seq, direction, opcode, opcode_name, entity_id,
                         entity_name, event_hex, option, message_id, params_raw)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                        (capture_id, zone_db, seq, direction, opcode,
                         opcode_name, entity_id, entity_name, event_hex, option, message_id,
                         params_raw))
                    capture_integrity.record_row_locator(
                        con, capture_id, relname, "capture_events",
                        json.dumps({"zone_db": zone_db, "seq": seq}, sort_keys=True), "line",
                        source_sha256=source_sha256,
                        details={"source": "caplog", "tag": tag, "timestamp": ts,
                                 "opcode": opcode, "opcode_name": opcode_name},
                        **locator_span(source_line_idx, source_line_idx),
                    )
                    event_local += 1
                    events_n += 1
                    if entity_id and entity_name:
                        entity_profile.record_field(
                            con, "npc", entity_id, "capture_name", "capture", entity_name
                        )
            elif tag == "HP Track":
                hp_m = CAPLOG_HP_KILL_RE.match(body)
                if hp_m:
                    mob_name, hp_low, hp_high = hp_m.groups()
                    seq = CAPLOG_SEQ_BASE + hp_local
                    con.execute("""INSERT OR REPLACE INTO capture_hp_events
                        (capture_id, seq, mob_name, hp_low, hp_high) VALUES (?,?,?,?,?)""",
                        (capture_id, seq, mob_name, int(hp_low), int(hp_high)))
                    capture_integrity.record_row_locator(
                        con, capture_id, relname, "capture_hp_events",
                        json.dumps({"seq": seq}, sort_keys=True), "line",
                        source_sha256=source_sha256,
                        details={"source": "caplog", "tag": tag, "timestamp": ts,
                                 "mob_name": mob_name},
                        **locator_span(source_line_idx, source_line_idx),
                    )
                    hp_local += 1
                    hp_n += 1
            continue

        if CAPLOG_BOOKKEEPING_RE.match(rest):
            continue

        seq = chat_n
        con.execute("""INSERT OR REPLACE INTO capture_caplog_chat
            (capture_id, seq, ts, zone_db, text) VALUES (?,?,?,?,?)""",
            (capture_id, seq, ts, zone_db, rest))
        span = locator_span(source_line_idx, source_line_idx)
        capture_chat.insert_chat_observation(
            con, capture_id,
            ts=ts, direction=None, zone_id=None, zone_db=zone_db, text=rest,
            source_format="caplog",
            source_native_id=f"{relname}:line:{source_line_idx + 1}",
            filename=relname, source_sha256=source_sha256, locator_basis="line",
            details={"source": "caplog"},
            **span,
        )
        capture_integrity.record_row_locator(
            con, capture_id, relname, "capture_caplog_chat",
            json.dumps({"seq": seq}, sort_keys=True), "line",
            source_sha256=source_sha256,
            details={"source": "caplog", "timestamp": ts, "zone_db": zone_db},
            **span,
        )
        chat_n += 1

    return events_n, hp_n, eview_n, chat_n

EVENTVIEW_HEADER_RE = re.compile(
    r'^\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\]\s+(<<|>>)\s+\[(0x[0-9A-Fa-f]{3})\]\s+(\w+)\*?\s+\((\w+)\)\s*$',
    re.MULTILINE)
# Newer EventView: no [0xNNN]/packet-class in the header -- "[ts] << GP_SERV_COMMAND_X (note)"; the real
# opcode is the nested header.id in the body (decimal).
EVENTVIEW_HEADER_NEW_RE = re.compile(
    r'^\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})(?:\.\d+)?\]\s+(<<|>>)\s+(GP_\w+)(?:\s+\(([^)\n]*)\))?\s*$',
    re.MULTILINE)
EVENTVIEW_HEADER_ID_RE = re.compile(r'header\s*=\s*\{[^}]*?\bid\s*=\s*(\d+)', re.DOTALL)
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


def ingest_eventview(
    con, capture_id, src: Source, relname: str, *, source_filename: str | None = None
) -> int:
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
    source_sha256 = capture_integrity.sha256_bytes(src.read_bytes(relname))
    headers = [(m.start(), m.end(), m.group(1), m.group(2), m.group(3), m.group(4), m.group(5))
               for m in EVENTVIEW_HEADER_RE.finditer(text)]
    # newer format: opcode is resolved from the body below (marker None)
    headers += [(m.start(), m.end(), m.group(1), m.group(2), None, m.group(4) or "", m.group(3))
                for m in EVENTVIEW_HEADER_NEW_RE.finditer(text)]
    headers.sort(key=lambda h: h[0])
    n = 0
    for hstart, hend, ts, direction, opcode, packet_class, gp_command in headers:
        rest = text[hend:]
        brace_pos = rest.find("{")
        if brace_pos == -1:
            continue
        if opcode is None:  # newer format: next header must not precede the body's brace
            nxt = EVENTVIEW_HEADER_NEW_RE.search(rest)
            if nxt and nxt.start() < brace_pos:
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
        if opcode is None:
            hm = EVENTVIEW_HEADER_ID_RE.search(body)
            if not hm:
                continue  # no real opcode in the block -- never guess one
            opcode = "0x%03X" % int(hm.group(1))

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
        block_end = hend + j + 1
        capture_integrity.record_row_locator(
            con,
            capture_id,
            source_filename or relname,
            "capture_eventview",
            json.dumps({"zone_db": zone_db, "seq": n}, sort_keys=True),
            "block",
            source_sha256=source_sha256,
            start_line=text.count("\n", 0, hstart) + 1,
            end_line=text.count("\n", 0, block_end) + 1,
            start_offset=len(text[:hstart].encode("utf-8")),
            end_offset=len(text[:block_end].encode("utf-8")),
            details={"opcode": opcode, "packet_class": packet_class, "gp_command": gp_command},
        )
        n += 1
    return n


EVENTVIEW_SESSION_RAW_HEADER_RE = re.compile(
    r'(?m)^\s*(INCOMING|OUTGOING)\s*[<>].*?\((0x[0-9A-Fa-f]{3})\):.*$'
)


def ingest_eventview_session_simple(con, capture_id, src: Source, relname: str) -> int:
    """Preserve whole-session EventView decoded records without inventing a zone."""
    return ingest_idview_simple(con, capture_id, src, relname, zone_db_override=ZONE_UNKNOWN)


def ingest_eventview_session_raw(con, capture_id, src: Source, relname: str) -> int:
    """Preserve whole-session EventView raw packets with unknown zone/time attribution."""
    source_bytes = src.read_bytes(relname)
    text = source_bytes.decode("utf-8", "replace")
    byte_offsets_exact = text.encode("utf-8") == source_bytes
    source_sha256 = capture_integrity.sha256_bytes(source_bytes)

    old_locators = con.execute(
        """SELECT row_key FROM capture_row_locators
           WHERE capture_id=? AND filename=? AND target_table='capture_raw_packets'""",
        (capture_id, relname),
    ).fetchall()
    for (row_key_raw,) in old_locators:
        try:
            old_seq = json.loads(row_key_raw).get("seq")
        except Exception:
            old_seq = None
        if old_seq is not None:
            con.execute(
                "DELETE FROM capture_raw_packets WHERE capture_id=? AND seq=?",
                (capture_id, int(old_seq)),
            )
    con.execute(
        """DELETE FROM capture_row_locators
           WHERE capture_id=? AND filename=? AND target_table='capture_raw_packets'""",
        (capture_id, relname),
    )

    headers = list(EVENTVIEW_SESSION_RAW_HEADER_RE.finditer(text))
    count = 0
    for index, match in enumerate(headers):
        block_end = headers[index + 1].start() if index + 1 < len(headers) else len(text)
        block = text[match.end():block_end]
        hex_bytes = []
        for rowmatch in PACKETLOGGER_HEXROW_RE.finditer(block):
            for token in rowmatch.group(1).split():
                if token != "--":
                    hex_bytes.append(token)
        if not hex_bytes:
            continue
        start_char = match.start()
        direction_word, opcode = match.groups()
        raw_packet_ingest.insert_raw_packet(
            con, capture_id,
            ts=None,
            direction="incoming" if direction_word == "INCOMING" else "outgoing",
            opcode=opcode,
            raw_hex="".join(hex_bytes),
            zone_id=None,
            source_format="eventview_session_raw",
            source_native_id=f"{relname}:block:{index}",
            filename=relname,
            source_sha256=source_sha256,
            locator_basis="block",
            start_line=text.count("\n", 0, start_char) + 1,
            end_line=text.count("\n", 0, block_end) + 1,
            start_offset=len(text[:start_char].encode("utf-8")) if byte_offsets_exact else None,
            end_offset=len(text[:block_end].encode("utf-8")) if byte_offsets_exact else None,
            details={"zone_attribution": "unknown", "session_scope": True},
        )
        count += 1
    return count


PACKETLOGGER_HEADER_RE = re.compile(
    r'\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})(?:\.\d+)?\]'  # newer PacketLogger adds .mmm; ts stays whole-second
)
PACKETLOGGER_HEXROW_RE = re.compile(
    r'^\s*\d+ \|((?:\s+[0-9A-Fa-f]{2}|\s+--){1,16})\s+\d+ \|', re.MULTILINE
)


def parse_packetlogger_records(text: str, opcode: str) -> list[dict]:
    """Parse packet blocks while preserving exact physical source spans.

    This stays linear in source size. Historical PacketViewer files can contain tens of
    thousands of blocks; rescanning the complete prefix for every line number made provenance
    extraction quadratic and could make a valid capture appear to hang.
    """
    out = []
    headers = [(m.start(), m.end(), m.group(1)) for m in PACKETLOGGER_HEADER_RE.finditer(text)]
    newline_positions = [m.start() for m in re.finditer("\\n", text)]
    for i, (hstart, hend, ts) in enumerate(headers):
        block_end = headers[i + 1][0] if i + 1 < len(headers) else len(text)
        block = text[hend:block_end]
        hex_bytes = []
        for rowmatch in PACKETLOGGER_HEXROW_RE.finditer(block):
            for tok in rowmatch.group(1).split():
                if tok != "--":
                    hex_bytes.append(tok)
        if hex_bytes:
            header_end = text.find("\n", hstart)
            if header_end < 0 or header_end > block_end:
                header_end = block_end
            header_line = text[hstart:header_end]
            out.append({
                "ts": ts,
                "raw_hex": "".join(hex_bytes),
                "is_injected": "Injected" in header_line,
                "is_blocked": "Blocked" in header_line,
                "start_char": hstart,
                "end_char": block_end,
                "start_line": bisect.bisect_left(newline_positions, hstart) + 1,
                "end_line": bisect.bisect_left(newline_positions, block_end) + 1,
            })
    return out


def _utf8_offsets_for_positions(text: str, positions) -> dict[int, int]:
    """Resolve many UTF-8 byte offsets in one forward pass."""
    wanted = sorted(set(int(p) for p in positions))
    out: dict[int, int] = {}
    prev_char = 0
    prev_bytes = 0
    for pos in wanted:
        if pos < prev_char or pos < 0 or pos > len(text):
            continue
        prev_bytes += len(text[prev_char:pos].encode("utf-8"))
        out[pos] = prev_bytes
        prev_char = pos
    return out

def parse_packetlogger_log(text: str, opcode: str) -> list[tuple[str, str]]:
    """Compatibility wrapper returning only timestamp + compact hex."""
    return [(row["ts"], row["raw_hex"]) for row in parse_packetlogger_records(text, opcode)]


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
    print(
        f"[capture {capture_id}] PacketViewer/PacketLogger: parsing {len(relnames)} per-opcode files...",
        flush=True,
    )
    for relname in relnames:
        direction = "incoming" if "/incoming/" in relname.lower() else (
            "outgoing" if "/outgoing/" in relname.lower() else "unknown")
        opcode = Path(relname).stem.upper()
        source_bytes = src.read_bytes(relname)
        text = source_bytes.decode("utf-8", "replace")
        byte_offsets_exact = text.encode("utf-8") == source_bytes
        source_sha256 = capture_integrity.sha256_bytes(source_bytes)
        records = parse_packetlogger_records(text, opcode)
        byte_offsets = (
            _utf8_offsets_for_positions(
                text,
                [pos for record in records for pos in (record["start_char"], record["end_char"])],
            )
            if byte_offsets_exact else {}
        )
        for record in records:
            start_offset = byte_offsets.get(record["start_char"]) if byte_offsets_exact else None
            end_offset = byte_offsets.get(record["end_char"]) if byte_offsets_exact else None
            lower_relname = relname.lower()
            source_format = (
                "packetviewer"
                if lower_relname.startswith("packetviewer/") or "/packetviewer/" in lower_relname
                else "packetlogger"
            )
            header = raw_packet_ingest.decode_packet_header(record["raw_hex"])
            all_packets.append((
                record["ts"], direction, opcode, record["raw_hex"], relname, source_sha256,
                record["start_line"], record["end_line"], start_offset, end_offset,
                source_format, f"{relname}:{record['start_line']}",
                header["packet_size"], header["sync_id"],
                record["is_injected"], record["is_blocked"],
            ))

    print(
        f"[capture {capture_id}] PacketViewer/PacketLogger: parsed {len(all_packets)} packets; indexing...",
        flush=True,
    )
    all_packets.sort(key=lambda p: (p[0], p[4], p[6]))

    # Replace only this raw-log family. Other canonical raw sources (PacketDB, Packeteer,
    # NPCLogger-preserved bytes) remain independent evidence rows in the same capture. Delete
    # locator-owned legacy rows too: databases created before source_format existed have NULL
    # there, but their exact seq locators still prove ownership by these PacketViewer files.
    old_locator_rows = con.execute(
        """SELECT row_key FROM capture_row_locators
           WHERE capture_id=? AND target_table='capture_raw_packets'
             AND filename IN (%s)""" % ",".join("?" for _ in relnames),
        [capture_id] + list(relnames),
    ).fetchall()
    for (row_key_raw,) in old_locator_rows:
        try:
            old_seq = json.loads(row_key_raw).get("seq")
        except Exception:
            old_seq = None
        if old_seq is not None:
            con.execute(
                "DELETE FROM capture_raw_packets WHERE capture_id=? AND seq=?",
                (capture_id, int(old_seq)),
            )
    con.execute(
        """DELETE FROM capture_raw_packets
           WHERE capture_id=? AND source_format IN ('packetlogger','packetviewer')""",
        (capture_id,),
    )
    con.execute(
        """DELETE FROM capture_row_locators
           WHERE capture_id=? AND target_table='capture_raw_packets'
             AND filename IN (%s)""" % ",".join("?" for _ in relnames),
        [capture_id] + list(relnames),
    )
    next_seq = con.execute(
        "SELECT COALESCE(MAX(seq),-1)+1 FROM capture_raw_packets WHERE capture_id=?",
        (capture_id,),
    ).fetchone()[0]
    for offset, (
        ts, direction, opcode, hexstr, relname, source_sha256,
        start_line, end_line, start_offset, end_offset,
        source_format, source_native_id, packet_size, sync_id, is_injected, is_blocked,
    ) in enumerate(all_packets):
        seq = int(next_seq) + offset
        con.execute("""INSERT OR REPLACE INTO capture_raw_packets
            (capture_id,seq,ts,direction,opcode,raw_hex,zone_id,packet_size,sync_id,
             is_injected,is_blocked,source_format,source_native_id)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (capture_id,seq,ts,direction,opcode,hexstr,None,packet_size,sync_id,
             int(is_injected),int(is_blocked),source_format,source_native_id))
        capture_integrity.record_row_locator(
            con,
            capture_id,
            relname,
            "capture_raw_packets",
            json.dumps({"seq": seq}, sort_keys=True),
            "block",
            source_sha256=source_sha256,
            start_line=start_line,
            end_line=end_line,
            start_offset=start_offset,
            end_offset=end_offset,
            details={
                "opcode": opcode, "direction": direction, "timestamp": ts,
                "source_format": source_format, "source_native_id": source_native_id,
                "packet_size": packet_size, "sync_id": sync_id,
                "is_injected": bool(is_injected), "is_blocked": bool(is_blocked),
            },
        )
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


ZONE_UNKNOWN = "__UNKNOWN__"
_ZONE_FROM_FILENAME = object()


def ingest_idview_simple(
    con, capture_id, src: Source, relname: str, *, zone_db_override=_ZONE_FROM_FILENAME
) -> int:
    """Ingest either real IDView simple format with exact source line/block provenance."""
    zone_db = Path(relname).stem if zone_db_override is _ZONE_FROM_FILENAME else zone_db_override
    source_bytes = src.read_bytes(relname)
    text = source_bytes.decode("utf-8", "replace")
    byte_offsets_exact = text.encode("utf-8") == source_bytes
    source_sha256 = capture_integrity.sha256_bytes(source_bytes)
    con.execute(
        "DELETE FROM capture_row_locators WHERE capture_id=? AND filename=? AND target_table='capture_events'",
        (capture_id, relname),
    )

    first_line = next((l.strip() for l in text.splitlines() if l.strip()), "")
    if IDVIEW2_HEADER_RE.match(first_line):
        return _ingest_idview_simple_v2(
            con, capture_id, zone_db, text,
            relname=relname, source_sha256=source_sha256,
            byte_offsets_exact=byte_offsets_exact,
        )

    raw_lines = text.splitlines(keepends=True)
    n = 0
    char_pos = 0
    for i, raw_line in enumerate(raw_lines):
        line = raw_line.rstrip("\r\n").strip()
        start_char = char_pos
        char_pos += len(raw_line)
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
        capture_integrity.record_row_locator(
            con, capture_id, relname, "capture_events",
            json.dumps({"zone_db": zone_db, "seq": n}, sort_keys=True), "line",
            source_sha256=source_sha256,
            start_line=i + 1, end_line=i + 1,
            start_offset=len(text[:start_char].encode("utf-8")) if byte_offsets_exact else None,
            end_offset=len(text[:char_pos].encode("utf-8")) if byte_offsets_exact else None,
            details={"source": "idview_simple_v1", "opcode": opcode, "opcode_name": opcode_name},
        )
        n += 1
        if entity_id and entity_name:
            entity_profile.record_field(con, "npc", entity_id, "capture_name", "capture", entity_name)
    return n


def _ingest_idview_simple_v2(
    con, capture_id, zone_db, text: str, *,
    relname: str, source_sha256: str, byte_offsets_exact: bool,
) -> int:
    n = 0
    for match in re.finditer(r'(?ms)(^\s*(?:INCOMING|OUTGOING)\s*[<>].*?)(?=\n\s*\n|\Z)', text):
        raw_block = match.group(1)
        block = raw_block.strip()
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
        start, end = match.start(1), match.end(1)
        capture_integrity.record_row_locator(
            con, capture_id, relname, "capture_events",
            json.dumps({"zone_db": zone_db, "seq": n}, sort_keys=True), "block",
            source_sha256=source_sha256,
            start_line=text.count("\n", 0, start) + 1,
            end_line=text.count("\n", 0, end) + (0 if end > 0 and text[end - 1:end] == "\n" else 1),
            start_offset=len(text[:start].encode("utf-8")) if byte_offsets_exact else None,
            end_offset=len(text[:end].encode("utf-8")) if byte_offsets_exact else None,
            details={"source": "idview_simple_v2", "opcode": opcode, "opcode_name": opcode_name},
        )
        n += 1
        if entity_id and entity_name:
            entity_profile.record_field(con, "npc", entity_id, "capture_name", "capture", entity_name)
    return n

def ingest_npclogger_lua(con, capture_id, src: Source, relname: str, leg: int = 1) -> tuple[int, int]:
    """Ingest legacy NPCLogger Lua snapshots with exact source-line provenance."""
    zone_db = Path(relname).stem
    source_bytes = src.read_bytes(relname)
    text = source_bytes.decode("utf-8", "replace")
    byte_offsets_exact = text.encode("utf-8") == source_bytes
    source_sha256 = capture_integrity.sha256_bytes(source_bytes)
    raw_lines = text.splitlines(keepends=True)
    con.execute(
        """DELETE FROM capture_row_locators
           WHERE capture_id=? AND filename=?
             AND target_table IN ('capture_npc_entries','capture_npc_path','capture_raw_packets')""",
        (capture_id, relname),
    )
    n_entries = n_path = 0
    seen_ids = set()
    char_pos = 0
    for step, raw_line in enumerate(raw_lines):
        line = raw_line.rstrip("\r\n")
        start_char = char_pos
        char_pos += len(raw_line)
        m = NPCLOGGER_LUA_LINE_RE.match(line)
        if not m:
            continue
        entity_id = int(m.group(1))
        fields = {}
        for fm in NPCLOGGER_LUA_FIELD_RE.finditer(m.group(2)):
            key, str_val, num_val = fm.group(1), fm.group(2), fm.group(3)
            fields[key.lower()] = str_val if str_val is not None else float(num_val)
        if "x" not in fields or "z" not in fields:
            continue

        x, y, z = fields.get("x"), fields.get("y", 0.0), fields.get("z")
        dir_ = int(fields.get("r", 0))
        con.execute("""INSERT OR REPLACE INTO capture_npc_path
            (capture_id, zone_db, entity_id, leg, step, x, y, z, dir, delta)
            VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (capture_id, zone_db, entity_id, leg, step, x, y, z, dir_, 0))
        capture_integrity.record_row_locator(
            con, capture_id, relname, "capture_npc_path",
            json.dumps(
                {"zone_db": zone_db, "entity_id": entity_id, "leg": leg, "step": step},
                sort_keys=True,
            ),
            "line", source_sha256=source_sha256,
            start_line=step + 1, end_line=step + 1,
            start_offset=len(text[:start_char].encode("utf-8")) if byte_offsets_exact else None,
            end_offset=len(text[:char_pos].encode("utf-8")) if byte_offsets_exact else None,
            details={"source": "npclogger_lua", "leg": leg},
        )
        if fields.get("raw_packet"):
            raw_packet_ingest.promote_npclogger_raw_packet(
                con, capture_id,
                relname=relname, source_sha256=source_sha256,
                line_number=step + 1, raw_hex=fields.get("raw_packet"),
                start_offset=len(text[:start_char].encode("utf-8")) if byte_offsets_exact else None,
                end_offset=len(text[:char_pos].encode("utf-8")) if byte_offsets_exact else None,
                entity_id=entity_id,
            )
        n_path += 1

        (look_blob, door_id, act_index, flags0, flags1, flags2, flags3,
         legacy_flag, sub_kind) = _npclogger_lua_optional_fields(fields)
        con.execute("""INSERT INTO capture_npc_entries
            (capture_id, zone_db, entity_id, name, model_id, x, y, z, dir, hpp,
             legacy_flags, legacy_status, legacy_animation, speed, created_at, updated_at,
             legacy_look, door_id, act_index, flags0, flags1, flags2, flags3, legacy_flag,
             sub_kind)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(capture_id, zone_db, entity_id) DO UPDATE SET
                name=excluded.name, model_id=excluded.model_id,
                x=excluded.x, y=excluded.y, z=excluded.z, dir=excluded.dir, hpp=excluded.hpp,
                legacy_flags=excluded.legacy_flags, legacy_status=excluded.legacy_status,
                legacy_animation=excluded.legacy_animation, speed=excluded.speed,
                created_at=excluded.created_at, updated_at=excluded.updated_at,
                legacy_look=COALESCE(excluded.legacy_look, capture_npc_entries.legacy_look),
                door_id=COALESCE(excluded.door_id, capture_npc_entries.door_id),
                act_index=COALESCE(excluded.act_index, capture_npc_entries.act_index),
                flags0=COALESCE(excluded.flags0, capture_npc_entries.flags0),
                flags1=COALESCE(excluded.flags1, capture_npc_entries.flags1),
                flags2=COALESCE(excluded.flags2, capture_npc_entries.flags2),
                flags3=COALESCE(excluded.flags3, capture_npc_entries.flags3),
                legacy_flag=COALESCE(excluded.legacy_flag, capture_npc_entries.legacy_flag),
                sub_kind=COALESCE(excluded.sub_kind, capture_npc_entries.sub_kind)""",
            (capture_id, zone_db, entity_id, fields.get("name"), None, x, y, z, dir_, None,
             int(fields.get("flags", 0)), int(fields.get("status", 0)),
             int(fields.get("animation", 0)), int(fields.get("speed", 0)), None, None,
             look_blob, door_id, act_index, flags0, flags1, flags2, flags3, legacy_flag,
             sub_kind))
        capture_integrity.record_row_locator(
            con, capture_id, relname, "capture_npc_entries",
            json.dumps({"zone_db": zone_db, "entity_id": entity_id}, sort_keys=True),
            "line", source_sha256=source_sha256,
            start_line=step + 1, end_line=step + 1,
            start_offset=len(text[:start_char].encode("utf-8")) if byte_offsets_exact else None,
            end_offset=len(text[:char_pos].encode("utf-8")) if byte_offsets_exact else None,
            details={"source": "npclogger_lua", "leg": leg, "last_seen_snapshot": True},
        )
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
           mission_name_override: str | None = None, force: bool = False) -> int:
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
    source_path = f"{path}::{subroot}" if subroot else str(path)
    try:
        src = Source(path)
    except Exception as _ex:      # unreadable/corrupt archive: nothing parsed -- put it in the exception queue
        _report_ingest_failure(con, source_path, path, _ex, content_type, subroot)
        raise
    try:
        existing = con.execute("SELECT capture_id FROM captures WHERE source_path=?",
                                (source_path,)).fetchone()
        if existing:
            print(f"already ingested as capture_id={existing[0]} ({path.name}"
                  f"{f'::{subroot}' if subroot else ''}) -- skipping. "
                  f"Delete its rows first if you want to re-ingest.")
            return existing[0]

        # Content-fingerprint precheck (zip central directory / folder listing -- no parsing): the same
        # content under another name/location is a duplicate. Skipped for bundle subroots (the bundle
        # fingerprint covers every session) and with --force.
        fp_key = None
        if not subroot:
            try:
                from workbench.captures import source_fingerprint as _sf
                fp_key, dup = _sf.precheck(con, str(path))
                if dup and not force and con.execute("SELECT 1 FROM captures WHERE capture_id=?", (dup[0],)).fetchone():
                    print(f"duplicate content: {path.name} matches capture_id={dup[0]} ({dup[1]}) -- skipping "
                          f"(re-run with --force to ingest anyway).")
                    from workbench.captures import review_queue as _rq
                    _rq.raise_item(con, "duplicate_source", source_path, dup[0], "",
                                   {"reason": "identical content to capture #%s already ingested from %s -- skipped" % (dup[0], dup[1]),
                                    "path": str(path), "duplicate_of": dup[0], "duplicate_path": dup[1]})
                    return dup[0]
            except Exception as _ex:
                print(f"  [fingerprint precheck skipped: {_ex}]")

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

        file_results: list[dict] = []
        counts = ingest_from_source(con, capture_id, src, subroot=subroot, file_results=file_results)
        recompute_zones(con, capture_id)
        try:
            from workbench.captures import msgid_shift as _ms
            con.commit()
            _ms.update_after_ingest(con, capture_id)
        except Exception as _ex:
            print(f"  [shift check skipped: {_ex}]")
        try:
            from workbench.captures import review_queue as _rq
            _rq.report_file_results(con, source_path, capture_id, file_results)   # per-file parse errors / unrecognized files
            _rq.scan_capture(con, capture_id)   # exception queue: empty ingest / unlinked post / unresolved zones
        except Exception as _ex:
            print(f"  [review scan skipped: {_ex}]")

        con.commit()
        if fp_key:
            try:
                from workbench.captures import source_fingerprint as _sf
                _sf.record(con, str(path), capture_id)
            except Exception as _ex:
                print(f"  [fingerprint record skipped: {_ex}]")
        zones = json.loads(con.execute("SELECT zones FROM captures WHERE capture_id=?", (capture_id,)).fetchone()[0] or "[]")
        print(f"[{capture_id}] {label}: {counts['npc_entries']} npc entries, {counts['npc_hist']} history "
              f"deltas, {counts['path']} path points, {counts['actions']} actions, {counts['hp']} hp events, "
              f"{counts['events']} idview events, {counts['ki']} ki events, {counts['eventview']} eventview packets, "
              f"{counts['level_range']} level-range entries, {counts['attack_delay']} attack-delay entries -- "
              f"content_type={content_type} zones={zones} mission={mission_name!r} "
              f"(capturer={capturer}, build={meta.get('client_build', '?')!r})")
        return capture_id
    except Exception as _ex:
        try:
            con.rollback()
        except Exception:
            pass
        _report_ingest_failure(con, source_path, path, _ex, content_type, subroot)
        raise
    finally:
        src.close()


def _report_ingest_failure(con, source_path, path, ex, content_type, subroot):
    """Ingest threw: record it in the exception queue (with a copy of the archive for manual review).
    Never raises -- the caller re-raises the original error."""
    try:
        from workbench.captures import review_queue as _rq
        row = con.execute("SELECT capture_id FROM captures WHERE source_path=?", (source_path,)).fetchone()
        _rq.report_ingest_failure(con, source_path, path, ex, row[0] if row else None, content_type, subroot)
    except Exception as _e2:
        print(f"  [could not queue ingest failure for {source_path}: {_e2}]")


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
    result_sink = file_results if file_results is not None else []

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
            if result_sink is not None:
                result_sink.append({"filename": relname, "rows": 0, "error": str(ex)})
            return 0
        if result_sink is not None:
            result_sink.append({"filename": relname, "rows": rows, "error": None})
        return rows

    def run2(relname, fn, *args):
        """For an ingester returning a (a, b) row-count tuple."""
        matched_names.add(relname)
        try:
            a, b = fn(*args)
        except Exception as ex:
            if result_sink is not None:
                result_sink.append({"filename": relname, "rows": 0, "error": str(ex)})
            return 0, 0
        if result_sink is not None:
            result_sink.append({"filename": relname, "rows": a + b, "error": None})
        return a, b

    def run3(relname, fn, *args):
        """For an ingester returning an (a, b, c) row-count tuple."""
        matched_names.add(relname)
        try:
            a, b, c = fn(*args)
        except Exception as ex:
            if result_sink is not None:
                result_sink.append({"filename": relname, "rows": 0, "error": str(ex)})
            return 0, 0, 0
        if result_sink is not None:
            result_sink.append({"filename": relname, "rows": a + b + c, "error": None})
        return a, b, c

    def run4(relname, fn, *args):
        """For an ingester returning an (a, b, c, d) row-count tuple."""
        matched_names.add(relname)
        try:
            a, b, c, d = fn(*args)
        except Exception as ex:
            if result_sink is not None:
                result_sink.append({"filename": relname, "rows": 0, "error": str(ex)})
            return 0, 0, 0, 0
        if result_sink is not None:
            result_sink.append({"filename": relname, "rows": a + b + c + d, "error": None})
        return a, b, c, d

    counts = {"npc_entries": 0, "npc_hist": 0, "actions": 0, "path": 0, "hp": 0, "events": 0,
              "ki": 0, "eventview": 0, "level_range": 0, "attack_delay": 0, "raw_packets": 0,
              "pc_path": 0, "widescan": 0, "caplog_chat": 0, "structured": 0}
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
    for relname in sfind(r'(?:^|/)logs/[^/]+_\d{4}\.\d{2}\.\d{2}\.log$'):
        counts["caplog_chat"] += run1(
            relname, ingest_windower_logger, con, capture_id, src, relname
        )
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
    pl_files = sfind(r'(?:Packet(?:Logger|Viewer)|(?:^|/)logs)/(incoming|outgoing)/0x[0-9A-Fa-f]{3}\.log$')  # bare 'logs/' = 2021 PacketViewer layout (no wrapper folder)
    if pl_files:
        matched_names.update(pl_files)
        try:
            pl_rows = ingest_packetlogger(con, capture_id, src, pl_files)
        except Exception as ex:
            pl_rows = 0
            if result_sink is not None:
                for relname in pl_files:
                    result_sink.append({"filename": relname, "rows": 0, "error": str(ex)})
        else:
            if result_sink is not None:
                # One combined call across every raw-packet-log file -- rows aren't attributable
                # to any single file, so report the real total once (against the first file) and
                # the rest as "ok" with no per-file row count, rather than fabricating a split.
                for i, relname in enumerate(pl_files):
                    result_sink.append({"filename": relname, "rows": pl_rows if i == 0 else None, "error": None})
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

    # Whole-session EventView files contain real observations that can span multiple zones.
    # Preserve them with explicit unknown-zone attribution rather than dropping them or guessing.
    session_simple_files = sfind(r'[Ee]ventview/(?:[^/]+/)?simple\.log$')
    session_raw_files = sfind(r'[Ee]ventview/(?:[^/]+/)?raw\.log$')
    session_simple_set = set(session_simple_files)
    all_source_names_set = set(src.list_files())
    for relname in session_simple_files:
        counts["events"] += run1(
            relname, ingest_eventview_session_simple, con, capture_id, src, relname
        )
    for relname in session_raw_files:
        counts["raw_packets"] += run1(
            relname, ingest_eventview_session_raw, con, capture_id, src, relname
        )
        peer = relname.rsplit("/", 1)[0] + "/simple.log"
        if peer not in session_simple_set and peer not in all_source_names_set:
            try:
                counts["events"] += ingest_eventview_session_simple(
                    con, capture_id, src, relname
                )
            except Exception as ex:
                if result_sink is not None:
                    result_sink.append({
                        "filename": relname,
                        "rows": 0,
                        "error": f"raw fallback decode failed: {ex}",
                    })

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
        # 2026-09-08, same real Tacocat capture: packetviewer/full.log, incoming.log, outgoing.log
        # (bare, directly under packetviewer/) are a whole-session concatenation of the exact same
        # packets already ingested per-opcode from packetviewer/incoming/0x*.log and
        # packetviewer/outgoing/0x*.log (confirmed live: this capture had both packetviewer/incoming/
        # with 63 real per-opcode files AND this flat incoming.log side by side) -- redundant, not
        # new data, same bucket as the actionview/npclogger redundant views above.
        + sfind(r'[Pp]acket(?:[Ll]ogger|[Vv]iewer)/(?:full|incoming|outgoing)\.log$')
    ):
        matched_names.add(relname)
        if result_sink is not None:
            result_sink.append({"filename": relname, "rows": 0, "error": None})

    # Content-first packet/network adapters: PacketDB and Packeteer already expose decoded
    # FFXI chunks, while PCAP/PCAPNG preserves network frames and promotes only proven plaintext
    # FFXI UDP chunk streams.
    all_source_names = sorted(src.list_files() if subroot is None
                              else [n for n in src.list_files() if n.startswith(subroot + "/")])
    for relname in all_source_names:
        if relname in matched_names:
            continue
        fmt = _capture_source_format(src, relname)
        if fmt not in {"packetdb", "packeteer", "pcap", "pcapng"}:
            continue
        matched_names.add(relname)
        try:
            if fmt == "packetdb":
                rows = raw_packet_ingest.ingest_packetdb(con, capture_id, src, relname)
                counts["raw_packets"] += rows
            elif fmt == "packeteer":
                rows = raw_packet_ingest.ingest_packeteer(con, capture_id, src, relname)
                counts["raw_packets"] += rows
            else:
                frames, chunks, flows, ranges, messages = pcap_ingest.ingest_pcap(con, capture_id, src, relname)
                counts["structured"] += frames + flows + ranges + messages
                counts["raw_packets"] += chunks
                rows = frames + chunks + flows + ranges + messages
            if result_sink is not None:
                result_sink.append({"filename": relname, "rows": rows, "error": None})
        except Exception as ex:
            if result_sink is not None:
                result_sink.append({"filename": relname, "rows": 0, "error": str(ex)})

    # Content-first compatibility pass for auxiliary/past-and-present logger families. Core
    # mission/runtime parsers above retain priority; only otherwise-unmatched files are considered.
    all_source_names = sorted(src.list_files() if subroot is None
                              else [n for n in src.list_files() if n.startswith(subroot + "/")])
    for relname in all_source_names:
        if relname in matched_names:
            continue
        fmt = _capture_source_format(src, relname)
        if fmt not in AUX_STRUCTURED_FORMATS:
            continue
        matched_names.add(relname)
        try:
            rows = ingest_aux_structured(con, capture_id, src, relname, fmt)
            counts.setdefault("structured", 0)
            counts["structured"] += rows
            if result_sink is not None:
                result_sink.append({"filename": relname, "rows": rows, "error": None})
        except Exception as ex:
            if result_sink is not None:
                result_sink.append({"filename": relname, "rows": 0, "error": str(ex)})

    if result_sink is not None:
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
                result_sink.append({"filename": relname, "rows": 0, "error": None})
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
                result_sink.append({"filename": relname, "rows": 0, "error": error})
    # Content-address every real source file and persist parser/table-family lineage.
    result_by_name = {row["filename"]: row for row in result_sink}
    source_names = sorted(src.list_files() if subroot is None
                          else [n for n in src.list_files() if n.startswith(subroot + "/")])
    for relname in source_names:
        row = result_by_name.get(relname, {})
        try:
            data = src.read_bytes(relname)
        except Exception as ex:
            capture_integrity.record_source_file(
                con, capture_id, relname, b"",
                format_detected=None, parser_name=None,
                row_count=row.get("rows"), error=row.get("error") or str(ex),
            )
            continue
        fmt = _capture_source_format(src, relname)
        capture_integrity.record_source_file(
            con, capture_id, relname, data,
            format_detected=fmt, parser_name=fmt,
            row_count=row.get("rows"), error=row.get("error"),
        )
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


def _capture_source_format(src: "Source", relname: str) -> str | None:
    """Best-effort deterministic format identity for source-manifest provenance."""
    lower = relname.lower()
    basename = lower.rsplit("/", 1)[-1]
    if basename in {"manifest.txt", "thumbs.db", "desktop.ini", ".ds_store"}:
        return "manifest" if basename == "manifest.txt" else "benign"
    if lower.endswith((".pcap", ".pcapng")):
        try:
            detected = pcap_ingest.sniff_pcap_format(src.read_bytes(relname))
            if detected:
                return detected
        except Exception:
            return "pcapng" if lower.endswith(".pcapng") else "pcap"
    if re.search(r'npclogger/[^/]+\.db$', lower):
        try:
            return sniff_sqlite_format(src.read_bytes(relname))
        except Exception:
            return "npclogger_db"
    if lower.endswith("actions.db"):
        return "actionview_db"
    if "levelrangetrack/" in lower and lower.endswith(".db"):
        return "levelrange_db"
    if re.search(r'packet(?:logger|viewer)/(incoming|outgoing)/0x[0-9a-f]{3}\.log$', lower):
        return "packetlogger"
    if re.search(r'packet(?:logger|viewer)/(?:full|incoming|outgoing)\.log$', lower):
        # Whole-session flat views duplicate the per-opcode packet files. Recognize by path here
        # so provenance finalization does not decompress/read tens of megabytes again merely to
        # rediscover that already-known redundancy.
        return "packetlogger_redundant"
    if "caplog/" in lower and lower.endswith((".txt", ".log")):
        return "caplog"
    if WINDOWER_LOGGER_FILENAME_RE.search(lower):
        return "windower_logger"
    if "kitrack/" in lower:
        return "kitrack"
    if "hptrack/" in lower:
        return "hptrack"
    if "attackdelay/" in lower:
        return "attackdelay"
    if "pathlog/" in lower and lower.endswith(".csv"):
        return "pc_pathlog_csv" if "/pc_" in lower else "pathlog_csv"
    if "widescan/" in lower:
        return "widescan"
    if "actionview/simple/" in lower:
        return "actionview_simple"
    if re.search(r'eventview/(?:[^/]+/)?simple\.log$', lower):
        return "eventview_session_simple"
    if re.search(r'eventview/(?:[^/]+/)?raw\.log$', lower):
        return "eventview_session_raw"
    if "eventview/" in lower and "/simple/" in lower:
        return "idview_simple"
    if re.search(r'eventview/(?!.*(?:simple|raw)/)[^/]+/[^/]+\.log$', lower):
        return "eventview"
    if "npclogger/" in lower and lower.endswith(".lua"):
        return "npclogger_lua"
    # Auxiliary logger generations are content-addressed rather than path-bound. This lets old
    # bundles, renamed files, and current Captain output share one detection contract.
    try:
        if lower.endswith((".db", ".sqlite", ".sqlite3")):
            detected = sniff_sqlite_format(src.read_bytes(relname))
            if detected:
                return detected
        elif lower.endswith(".csv"):
            detected = sniff_csv_format(src.read_text(relname))
            if detected:
                return detected
        elif lower.endswith((".log", ".txt", ".lua")):
            detected = sniff_text_format(src.read_text(relname))
            if detected:
                return detected
    except Exception:
        pass
    return _sniff_known_format(src, relname)



REBUILDABLE_CAPTURE_FORMATS = {
    "eventview", "idview_simple", "eventview_session_simple", "eventview_session_raw",
    "kitrack", "hptrack", "actionview_simple", "caplog", "windower_logger", "packetlogger",
    "packetdb", "packeteer", "pcap", "pcapng",
    "npclogger_db", "actionview_db", "levelrange_db",
    "npclogger_lua", "pathlog_csv", "pc_pathlog_csv", "widescan", "attackdelay",
} | AUX_STRUCTURED_FORMATS


def _capture_source_origin(con, capture_id: int) -> tuple[Path | None, str | None, str | None]:
    row = con.execute("SELECT source_path FROM captures WHERE capture_id=?", (capture_id,)).fetchone()
    if not row:
        return None, None, "capture not found"
    source_path = row[0] or ""
    if source_path.startswith("manual://"):
        return None, None, "original source bytes were not persisted for this manual/upload capture"
    base, subroot = source_path, None
    if "::" in source_path:
        base, subroot = source_path.rsplit("::", 1)
    path = Path(base)
    if not path.exists():
        return path, subroot, f"original source path is no longer accessible: {path}"
    return path, subroot, None


def capture_rebuild_inventory(con, capture_id: int) -> list[dict]:
    """Return per-source rebuildability without mutating the capture."""
    manifest = con.execute(
        """SELECT filename,sha256,format_detected,row_count,ingest_status
           FROM capture_source_manifest WHERE capture_id=? ORDER BY filename""",
        (capture_id,),
    ).fetchall()
    path, subroot, origin_error = _capture_source_origin(con, capture_id)
    src = None
    names = set()
    try:
        if path is not None and origin_error is None:
            src = Source(path)
            names = set(src.list_files())
        out = []
        for filename, digest, fmt, row_count, status in manifest:
            rebuildable = True
            reason = None
            if fmt not in REBUILDABLE_CAPTURE_FORMATS:
                rebuildable = False
                reason = f"parser family {fmt or 'unknown'} does not yet support safe exact-row rebuild"
            elif origin_error:
                rebuildable = False
                reason = origin_error
            elif filename not in names:
                rebuildable = False
                reason = "source file is no longer present in the original folder/archive"
            else:
                data = src.read_bytes(filename)
                actual = capture_integrity.sha256_bytes(data)
                if actual != digest:
                    rebuildable = False
                    reason = "source bytes changed since ingestion; current manifest hash does not match"
                elif fmt != "packetlogger":
                    locator_count = con.execute(
                        """SELECT COUNT(*) FROM capture_row_locators
                           WHERE capture_id=? AND filename=?""",
                        (capture_id, filename),
                    ).fetchone()[0]
                    if not locator_count:
                        rebuildable = False
                        reason = "no exact row locators exist for the previously normalized rows"
                    else:
                        shared = con.execute(
                            """SELECT 1
                               FROM capture_row_locators a
                               JOIN capture_row_locators b
                                 ON b.capture_id=a.capture_id
                                AND b.target_table=a.target_table
                                AND b.row_key=a.row_key
                                AND b.filename<>a.filename
                               WHERE a.capture_id=? AND a.filename=?
                               LIMIT 1""",
                            (capture_id, filename),
                        ).fetchone()
                        if shared:
                            rebuildable = False
                            reason = "normalized row keys overlap another source file; source ownership is ambiguous"
            out.append({
                "filename": filename,
                "sha256": digest,
                "format": fmt,
                "row_count": row_count,
                "ingest_status": status,
                "rebuildable": rebuildable,
                "reason": reason,
            })
        return out
    finally:
        if src is not None:
            src.close()


def _delete_exact_source_rows(con, capture_id: int, filename: str) -> int:
    """Delete only rows whose real primary keys are proven by this source's exact locators."""
    locators = con.execute(
        """SELECT target_table,row_key
           FROM capture_row_locators
           WHERE capture_id=? AND filename=?
           ORDER BY target_table,row_key""",
        (capture_id, filename),
    ).fetchall()
    if not locators:
        raise ValueError("no exact row locators exist for this source")

    shared = con.execute(
        """SELECT 1
           FROM capture_row_locators a
           JOIN capture_row_locators b
             ON b.capture_id=a.capture_id
            AND b.target_table=a.target_table
            AND b.row_key=a.row_key
            AND b.filename<>a.filename
           WHERE a.capture_id=? AND a.filename=?
           LIMIT 1""",
        (capture_id, filename),
    ).fetchone()
    if shared:
        raise ValueError("cannot safely rebuild: normalized row ownership overlaps another source file")

    deleted = 0
    for target_table, row_key_raw in locators:
        if not re.match(r"^capture_[a-z0-9_]+$", target_table):
            raise ValueError(f"unsafe target table in locator: {target_table}")
        cols = con.execute(f'PRAGMA table_info("{target_table}")').fetchall()
        if not cols:
            raise ValueError(f"locator target table no longer exists: {target_table}")
        pk_cols = [r[1] for r in sorted((r for r in cols if int(r[5] or 0) > 0), key=lambda r: int(r[5]))]
        if "capture_id" not in pk_cols:
            raise ValueError(f"locator target table has no capture_id primary key: {target_table}")
        try:
            row_key = json.loads(row_key_raw)
        except Exception as ex:
            raise ValueError(f"invalid locator row key for {target_table}: {row_key_raw}") from ex
        needed = [name for name in pk_cols if name != "capture_id"]
        if not isinstance(row_key, dict) or any(name not in row_key for name in needed):
            raise ValueError(f"locator row key does not cover the real primary key for {target_table}")
        where = ["capture_id=?"] + [f'"{name}"=?' for name in needed]
        params = [capture_id] + [row_key[name] for name in needed]
        cur = con.execute(f'DELETE FROM "{target_table}" WHERE ' + " AND ".join(where), params)
        deleted += cur.rowcount
    con.execute(
        "DELETE FROM capture_row_locators WHERE capture_id=? AND filename=?",
        (capture_id, filename),
    )
    return deleted


def rebuild_capture_source(con, capture_id: int, filename: str) -> dict:
    """Safely rerun one exact-locator parser without replacing capture metadata or annotations.

    Rebuild is refused unless the original bytes are accessible and still hash-identical to the
    current source manifest. Non-packet formats delete only rows proven by exact primary-key
    locators. PacketLogger/Viewer is rebuilt as one family because its final sequence is a merge
    across every opcode file.
    """
    manifest = con.execute(
        """SELECT sha256,format_detected FROM capture_source_manifest
           WHERE capture_id=? AND filename=?""",
        (capture_id, filename),
    ).fetchone()
    if not manifest:
        raise ValueError("source file is not present in the capture source manifest")
    expected_hash, fmt = manifest
    if fmt not in REBUILDABLE_CAPTURE_FORMATS:
        raise ValueError(f"safe rebuild is not implemented for parser family {fmt or 'unknown'}")

    path, subroot, origin_error = _capture_source_origin(con, capture_id)
    if origin_error:
        raise ValueError(origin_error)
    src = Source(path)
    try:
        names = set(src.list_files())
        if filename not in names:
            raise ValueError("source file is no longer present in the original folder/archive")

        if fmt == "packetlogger":
            packet_rows = con.execute(
                """SELECT filename,sha256 FROM capture_source_manifest
                   WHERE capture_id=? AND format_detected='packetlogger'
                   ORDER BY filename""",
                (capture_id,),
            ).fetchall()
            packet_files = [r[0] for r in packet_rows]
            if not packet_files:
                raise ValueError("no PacketLogger/PacketViewer source family remains in the manifest")
            for packet_filename, packet_hash in packet_rows:
                if packet_filename not in names:
                    raise ValueError(f"packet source is missing: {packet_filename}")
                if capture_integrity.sha256_bytes(src.read_bytes(packet_filename)) != packet_hash:
                    raise ValueError(f"packet source bytes changed since ingestion: {packet_filename}")
            con.execute("SAVEPOINT capture_rebuild")
            try:
                rows = ingest_packetlogger(con, capture_id, src, packet_files)
                con.execute("RELEASE SAVEPOINT capture_rebuild")
            except Exception:
                con.execute("ROLLBACK TO SAVEPOINT capture_rebuild")
                con.execute("RELEASE SAVEPOINT capture_rebuild")
                raise
            for i, packet_filename in enumerate(packet_files):
                data = src.read_bytes(packet_filename)
                capture_integrity.record_source_file(
                    con, capture_id, packet_filename, data,
                    format_detected="packetlogger", parser_name="packetlogger",
                    row_count=rows if i == 0 else None, error=None,
                )
                con.execute(
                    """INSERT OR REPLACE INTO capture_source_files
                       (capture_id,filename,format_detected,ingested_at,row_count,error)
                       VALUES (?,?,?,datetime('now'),?,NULL)""",
                    (capture_id, packet_filename, "packetlogger", rows if i == 0 else None),
                )
            con.commit()
            return {
                "capture_id": capture_id, "filename": filename, "format": fmt,
                "scope": "packetlogger_family", "source_files": packet_files, "rows": rows,
            }

        data = src.read_bytes(filename)
        if capture_integrity.sha256_bytes(data) != expected_hash:
            raise ValueError("source bytes changed since ingestion; refusing rebuild")

        con.execute("SAVEPOINT capture_rebuild")
        try:
            deleted = _delete_exact_source_rows(con, capture_id, filename)
            if fmt == "packetdb":
                result = raw_packet_ingest.ingest_packetdb(con, capture_id, src, filename)
            elif fmt == "packeteer":
                result = raw_packet_ingest.ingest_packeteer(con, capture_id, src, filename)
            elif fmt in {"pcap", "pcapng"}:
                result = pcap_ingest.ingest_pcap(con, capture_id, src, filename)
            elif fmt == "eventview":
                result = ingest_eventview(con, capture_id, src, filename)
            elif fmt == "idview_simple":
                result = ingest_idview_simple(con, capture_id, src, filename)
            elif fmt == "eventview_session_simple":
                result = ingest_eventview_session_simple(con, capture_id, src, filename)
            elif fmt == "eventview_session_raw":
                result = ingest_eventview_session_raw(con, capture_id, src, filename)
            elif fmt == "kitrack":
                result = ingest_kitrack(con, capture_id, src, filename)
            elif fmt == "hptrack":
                result = ingest_hptrack(con, capture_id, src, filename)
            elif fmt == "actionview_simple":
                result = ingest_actionview_simple(con, capture_id, src, filename)
            elif fmt == "caplog":
                result = ingest_caplog(con, capture_id, src, filename)
            elif fmt == "windower_logger":
                result = ingest_windower_logger(con, capture_id, src, filename)
            elif fmt == "npclogger_db":
                result = ingest_npc_db(con, capture_id, src, filename)
            elif fmt == "actionview_db":
                result = ingest_actions_db(con, capture_id, src, filename)
            elif fmt == "levelrange_db":
                result = ingest_level_range_db(con, capture_id, src, filename)
            elif fmt == "npclogger_lua":
                leg = 2 if "/database/" in filename.lower() else 1
                result = ingest_npclogger_lua(con, capture_id, src, filename, leg)
            elif fmt == "pathlog_csv":
                result = ingest_pathlog(con, capture_id, src, filename)
            elif fmt == "pc_pathlog_csv":
                result = ingest_pc_pathlog(con, capture_id, src, filename)
            elif fmt == "widescan":
                result = ingest_widescan(con, capture_id, src, filename)
            elif fmt == "attackdelay":
                result = ingest_attackdelay(con, capture_id, src, filename)
            elif fmt in AUX_STRUCTURED_FORMATS:
                result = ingest_aux_structured(con, capture_id, src, filename, fmt)
            else:
                raise ValueError(f"unsupported rebuild parser: {fmt}")
            rows = sum(result) if isinstance(result, tuple) else int(result)
            con.execute("RELEASE SAVEPOINT capture_rebuild")
        except Exception:
            con.execute("ROLLBACK TO SAVEPOINT capture_rebuild")
            con.execute("RELEASE SAVEPOINT capture_rebuild")
            raise

        capture_integrity.record_source_file(
            con, capture_id, filename, data,
            format_detected=fmt, parser_name=fmt, row_count=rows, error=None,
        )
        con.execute(
            """INSERT OR REPLACE INTO capture_source_files
               (capture_id,filename,format_detected,ingested_at,row_count,error)
               VALUES (?,?,?,datetime('now'),?,NULL)""",
            (capture_id, filename, fmt, rows),
        )
        recompute_zones(con, capture_id)
        con.commit()
        return {
            "capture_id": capture_id, "filename": filename, "format": fmt,
            "scope": "single_source", "deleted_rows": deleted, "rows": rows,
        }
    finally:
        src.close()


# Every real table keyed by capture_id -- kept as one list so delete_capture() can never miss one
# as new tables get added (a table added to init_db() but forgotten here would leave orphaned rows
# behind on every future delete, silently). Deliberately NOT derived by introspecting sqlite_master
# for tables with a capture_id column: several real tables (capture_source_files, capture_tags)
# have no data-quality reason to auto-discover, and an explicit list is easier to audit against
# init_db() by eye than trusting a DB introspection query to get it right.
CAPTURE_CHILD_TABLES = [
    "capture_network_flows", "capture_network_ranges", "capture_network_messages",
    "capture_npc_entries", "capture_npc_history", "capture_npc_path", "capture_actions",
    "capture_hp_events", "capture_events", "capture_ki_events", "capture_eventview",
    "capture_level_range", "capture_attack_delay", "capture_pc_path", "capture_structured_records", "capture_source_files",
    "capture_source_manifest", "capture_source_artifacts", "capture_content_manifest",
    "capture_ingest_lineage",
    "capture_raw_packets", "capture_video_observations", "capture_tags", "capture_caplog_chat",
    "capture_chat_observations",
    "capture_alignment_anchors", "capture_key_evidence",
]


def delete_capture(con, capture_id: int) -> dict:
    """Permanently removes one capture and every real row it owns across every child table --
    there is no soft-delete/undo, so the GUI route gates this behind an explicit confirm page
    rather than a single click. Returns {table: rows_deleted} for whatever confirmation message
    the caller wants to show."""
    return capture_integrity.delete_capture_rows(con, capture_id, CAPTURE_CHILD_TABLES)


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


def _backfill_npclogger_lua_fields(con, capture_id: int, src: Source, relname: str) -> int:
    """Backfill optional per-entity fields from one original legacy Lua snapshot file only."""
    zone_db = Path(relname).stem
    updated_entities = set()
    for raw_line in src.read_text(relname).splitlines():
        match = NPCLOGGER_LUA_LINE_RE.match(raw_line)
        if not match:
            continue
        entity_id = int(match.group(1))
        fields = {}
        for fm in NPCLOGGER_LUA_FIELD_RE.finditer(match.group(2)):
            key, str_val, num_val = fm.group(1), fm.group(2), fm.group(3)
            fields[key.lower()] = str_val if str_val is not None else float(num_val)
        optional = _npclogger_lua_optional_fields(fields)
        if not any(value is not None for value in optional):
            continue
        cur = con.execute(
            """UPDATE capture_npc_entries SET
                 legacy_look=COALESCE(?, legacy_look),
                 door_id=COALESCE(?, door_id), act_index=COALESCE(?, act_index),
                 flags0=COALESCE(?, flags0), flags1=COALESCE(?, flags1),
                 flags2=COALESCE(?, flags2), flags3=COALESCE(?, flags3),
                 legacy_flag=COALESCE(?, legacy_flag), sub_kind=COALESCE(?, sub_kind)
               WHERE capture_id=? AND zone_db=? AND entity_id=?""",
            (*optional, capture_id, zone_db, entity_id),
        )
        if cur.rowcount:
            updated_entities.add((zone_db, entity_id))
    return len(updated_entities)


def backfill_npc_fields(con):
    """Populates capture_npc_entries.legacy_look plus the door_id/act_index/flags0-3/legacy_flag/
    sub_kind columns for every already-ingested capture whose real source zip/folder is still on
    disk, without a full re-ingest -- same pattern used for KITrack/EventView/LevelRangeTrack/
    AttackDelay when those were added after captures already existed. Supports both the newer
    NPCLogger.db source and the older tables/database Lua-table snapshots; only fields genuinely
    present in the original source are applied. Captures whose source moved/deleted are reported
    and skipped rather than guessed."""
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
                lua_files = (
                    sfind(r'[Nn]pclogger/(?:[^/]+/)?tables/[^/]+\.lua$')
                    + sfind(r'[Nn]pclogger/(?:[^/]+/)?database/[^/]+\.lua$')
                )
                if not lua_files:
                    continue
                n_updated = 0
                for relname in lua_files:
                    n_updated += _backfill_npclogger_lua_fields(
                        con, capture_id, src, relname
                    )
                if n_updated:
                    print(f"  capture #{capture_id}: {n_updated} legacy-Lua entities backfilled")
                n_captures += 1
                n_updated_total += n_updated
                continue

            # Existing NPCLogger.db backfill logic remains unchanged.
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
    print(
        f"Done -- {n_updated_total} entities backfilled across {n_captures} capture(s) "
        "with original NPCLogger DB/Lua sources."
    )

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p1 = sub.add_parser("ingest", help="ingest one capture folder or .zip")
    p1.add_argument("path")
    p1.add_argument("--force", action="store_true", help="ingest even if identical content was already ingested")
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
                                          "legacy_flag/sub_kind from original NPCLogger DB or "
                                          "legacy tables/database Lua sources, without a full "
                                          "re-ingest")

    p6 = sub.add_parser("apply-manifest", help="link ingested captures to their Discord #campaign posts "
                                                "(uploader, post date, video, type/tags) via campaign_manifest.json")
    p6.add_argument("--dry-run", action="store_true")

    p7 = sub.add_parser("fingerprint-backfill", help="fingerprint already-ingested captures so duplicate detection covers them")
    p7.add_argument("--dry-run", action="store_true")
    p7.add_argument("--queue-duplicates", action="store_true", help="raise a review-queue item for each duplicate-content capture")

    p8 = sub.add_parser("repoint-sources", help="re-point captures whose source file moved to the same-named file under a new root")
    p8.add_argument("root")
    p8.add_argument("--dry-run", action="store_true")

    args = ap.parse_args()
    con = sqlite3.connect(str(DB_PATH))
    init_db(con)

    if args.cmd == "repoint-sources":
        from workbench.captures import source_fingerprint
        res = source_fingerprint.repoint(con, args.root, dry_run=args.dry_run)
        print({k: (len(v) if isinstance(v, list) else v) for k, v in res.items()})
        for k in ("ambiguous", "mismatch"):
            for r in res[k]:
                print(" ", k, r)
        con.close()
        return

    if args.cmd == "fingerprint-backfill":
        from workbench.captures import source_fingerprint
        print(source_fingerprint.backfill(con, dry_run=args.dry_run, queue=args.queue_duplicates))
        con.close()
        return

    if args.cmd == "apply-manifest":
        from workbench.core.services import campaign_manifest
        campaign_manifest.apply(con, dry_run=args.dry_run)
        con.close()
        return
    if args.cmd == "ingest":
        ingest(con, args.path, content_type=args.content_type, force=args.force)
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

    if args.cmd in ("ingest", "ingest-all", "ingest-batch"):
        from workbench.core.services import campaign_manifest
        if campaign_manifest.MANIFEST_PATH.exists():
            campaign_manifest.apply(con)

    con.close()


if __name__ == "__main__":
    main()
