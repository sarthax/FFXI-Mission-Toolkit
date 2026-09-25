#!/usr/bin/env python3
"""
entity_profile.py -- Mission Toolkit GUI, entity correlation + provenance layer.

The single canonical "everything about entity X" builder, replacing the duplicated partial
versions that had drifted apart across Entity Lookup, Wiki Compiler, and Zero-Position/
Unregistered (each independently re-deriving its own slice of the same cross-reference). Every
page that needs entity facts should call build_profile() here rather than re-deriving them.

Also the provenance layer the original Mission Toolkit GUI proposal designed but never built:
every fact this module records goes into a real field_sources table (entity_type, entity_id,
field_name, source, value, confidence) -- one row per (entity, field, SOURCE), not one row per
entity. When two sources agree on a field, that's two rows with the same value, which IS the
confidence signal (matching this project's own long-standing rule: never trust one source alone,
two independent sources agreeing is real evidence). When they disagree, both rows exist side by
side instead of one silently overwriting the other -- this matters now specifically because
entity_profile.py is the first place facts get merged from more than one kind of source at once
(client dat, Topaz SQL/Lua, wiki text, eventually captures), and once mission auto-drafting
becomes real (Phase 5, deferred but not deleted), a field with conflicting or wiki-only-tier
sources has to be visibly flagged, not silently trusted.

Usage:
    py -3 entity_profile.py 17093430
    py -3 entity_profile.py "Vending Box"
"""
import argparse
import io
import re
import sqlite3
import sys
from pathlib import Path

import lookup_entity
import mob_look_decode
import settings
from workbench.core.services.entity_profile_graph import import_entity_profile_provenance

TOOLS_ROOT = Path(__file__).parent
TOPAZ_ROOT = settings.get_topaz_root()
DB_PATH = TOOLS_ROOT / "ffxi_zone_database.db"

# Confidence tiers, reused directly from the original Mission Toolkit GUI proposal's provenance
# section -- not re-derived here, the reasoning already exists.
CONFIDENCE = {
    "client_dat": "highest -- ground truth for this client build",
    "topaz_sql": "authoritative for 'does Topaz implement this', not 'is this the real value'",
    "topaz_lua": "authoritative for 'does Topaz implement this', not 'is this the real value'",
    "wiki": "reference only -- never load-bearing alone",
    "packet_decode": "high, but scoped to that capture's calling convention",
    "derived": "computed from another already-recorded field, not an independent source",
    "capture": "observed behavior from a real captured session -- not a guarantee of Topaz's own scripted behavior",
}


def init_db(con: sqlite3.Connection):
    con.executescript("""
        CREATE TABLE IF NOT EXISTS field_sources (
            entity_type TEXT,
            entity_id INTEGER,
            field_name TEXT,
            source TEXT,
            value TEXT,
            confidence TEXT,
            recorded_at TEXT DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (entity_type, entity_id, field_name, source)
        );
        CREATE INDEX IF NOT EXISTS idx_field_sources_entity ON field_sources(entity_type, entity_id);
    """)
    con.commit()


def record_field(con: sqlite3.Connection, entity_type: str, entity_id: int, field_name: str,
                  source: str, value) -> None:
    """Upserts one (entity, field, source) row. Called as a side effect of every resolver below
    -- the table builds up from normal usage, not a separate ingestion pass."""
    if value is None:
        return
    con.execute(
        """INSERT OR REPLACE INTO field_sources
           (entity_type, entity_id, field_name, source, value, confidence)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (entity_type, entity_id, field_name, source, str(value), CONFIDENCE.get(source, "unspecified")),
    )


def get_field_history(con: sqlite3.Connection, entity_type: str, entity_id: int) -> dict[str, list[dict]]:
    """Every recorded (field -> [{source, value, confidence}, ...]) for this entity -- the actual
    provenance view: which fields have multiple sources (agreement or conflict), which have only
    one, sourced from where."""
    rows = con.execute(
        "SELECT field_name, source, value, confidence FROM field_sources "
        "WHERE entity_type = ? AND entity_id = ? ORDER BY field_name, source",
        (entity_type, entity_id),
    ).fetchall()
    history: dict[str, list[dict]] = {}
    for field_name, source, value, confidence in rows:
        history.setdefault(field_name, []).append(
            {"source": source, "value": value, "confidence": confidence}
        )
    return history


def get_wiring_status(con: sqlite3.Connection, npcid: int) -> str:
    """Real registration status from build_sql_index.py's own structured tables. Canonical --
    wiki_compile.py used to keep its own separate copy of this exact check, which is the kind of
    duplication that let it drift from Entity Lookup's own gap_warning logic (Entity Lookup's
    version greps ALL of sql/*.sql for a broader signal; this one checks just the two structured
    tables that actually define 'wired'). Both now call this single function instead of two
    independently-maintained near-duplicates that could silently disagree."""
    in_instance = con.execute(
        "SELECT 1 FROM sql_instance_entities WHERE id = ? LIMIT 1", (npcid,)
    ).fetchone()
    in_spawn = con.execute(
        "SELECT 1 FROM sql_mob_spawn_points WHERE mobid = ? LIMIT 1", (npcid,)
    ).fetchone()
    if in_instance:
        return "wired (instance_entities)"
    if in_spawn:
        return "registered (mob_spawn_points) but NOT in any instance_entities"
    return "not registered anywhere"


def decode_entity_id(npcid: int) -> dict:
    """Real FFXI entity id structure: 0x01[zone:12bits][index:12bits] -- confirmed this session
    (the Caedarva Mire / Leujaoam Sanctum capture cross-check) by checking these bits agree with
    a real SQL zoneid lookup, not assumed from documentation alone."""
    zone_bits = (npcid >> 12) & 0xFFF
    local_bits = npcid & 0xFFF
    return {"hex": f"0x{npcid:08X}", "zone_bits": zone_bits, "local_bits": local_bits}


def get_wiki_references(con: sqlite3.Connection, real_name: str) -> list[dict]:
    """Reverse of wiki_compile.py's own direction: given a real entity name, which wiki pages
    are about it or reference it. Reads two indexes built once by build_wiki_index.py rather than
    re-scanning the whole dump live:
      - wiki_pages: the canonical article, if any, whose OWN title matches the entity name.
      - wiki_entity_refs: other pages that [[link to]] the entity, i.e. mention it in passing.
    These are kept separate (not merged into one lookup) because a canonical article rarely
    wikilinks to its own title -- a name-only match against wiki_entity_refs alone can surface
    nothing but incidental listing pages (e.g. a hunts-by-nation index) while missing the real
    article entirely, which is exactly what happened before this split existed (real example:
    "Jaggedy-Eared Jack" -- found live 2026-09-03)."""
    norm = re.sub(r"[^a-z0-9]", "", real_name.lower())
    out = []
    try:
        primary = con.execute(
            "SELECT title, url FROM wiki_pages WHERE norm_title = ?", (norm,),
        ).fetchone()
    except sqlite3.OperationalError:
        primary = None  # wiki_pages not built yet (stale index from before this split existed)
    if primary:
        out.append({"title": primary[0], "url": primary[1], "kind": "primary"})
    try:
        rows = con.execute(
            "SELECT DISTINCT page_title, page_url FROM wiki_entity_refs WHERE norm_name = ? LIMIT 20",
            (norm,),
        ).fetchall()
    except sqlite3.OperationalError:
        rows = []  # wiki_entity_refs not built yet -- not an error, just not indexed
    for t, u in rows:
        if primary and t == primary[0]:
            continue  # already listed as the primary page above
        out.append({"title": t, "url": u, "kind": "mention"})
    return out


def get_mission_rollup(con: sqlite3.Connection, mission_id: int, mission_name: str) -> dict:
    """Per-mission coverage summary for the Assault Missions page -- how much of what this
    mission actually spawns has real capture/drop/ability data behind it, not just the client
    text. Real, confirmed mapping: sql_instance_entities.instanceid == assault_missions.mission_id
    (see build_profile's own comment, verified 2026-09 via Leujaoam Worm -> instanceid 1 ->
    "Leujaoam Cleansing"). A mission with 0 entities here either has no Assault mobs wired in
    instance_entities.sql yet, or isn't actually an Assault-content row in this broader table.

    2026-09-07: real bug fixed -- 75 of 127 assault_missions rows are real, unresolved client
    placeholder strings ("ASミッション53" etc, a literal untranslated template with no real
    mission text ever substituted in, confirmed live: their own Mission Orders/Area/Objective
    fields are blank). Their mission_id still coincidentally collides with OTHER real instance
    content in the broader instance_entities/instance_list numbering space -- confirmed by hand:
    id 53 -> "the_black_coffin" (a BCNM), id 65 -> "arrapago_remnants" (Salvage), none of them
    Assault content at all. Before this fix, those rows showed real-looking but entirely wrong
    entity/drop counts borrowed from whatever unrelated instance happened to reuse that same
    numeric id. A placeholder mission name can never have real Assault entities to roll up, so
    skip the lookup entirely rather than let it return a coincidentally-real-looking wrong
    answer."""
    if mission_name.startswith("ASミッション"):
        return {"n_entities": 0, "is_placeholder": True}

    entity_ids = [r[0] for r in con.execute(
        "SELECT id FROM sql_instance_entities WHERE instanceid = ?", (mission_id,)
    ).fetchall()]
    if not entity_ids:
        return {"n_entities": 0}

    placeholders = ",".join("?" * len(entity_ids))

    def _safe_count(sql: str) -> int:
        # Defense in depth: gui_server.py now ensures the capture_* tables exist at startup (see
        # its own _ensure_capture_schema_exists()), so this shouldn't fire in practice -- but a
        # missing capture table degrading to "0" instead of a hard 500 is the correct behavior
        # for a page whose whole point is "here's what real capture evidence exists, if any."
        try:
            return con.execute(sql, entity_ids).fetchone()[0]
        except sqlite3.OperationalError:
            return 0

    n_captured = _safe_count(
        f"SELECT COUNT(DISTINCT entity_id) FROM capture_npc_entries WHERE entity_id IN ({placeholders})"
    )
    n_with_abilities = _safe_count(
        f"SELECT COUNT(DISTINCT actor) FROM capture_actions WHERE actor IN ({placeholders})"
    )
    n_with_drops = con.execute(
        f"""SELECT COUNT(DISTINCT msp.mobid) FROM sql_mob_spawn_points msp
            JOIN sql_mob_groups g ON g.groupid = msp.groupid
            WHERE msp.mobid IN ({placeholders}) AND g.dropid > 0
              AND EXISTS (SELECT 1 FROM sql_mob_droplist d WHERE d.dropid = g.dropid)""",
        entity_ids,
    ).fetchone()[0]
    captures_for_mission = con.execute(
        "SELECT capture_id, capture_label FROM captures WHERE mission_name = ? ORDER BY capture_id",
        (mission_name,),
    ).fetchall()

    return {
        "n_entities": len(entity_ids),
        "n_captured": n_captured,
        "n_with_abilities": n_with_abilities,
        "n_with_drops": n_with_drops,
        "captures": [{"capture_id": cid, "label": label} for cid, label in captures_for_mission],
    }


def build_profile(con: sqlite3.Connection, npcid: int) -> dict:
    """The one canonical 'everything about this entity' assembly -- reuses every existing
    resolver rather than re-deriving them (get_npc_list_row_detail, get_mob_chain_detail,
    grep_sql, grep_lua all already exist in lookup_entity.py), and records every fact it touches
    into field_sources as it goes."""
    init_db(con)
    # Cleared and rebuilt fresh each call, not incrementally accumulated -- build_profile() is
    # called live per request, so "current known state" should mean exactly that; an old
    # field_name scheme (or a fact that's no longer true) should never linger as a stale row.
    con.execute("DELETE FROM field_sources WHERE entity_type = 'npc' AND entity_id = ?", (npcid,))
    profile: dict = {"npcid": npcid, "id_decode": decode_entity_id(npcid)}

    name_row = con.execute("SELECT name, zoneid FROM npc_names WHERE npcid = ?", (npcid,)).fetchone()
    if not name_row:
        profile["error"] = "not in npc_names index"
        return profile
    real_name, zoneid = name_row
    profile["name"] = real_name
    profile["zoneid"] = zoneid
    record_field(con, "npc", npcid, "name", "client_dat", real_name)

    zname_row = con.execute("SELECT name FROM zones WHERE zoneid = ?", (zoneid,)).fetchone()
    zname = zname_row[0] if zname_row else None
    profile["zone_name"] = zname
    zone_folder = lookup_entity.zone_folder_name_guess(zname) if zname else None
    profile["zone_folder"] = zone_folder

    row_detail = lookup_entity.get_npc_list_row_detail(npcid)
    profile["npc_list"] = row_detail
    if row_detail:
        record_field(con, "npc", npcid, "position", "topaz_sql", row_detail["pos"])
        if row_detail["content_tag"]:
            record_field(con, "npc", npcid, "content_tag", "topaz_sql", row_detail["content_tag"])

    mob_chain = lookup_entity.get_mob_chain_detail(con, npcid, zoneid)
    profile["mob_chain"] = mob_chain
    if mob_chain and "pool_name" in mob_chain:
        record_field(con, "npc", npcid, "mob_pool", "topaz_sql", mob_chain["pool_name"])
        if mob_chain.get("min_level") is not None:
            record_field(con, "npc", npcid, "observed_level_range", "topaz_sql",
                         f"{mob_chain['min_level']}-{mob_chain['max_level']}")
        # Model DAT: mob_pools.modelid, decoded via mob_look_decode.py's real ground-truth
        # struct parser -- wired in here (it existed but was never connected to a profile view).
        model_row = con.execute(
            "SELECT modelid, cmbDelay FROM sql_mob_pools WHERE poolid = ?", (mob_chain["poolid"],)
        ).fetchone()
        if model_row and model_row[1] is not None:
            mob_chain["cmb_delay"] = model_row[1]
            record_field(con, "npc", npcid, "observed_attack_delay", "topaz_sql", str(model_row[1]))
        if model_row and model_row[0]:
            hexstr = model_row[0][2:] if model_row[0].startswith("0x") else model_row[0]
            try:
                model_data = mob_look_decode.decode_look_data(bytes.fromhex(hexstr))
                profile["model"] = model_data
                if model_data.get("kind") == "flat":
                    record_field(con, "npc", npcid, "model_file_id", "topaz_sql", model_data["file_id"])
                    # Real bug found 2026-09-04: the decode math is correct, but a whole mob
                    # family (Lamia_NoXX) turned out to share only ~8 distinct modelid values
                    # across 14 real, distinct mobs -- the classic "generic placeholder, copy-
                    # pasted and never individually fixed" pattern already seen elsewhere in this
                    # project's own SQL history (0x0000320000... invisible-placeholder look), not
                    # a decode error. Surface this per-entity instead of trusting every flat
                    # modelid equally: count how many OTHER real pool rows share this exact same
                    # raw blob -- a value reused by several unrelated mobs is a real placeholder
                    # signal, a value unique to this pool is real signal the other way.
                    dupe_row = con.execute(
                        "SELECT COUNT(DISTINCT name) FROM sql_mob_pools WHERE modelid = ? AND poolid != ?",
                        (model_row[0], mob_chain["poolid"]),
                    ).fetchone()
                    if dupe_row and dupe_row[0]:
                        model_data["shared_with_n_other_pools"] = dupe_row[0]
            except ValueError:
                profile["model"] = {"error": "could not parse modelid hex"}

    script_name_guess, _ = lookup_entity.find_owning_zone_and_name(con, npcid)
    profile["script_name_guess"] = script_name_guess
    sql_hits = lookup_entity.grep_sql(npcid)
    profile["sql_hits"] = sql_hits
    lua_hits = lookup_entity.grep_lua(npcid, script_name_guess, zone_folder)
    profile["lua_hits"] = lua_hits
    # field_name must be unique per (entity, field_name, source) -- record_field's own primary
    # key -- or looping the same field_name+source pair over multiple files silently drops all
    # but the last one (confirmed live: Vending Box has 2 real SQL files and 2 real Lua files,
    # but only the last of each survived before this fix). Fold the filename into field_name so
    # each real reference gets its own row.
    for fname in sql_hits:
        record_field(con, "npc", npcid, f"referenced_in_sql:{fname}", "topaz_sql", fname)
    for fname in lua_hits:
        record_field(con, "npc", npcid, f"referenced_in_lua:{fname}", "topaz_lua", fname)

    in_instance = "instance_entities.sql" in sql_hits
    in_spawn = "npc_list.sql" in sql_hits or "mob_spawn_points.sql" in sql_hits
    profile["gap_warning"] = in_spawn and not in_instance

    # Assault mission link: instance_entities.instanceid -> assault_missions.mission_id --
    # confirmed real this session (Leujaoam Worm 17059841 -> instanceid 1 -> "Leujaoam Cleansing",
    # mission_id 1, exact match), not assumed.
    mission_row = con.execute(
        """SELECT am.mission_id, am.name FROM sql_instance_entities ie
           JOIN assault_missions am ON am.mission_id = ie.instanceid
           WHERE ie.id = ? LIMIT 1""",
        (npcid,),
    ).fetchone()
    if mission_row:
        profile["assault_mission"] = {"id": mission_row[0], "name": mission_row[1]}
        record_field(con, "npc", npcid, "assault_mission", "topaz_sql", mission_row[1])

    # Drop table: mob_groups.dropid is the real FK into mob_droplist (NOT mob_pools.poolid --
    # confirmed directly against Topaz's own C++, see build_sql_index.py's load_mob_droplist
    # docstring). dropid=0 is a real, valid "no drop table configured" state, not a lookup miss.
    if mob_chain and mob_chain.get("dropid"):
        drop_rows = con.execute(
            """SELECT d.groupId, d.groupRate, d.itemId, d.itemRate, i.name
               FROM sql_mob_droplist d LEFT JOIN items_ours i ON i.itemid = d.itemId
               WHERE d.dropid = ? ORDER BY d.groupId, d.itemRate DESC""",
            (mob_chain["dropid"],),
        ).fetchall()
        if drop_rows:
            profile["drops"] = [
                {"group_id": g, "group_rate": gr, "item_id": iid, "item_rate": ir,
                 "item_name": name, "effective_pct": round(gr / 1000 * ir / 1000 * 100, 2)}
                for g, gr, iid, ir, name in drop_rows
            ]
            for d in profile["drops"]:
                label = d["item_name"] or f"item#{d['item_id']}"
                record_field(con, "npc", npcid, f"drops:{label}", "topaz_sql",
                             f"{d['effective_pct']}%")

    # Real capture data -- abilities/weaponskills this entity was actually observed using
    # (capture_actions.actor), and every capture bundle it appeared in (capture_npc_entries).
    # Confidence tier "capture" (see CONFIDENCE dict) -- observed behavior from a real session,
    # not a guarantee of Topaz's own scripted behavior for it.
    ability_rows = con.execute(
        """SELECT name, action_type, animation, category, message, COUNT(*) as n
           FROM capture_actions WHERE actor = ?
           GROUP BY name, action_type, animation, category, message ORDER BY n DESC""",
        (npcid,),
    ).fetchall()
    if ability_rows:
        profile["capture_abilities"] = [
            {"name": n, "action_type": at, "animation": anim, "category": cat,
             "message": msg, "count": cnt}
            for n, at, anim, cat, msg, cnt in ability_rows
        ]
        for a in profile["capture_abilities"]:
            record_field(con, "npc", npcid, f"observed_ability:{a['name']}", "capture",
                         f"used {a['count']}x, animation={a['animation']}")

    # Real observed CS-events/dialogue for this entity, from idview/simple capture logs (see
    # build_capture_index.ingest_idview_simple) -- distinct (event_hex, message_id) pairs actually
    # fired against a real client, not a guess at what CSID/message a menu uses.
    event_rows = con.execute(
        """SELECT event_hex, message_id, COUNT(*) as n FROM capture_events
           WHERE entity_id = ? AND (event_hex IS NOT NULL OR message_id IS NOT NULL)
           GROUP BY event_hex, message_id ORDER BY n DESC""",
        (npcid,),
    ).fetchall()
    if event_rows:
        profile["capture_events"] = [
            {"event_hex": eh, "message_id": mid, "count": cnt} for eh, mid, cnt in event_rows
        ]
        for e in profile["capture_events"]:
            label = e["event_hex"] or f"message:{e['message_id']}"
            record_field(con, "npc", npcid, f"observed_event:{label}", "capture",
                         f"seen {e['count']}x" + (f", message_id={e['message_id']}" if e["event_hex"] and e["message_id"] else ""))

    # Real, already-decoded packet dumps for this entity from EventView capture logs (see
    # build_capture_index.ingest_eventview) -- richer than capture_events/idview: real packet
    # class name, the real GP_SERV_COMMAND_* constant, and real message ids, with real timestamps.
    eventview_rows = con.execute(
        """SELECT packet_class, gp_command, mes_num, message_number, COUNT(*) as n
           FROM capture_eventview WHERE entity_id = ?
           GROUP BY packet_class, gp_command, mes_num, message_number ORDER BY n DESC""",
        (npcid,),
    ).fetchall()
    if eventview_rows:
        profile["capture_eventview"] = [
            {"packet_class": pc, "gp_command": gc, "mes_num": mn, "message_number": mnum, "count": cnt}
            for pc, gc, mn, mnum, cnt in eventview_rows
        ]
        for e in profile["capture_eventview"]:
            label = f"{e['packet_class']}:{e['gp_command']}"
            detail = f"seen {e['count']}x"
            if e["mes_num"]:
                detail += f", MesNum={e['mes_num']}"
            if e["message_number"]:
                detail += f", MessageNumber={e['message_number']}"
            record_field(con, "npc", npcid, f"eventview_packet:{label}", "capture", detail)

    # Real observed level range from LevelRangeTrack (see build_capture_index.ingest_level_range_db)
    # -- an independent live-client cross-check against sql_mob_groups.minLevel/maxLevel, not just
    # a restatement of what Topaz's own SQL says the range should be.
    lvl_rows = con.execute(
        "SELECT DISTINCT level_min, level_max FROM capture_level_range WHERE entity_id = ?",
        (npcid,),
    ).fetchall()
    if lvl_rows:
        profile["capture_level_range"] = [{"min": lo, "max": hi} for lo, hi in lvl_rows]
        for lr in profile["capture_level_range"]:
            record_field(con, "npc", npcid, "observed_level_range", "capture",
                         f"{lr['min']}-{lr['max']}")

    # Real observed attack timing from AttackDelay (see build_capture_index.ingest_attackdelay)
    # -- aggregated by mob NAME across a whole zone capture (this addon doesn't track individual
    # entity ids), matched here by the entity's own real display name. "Reverse calculation" is
    # the addon's own estimate of the real configured delay from observed hit intervals -- an
    # independent live-client cross-check against sql_mob_pools.cmbDelay, recorded to the SAME
    # field_sources field as the SQL value above so agreement/conflict is real, not asserted.
    ad_rows = con.execute(
        """SELECT capture_id, hit_count, delay_min, delay_max, delay_avg, delay_median,
                  reverse_calc_delay, reverse_calc_samples, multihit_raw, slots_raw
           FROM capture_attack_delay WHERE LOWER(mob_name) = LOWER(?) ORDER BY capture_id""",
        (real_name,),
    ).fetchall()
    if ad_rows:
        profile["capture_attack_delay"] = [
            {"capture_id": cid, "hits": hc, "min": dmin, "max": dmax, "avg": avg, "median": med,
             "reverse_calc": rc, "reverse_samples": rs, "multihit": mh, "slots": sl}
            for cid, hc, dmin, dmax, avg, med, rc, rs, mh, sl in ad_rows
        ]
        for a in profile["capture_attack_delay"]:
            if a["reverse_calc"] is not None:
                record_field(con, "npc", npcid, "observed_attack_delay", "capture",
                             f"{a['reverse_calc']} (reverse-calc from {a['reverse_samples']} samples, capture #{a['capture_id']})")

    capture_rows = con.execute(
        """SELECT c.capture_id, c.capture_label, c.mission_name, e.door_id, e.act_index
           FROM capture_npc_entries e JOIN captures c ON c.capture_id = e.capture_id
           WHERE e.entity_id = ? ORDER BY c.capture_id""",
        (npcid,),
    ).fetchall()
    if capture_rows:
        profile["capture_appearances"] = [
            {"capture_id": cid, "label": label, "mission_name": mission,
             "door_id": door_id, "act_index": act_index}
            for cid, label, mission, door_id, act_index in capture_rows
        ]
        record_field(con, "npc", npcid, "capture_appearances", "capture",
                     f"{len(capture_rows)} capture(s)")
        # door_id/act_index -- real NPCLogger.db columns (DoorId, ActIndex) added 2026-09-04 after
        # an audit found them silently dropped despite being genuinely populated. door_id ties an
        # entity to a real door/trigger prop id; act_index is the mission's own act/objective
        # index at the moment this entity was observed. Recorded per real distinct value seen (an
        # entity can show a different act_index across different captures/moments, which is real
        # signal -- a mission progressing -- not noise to collapse into one).
        seen_doors = {r["door_id"] for r in profile["capture_appearances"] if r["door_id"]}
        for door_id in sorted(seen_doors):
            record_field(con, "npc", npcid, "capture_door_id", "capture", str(door_id))
        seen_acts = {r["act_index"] for r in profile["capture_appearances"] if r["act_index"]}
        for act_index in sorted(seen_acts):
            record_field(con, "npc", npcid, "capture_act_index", "capture", str(act_index))

    profile["wiki_references"] = get_wiki_references(con, real_name)
    for ref in profile["wiki_references"]:
        record_field(con, "npc", npcid, f"wiki_reference:{ref['title']}", "wiki", ref["title"])

    con.commit()
    profile["field_sources"] = get_field_history(con, "npc", npcid)
    return profile


def print_profile(profile: dict):
    if "error" in profile:
        print(profile["error"])
        return
    d = profile["id_decode"]
    print(f"=== {profile['npcid']} ({d['hex']}) ===")
    print(f"Real name: {profile['name']!r}")
    print(f"Zone: {profile['zone_name']} (zoneid {profile['zoneid']}, "
          f"id-decoded zone_bits={d['zone_bits']}, local_bits={d['local_bits']})")
    if profile["zoneid"] is not None and d["zone_bits"] != profile["zoneid"]:
        print(f"  [!] id's own zone bits ({d['zone_bits']}) do NOT match its indexed zoneid "
              f"({profile['zoneid']}) -- worth a closer look, same pattern as the real "
              f"Caedarva Mire finding earlier this session.")

    if profile.get("npc_list"):
        rd = profile["npc_list"]
        print(f"Position: {rd['pos']}, rot={rd['pos_rot']}")
        if rd["content_tag"]:
            print(f"content_tag: {rd['content_tag']} (server-side flag, not proof of ownership)")

    if profile.get("model"):
        m = profile["model"]
        if m.get("kind") == "flat":
            print(f"Model: {m['model_type']}, file_id={m['file_id']} "
                  f"(py -3 model_schedule_dump.py --file-id {m['file_id']})")
        elif m.get("kind") == "gear":
            print(f"Model: {m['model_type']}, race={m['race_name']} -- composite, no single DAT "
                  f"({m['note']})")
        elif m.get("kind") == "prop":
            print(f"Model: {m['model_type']} (not a renderable model -- door/elevator/ship prop)")

    if profile.get("mob_chain") and "pool_name" in profile["mob_chain"]:
        mc = profile["mob_chain"]
        print(f"Mob group {mc['groupid']}: {mc['group_name']} -- level {mc['min_level']}-"
              f"{mc['max_level']}, pool {mc['pool_name']} (family {mc['familyid']})")

    if profile.get("assault_mission"):
        am = profile["assault_mission"]
        print(f"Assault mission: #{am['id']} {am['name']!r}")

    if profile["gap_warning"]:
        print("[!] Registered in npc_list/mob_spawn_points but NOT in instance_entities.sql")

    print(f"\nSQL references: {len(profile['sql_hits'])} file(s)")
    for fname in profile["sql_hits"]:
        print(f"  {fname}")
    print(f"Lua references: {len(profile['lua_hits'])} file(s)")
    for fname in profile["lua_hits"]:
        print(f"  {fname}")

    if profile["wiki_references"]:
        print(f"\nWiki references: {len(profile['wiki_references'])} page(s)")
        for ref in profile["wiki_references"]:
            print(f"  {ref['title']}  ({ref['url']})")
    else:
        print("\nWiki references: none found (or wiki_entity_refs not built yet -- "
              "run py -3 build_wiki_index.py)")

    print("\nField provenance:")
    for field_name, sources in profile["field_sources"].items():
        tags = ", ".join(f"{s['source']}={s['value'][:60]!r}" for s in sources)
        conflict = "  [CONFLICT]" if len({s["value"] for s in sources}) > 1 else ""
        print(f"  {field_name}: {tags}{conflict}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("query", help="npc/mob id, or a name substring")
    ap.add_argument("--graph-db", type=Path, help="Optionally import field provenance into the canonical Workbench graph.")
    args = ap.parse_args()

    # timeout+WAL: same reasoning as gui_server.py's get_con() -- lets this CLI usage coexist
    # with the GUI server if both touch the db around the same time, instead of racing to lock it.
    con = sqlite3.connect(DB_PATH, timeout=30)
    con.execute("PRAGMA journal_mode=WAL")
    if args.query.isdigit():
        npcid = int(args.query)
    else:
        matches = lookup_entity.resolve_query_to_ids(con, args.query)
        if not matches:
            print("No match.")
            return
        if len(matches) > 1:
            print(f"{len(matches)} matches -- pass a specific id:")
            for m in matches:
                print(f"  {m[0]}  {m[1]!r}")
            return
        npcid = matches[0][0]

    profile = build_profile(con, npcid)
    print_profile(profile)
    con.close()
    if args.graph_db:
        result=import_entity_profile_provenance(DB_PATH,args.graph_db,npcid)
        print(f"Graph import: {result['status']} ({result.get('findings',0)} findings, {result.get('conflicts',0)} conflicts)")


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    main()
