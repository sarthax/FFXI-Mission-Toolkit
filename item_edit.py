"""Item editing layer: every write to the live item_* tables goes through here so it is
  1. backed up first (data/item_backups/*.json: full previous rows, restorable),
  2. journalled as annotated SQL (data/item_edit_log.sql: `-- comment` + the exact statement).
Mirrors zone_edit.py's conventions exactly, but for item_basic/item_equipment/item_weapon/
item_usable/item_puppet/item_furnishing instead of mob_spawn_points/npc_list.

Client DAT edits (the level requirement the real client itself enforces, not just the server's
permission check) are a SEPARATE step handled by item_dat_tools.py -- update_item()/create_item()
below call into it so both sides move together, per the project's "level requirement is dual
authority" research finding.
"""
import json
import time
from decimal import Decimal
from pathlib import Path

import item_dat_tools as dat
import zone_plot

DATA = Path(__file__).parent / "data"
BACKUPS = DATA / "item_backups"
LOG = DATA / "item_edit_log.sql"

TABLES = {  # table -> primary key columns (all six real item_* tables, per C:\topaz\sql\*.sql)
    "item_basic":      ["itemid"],
    "item_equipment":  ["itemId"],
    "item_weapon":     ["itemId"],
    "item_usable":     ["itemid"],
    "item_puppet":     ["itemid"],
    "item_furnishing": ["itemid"],
}
# Which of the six tables a given item_basic.flags/type combination actually has a row in --
# item_basic always exists; the rest are conditional on item_type (mirrors item_dat_tools.TYPE_NAME).
TYPE_TABLES = {
    0: [],                       # general -- item_basic only
    1: ["item_usable"],          # consumable
    3: ["item_equipment"],       # armor
    4: ["item_equipment", "item_weapon"],  # weapon
    5: ["item_puppet"],
    6: ["item_furnishing"],
}

# Bitmasked columns, so the UI can render checkboxes instead of asking the user to know the
# schema. Only columns with a CONFIRMED bit mapping (verified against C:\topaz source or
# item_dat_tools' own vendored tables) are listed here -- per project rule, never invent a
# schema. {table: {column: [(bit_value, label), ...]}}
BITMASK_SCHEMAS = {
    "item_basic": {
        "flags": sorted(dat.ITEM_FLAGS.items()),
    },
    "item_equipment": {
        "jobs": [(1 << i, job) for i, job in enumerate(dat.JOBS)],
        "slot": [(1 << i, name) for i, name in enumerate(dat.SLOTS)],
    },
    "item_usable": {
        "validTargets": sorted(dat.VALID_TARGETS.items()),
    },
}

# Single-value enum columns -- rendered as a dropdown, NOT checkboxes, since only one value can
# ever be true at once (unlike the flag bitmasks above where several bits combine).
# item_basic.aH: which Auction House submenu the item appears under (0 = not sellable at AH).
# item_furnishing.moghancement: confirmed via charentity.cpp's UpdateMoghancement()
# (`switch (m_moghancementID)`, single-value equality) to be a real enum, NOT a bitmask, despite
# its value range superficially looking bitmask-shaped -- see item_dat_tools.MOGHANCEMENT comment.
ENUM_SCHEMAS = {
    "item_basic": {
        "aH": sorted(dat.AH_CATEGORY.items()),
    },
    "item_furnishing": {
        "moghancement": sorted(dat.MOGHANCEMENT.items()),
    },
    "item_usable": {
        "animation": sorted(dat.ITEM_ANIMATION.items()),
    },
}

# item_equipment.races (a client-DAT-only field item_dat_tools tracks -- there is no
# item_equipment.races column server-side; C:\topaz\sql\item_equipment.sql has no such
# column and no RACE_* equip-gating code exists in C:\topaz\src), item_usable.activation
# (a plain millisecond duration, not a bitmask -- itemutils.cpp:363/item_usable.h), and
# item_furnishing.element/aura (schema columns exist but no bit-decode code was found anywhere
# in C:\topaz\src to confirm a mapping) are deliberately NOT listed above -- their bit/value
# meaning is unconfirmed, and this project's rule is to say "don't know" rather than invent a
# schema. Edit those as plain numbers until a real mapping surfaces.

# Packed-nibble columns -- NOT flag bitmasks: each is N sub-values of `bits` width packed at
# fixed shifts, so the UI renders a small number input (0..2^bits-1) per sub-value instead of a
# single raw int. {table: {column: {"bits": width, "fields": [(shift, label), ...]}}}
# item_puppet.element confirmed at C:\topaz\src\map\utils\puppetutils.cpp
# (`(getElementSlots() >> (i*4)) & 0xF`) -- 8 packed 4-bit (0-15) element-capacity values, one
# nibble per element, order confirmed via the contiguous EFFECT_FIRE_MANEUVER..EFFECT_DARK_MANEUVER
# run in status_effect.h (300-307). Applies identically to puppet heads, frames, and attachments
# (equip slot is the separate, non-bitmask `item_puppet.slot` column: 1=head, 2=frame,
# 3=attachment -- ITEM_PUPPET_EQUIPSLOT enum, item_puppet.h). NOTE: the actual per-attachment
# combat behavior/stat values (e.g. Turbo Charger's haste amounts) are NOT stored in any SQL/DAT
# field at all -- they're hardcoded in each attachment's own Lua file under
# C:\topaz\scripts\globals\abilities\pets\attachments\<item_name>.lua, dispatched by item name
# (luautils.cpp OnAttachmentEquip/OnManeuverGain/etc. index
# tpz.globals.abilities.pets.attachments[itemName]). That is Lua source code, not row data, so it
# is out of scope for this row-level editor -- editing an attachment's real numeric effect means
# editing its .lua file directly, not a future GUI field.
NIBBLE_SCHEMAS = {
    "item_puppet": {
        "element": {"bits": 4, "fields": [(i * 4, name) for i, name in enumerate(dat.ELEMENTS)]},
    },
}


def bitmask_schema():
    """{table: {column: {type, bits: [{bit,label}]} | {type, width, fields: [{shift,label}]}
    | {type, options: [{value,label}]}}}."""
    result = {}
    for table, cols in BITMASK_SCHEMAS.items():
        result.setdefault(table, {})
        for col, bits in cols.items():
            result[table][col] = {
                "type": "bits",
                "bits": [{"bit": bit, "label": label} for bit, label in bits],
            }
    for table, cols in NIBBLE_SCHEMAS.items():
        result.setdefault(table, {})
        for col, spec in cols.items():
            result[table][col] = {
                "type": "nibbles",
                "width": spec["bits"],
                "fields": [{"shift": shift, "label": label} for shift, label in spec["fields"]],
            }
    for table, cols in ENUM_SCHEMAS.items():
        result.setdefault(table, {})
        for col, options in cols.items():
            result[table][col] = {
                "type": "enum",
                "options": [{"value": value, "label": label} for value, label in options],
            }
    return result


# ---- value <-> json / sql -------------------------------------------------------------------
def _enc(v):
    if isinstance(v, (bytes, bytearray)):
        return {"__hex__": bytes(v).hex()}
    if isinstance(v, Decimal):
        return float(v)
    return v


def _dec(v):
    if isinstance(v, dict) and "__hex__" in v:
        return bytes.fromhex(v["__hex__"])
    return v


def lit(v):
    v = _dec(v)
    if v is None:
        return "NULL"
    if isinstance(v, (bytes, bytearray)):
        return "0x" + bytes(v).hex()
    if isinstance(v, (int, float)):
        return repr(v)
    return "'" + str(v).replace("\\", "\\\\").replace("'", "\\'") + "'"


def _cols(cu, table):
    cu.execute(f"describe {table}")
    return [r[0] for r in cu.fetchall()]


def _pk_for(table):
    """Primary key columns for a table -- covers the six real item_* tables (TABLES) plus the
    three one-to-many mod tables, whose composite keys aren't in TABLES since they're never the
    target of update_item()/create_item()."""
    if table == "item_mods":
        return ["itemId", "modId"]
    if table == "item_mods_pet":
        return ["itemId", "modId", "petType"]
    if table == "item_latents":
        return ["itemId", "modId", "value", "latentId", "latentParam"]
    return TABLES[table]


def _fetch(cu, table, keyvals):
    cols = _cols(cu, table)
    where = " and ".join(f"{k}=%s" for k in _pk_for(table))
    cu.execute(f"select * from {table} where {where}", tuple(keyvals))
    r = cu.fetchall()
    return dict(zip(cols, [_enc(x) for x in r[0]])) if r else None


def _journal(comment, lines):
    LOG.parent.mkdir(exist_ok=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(f"\n-- [{time.strftime('%Y-%m-%d %H:%M:%S')}] {comment or '(no comment)'}\n")
        for l in lines:
            f.write(l + "\n")


def _save_backup(label, item_id, ops):
    BACKUPS.mkdir(parents=True, exist_ok=True)
    bid = time.strftime("%Y%m%d-%H%M%S") + f"-{len([1 for _ in BACKUPS.glob('*.json')]) % 1000:03d}"
    b = {"id": bid, "ts": time.strftime("%Y-%m-%d %H:%M:%S"), "label": label, "item_id": item_id, "ops": ops}
    (BACKUPS / f"{bid}.json").write_text(json.dumps(b, default=lambda o: float(o) if isinstance(o, Decimal) else str(o)))
    return bid


def _capture(cu, table, keyvals):
    return {"table": table, "key": list(keyvals), "row": _fetch(cu, table, keyvals)}


def list_backups():
    out = []
    for f in sorted(BACKUPS.glob("*.json"), reverse=True) if BACKUPS.exists() else []:
        b = json.loads(f.read_text())
        out.append({"id": b["id"], "ts": b["ts"], "label": b["label"], "item_id": b["item_id"], "rows": len(b["ops"])})
    return out


def restore(bid):
    """Put every row in the backup back (REPLACE / delete-if-it-did-not-exist). Backs up current state first."""
    b = json.loads((BACKUPS / f"{bid}.json").read_text())
    db = zone_plot._db(); cu = db.cursor()
    pre, lines = [], []
    for op in b["ops"]:
        pre.append(_capture(cu, op["table"], op["key"]))
    pre_id = _save_backup(f"auto: before restore of {bid}", b["item_id"], pre)
    for op in b["ops"]:
        t, kv, row = op["table"], op["key"], op["row"]
        pk = _pk_for(t)
        where = " and ".join(f"{k}={lit(v)}" for k, v in zip(pk, kv))
        if row is None:
            cu.execute(f"delete from {t} where " + " and ".join(f"{k}=%s" for k in pk), tuple(kv))
            lines.append(f"DELETE FROM {t} WHERE {where};")
        else:
            cols = list(row)
            cu.execute(f"replace into {t} ({','.join(cols)}) values ({','.join(['%s'] * len(cols))})",
                       tuple(_dec(row[c]) for c in cols))
            lines.append(f"REPLACE INTO {t} ({','.join(cols)}) VALUES ({','.join(lit(row[c]) for c in cols)});")
    db.commit(); db.close()
    _journal(f"RESTORE from backup {bid} ({b['label']}); pre-restore state saved as {pre_id}", lines)
    return {"restored": len(b["ops"]), "pre_restore_backup": pre_id}


# ---- search -----------------------------------------------------------------------------------
def search(q, category="", limit=60):
    """Search item_basic joined with whichever type-table applies, by name. category is one of
    '', 'armor', 'weapon', 'consumable', 'puppet', 'furnishing', 'general'."""
    if not q or len(q) < 2:
        return []
    db = zone_plot._db(); cu = db.cursor()
    like = f"%{q}%"
    cu.execute("""select b.itemid, b.name, b.flags, b.stackSize,
                         e.level, e.jobs, e.slot,
                         w.skill, w.dmg, w.delay
                  from item_basic b
                  left join item_equipment e on e.itemId = b.itemid
                  left join item_weapon w on w.itemId = b.itemid
                  where b.name like %s order by b.name limit %s""", (like, limit))
    rows = cu.fetchall()
    db.close()
    out = []
    for itemid, name, flags, stack, level, jobs, slot, skill, wdmg, delay in rows:
        if skill is not None:
            type_name = "weapon"
        elif level is not None:
            type_name = "armor"
        else:
            type_name = "general/other"
        if category and category not in (type_name, "general" if type_name == "general/other" else ""):
            continue
        out.append({"itemid": itemid, "name": name, "type_name": type_name, "level": level,
                     "jobs": jobs, "skill": skill, "dmg": wdmg, "delay": delay})
    return out


def get_item(item_id):
    """Full live row(s) for one item, across every table it actually appears in, plus its
    real client-DAT record (level/jobs/etc as the client itself sees them) for comparison."""
    item_id = int(item_id)
    db = zone_plot._db(); cu = db.cursor()
    basic = _fetch(cu, "item_basic", [item_id])
    if basic is None:
        db.close()
        raise ValueError(f"item_basic.itemid={item_id} not found")
    rows = {"item_basic": basic}
    for table in ("item_equipment", "item_weapon", "item_usable", "item_puppet", "item_furnishing"):
        row = _fetch(cu, table, [item_id])
        if row is not None:
            rows[table] = row
    cu.execute("select modId, value from item_mods where itemId=%s order by modId", (item_id,))
    mods = [{"modId": r[0], "value": r[1], "name": dat.MOD_NAMES.get(r[0])} for r in cu.fetchall()]
    cu.execute("select modId, value, petType from item_mods_pet where itemId=%s order by petType, modId", (item_id,))
    pet_mods = [{"modId": r[0], "value": r[1], "petType": r[2],
                 "name": dat.MOD_NAMES.get(r[0]), "petTypeName": dat.PET_TYPE_NAMES.get(r[2])} for r in cu.fetchall()]
    cu.execute("select modId, value, latentId, latentParam from item_latents where itemId=%s order by latentId, modId", (item_id,))
    latents = [{"modId": r[0], "value": r[1], "latentId": r[2], "latentParam": r[3],
                "name": dat.MOD_NAMES.get(r[0]), "latentName": dat.LATENT_NAMES.get(r[2])} for r in cu.fetchall()]
    db.close()
    client = None
    try:
        rec = dat.read_client_item(item_id)
        if rec is not None:
            client = dat.item_to_dict(rec)
    except ValueError:
        client = None
    dat_status = {"target": dat.dat_target(), "pivot_root": str(dat.pivot_root())}
    if client:
        backups = dat.list_dat_backups()
        key = client.get("dat_ui", "").replace("/", "_").replace("\\", "_")
        dat_status["dat_ui"] = client.get("dat_ui")
        dat_status["record_index"] = client.get("record_index")
        dat_status["format"] = client.get("format")
        dat_status["category"] = client.get("category")
        dat_status["has_backup"] = any(b["key"] == key for b in backups)
    return {"item_id": item_id, "server": rows, "mods": mods, "pet_mods": pet_mods, "latents": latents,
            "client": client, "dat_status": dat_status}


# ---- item_mods (one-to-many: multiple (modId,value) rows per item, composite PK) ------------
# Architecturally different from every table in TABLES above -- not one row per item, so it gets
# its own get/set/delete instead of going through update_item(). modId meaning comes from
# dat.MOD_NAMES, itself extracted verbatim from C:\topaz\src\map\modifier.h's real `enum class
# Mod` (never hand-typed), per the project's "never invent a schema" rule.
def set_item_mod(item_id, mod_id, value, comment=""):
    """Insert or update one (itemId, modId) row. `value` may be 0 (that's a real value, not a
    delete) -- use delete_item_mod to actually remove a mod row."""
    item_id, mod_id, value = int(item_id), int(mod_id), int(value)
    db = zone_plot._db(); cu = db.cursor()
    cu.execute("select modId, value from item_mods where itemId=%s and modId=%s", (item_id, mod_id))
    before = cu.fetchone()
    bid = _save_backup(f"set item_mods {item_id}/{mod_id}", item_id,
                        [{"table": "item_mods", "key": [item_id, mod_id],
                          "row": {"itemId": item_id, "modId": mod_id, "value": before[1]} if before else None}])
    cu.execute("replace into item_mods (itemId, modId, value) values (%s,%s,%s)", (item_id, mod_id, value))
    db.commit(); db.close()
    was = f"was {before[1]}" if before else "was absent"
    sql = f"REPLACE INTO item_mods (itemId, modId, value) VALUES ({item_id},{mod_id},{value});"
    _journal(comment, [f"-- item_mods {item_id}/{mod_id} {was}  backup {bid}", sql])
    return {"sql": sql, "backup": bid}


def delete_item_mod(item_id, mod_id, comment=""):
    item_id, mod_id = int(item_id), int(mod_id)
    db = zone_plot._db(); cu = db.cursor()
    cu.execute("select value from item_mods where itemId=%s and modId=%s", (item_id, mod_id))
    before = cu.fetchone()
    if before is None:
        db.close()
        raise ValueError(f"item_mods itemId={item_id} modId={mod_id} not found")
    bid = _save_backup(f"delete item_mods {item_id}/{mod_id}", item_id,
                        [{"table": "item_mods", "key": [item_id, mod_id],
                          "row": {"itemId": item_id, "modId": mod_id, "value": before[0]}}])
    cu.execute("delete from item_mods where itemId=%s and modId=%s", (item_id, mod_id))
    db.commit(); db.close()
    sql = f"DELETE FROM item_mods WHERE itemId={item_id} AND modId={mod_id};"
    _journal(comment, [f"-- item_mods {item_id}/{mod_id} was {before[0]}  backup {bid}", sql])
    return {"sql": sql, "backup": bid}


def mod_names():
    """{modId: name} for every confirmed mod, for the UI's add-mod dropdown."""
    return dat.MOD_NAMES


# ---- item_mods_pet (one-to-many: multiple (modId,petType,value) rows per item, composite PK) --
# Same modId space as item_mods (dat.MOD_NAMES). petType is dat.PET_TYPE_NAMES, extracted from
# C:\topaz\src\map\modifier.h's `enum class PetModType` (8 entries: All/Avatar/Wyvern/Automaton/
# Harlequin/Valoredge/Sharpshot/Stormwaker) -- confirmed live via itemutils.cpp's item_mods_pet
# load query casting column 3 to PetModType. petType=0 (All) applies to every pet job.
def set_item_pet_mod(item_id, mod_id, pet_type, value, comment=""):
    """Insert or update one (itemId, modId, petType) row. `value` may be 0 (real value, not a
    delete) -- use delete_item_pet_mod to actually remove a row."""
    item_id, mod_id, pet_type, value = int(item_id), int(mod_id), int(pet_type), int(value)
    db = zone_plot._db(); cu = db.cursor()
    cu.execute("select value from item_mods_pet where itemId=%s and modId=%s and petType=%s", (item_id, mod_id, pet_type))
    before = cu.fetchone()
    bid = _save_backup(f"set item_mods_pet {item_id}/{mod_id}/{pet_type}", item_id,
                        [{"table": "item_mods_pet", "key": [item_id, mod_id, pet_type],
                          "row": {"itemId": item_id, "modId": mod_id, "value": before[0], "petType": pet_type} if before else None}])
    cu.execute("replace into item_mods_pet (itemId, modId, value, petType) values (%s,%s,%s,%s)", (item_id, mod_id, value, pet_type))
    db.commit(); db.close()
    was = f"was {before[0]}" if before else "was absent"
    sql = f"REPLACE INTO item_mods_pet (itemId, modId, value, petType) VALUES ({item_id},{mod_id},{value},{pet_type});"
    _journal(comment, [f"-- item_mods_pet {item_id}/{mod_id}/{pet_type} {was}  backup {bid}", sql])
    return {"sql": sql, "backup": bid}


def delete_item_pet_mod(item_id, mod_id, pet_type, comment=""):
    item_id, mod_id, pet_type = int(item_id), int(mod_id), int(pet_type)
    db = zone_plot._db(); cu = db.cursor()
    cu.execute("select value from item_mods_pet where itemId=%s and modId=%s and petType=%s", (item_id, mod_id, pet_type))
    before = cu.fetchone()
    if before is None:
        db.close()
        raise ValueError(f"item_mods_pet itemId={item_id} modId={mod_id} petType={pet_type} not found")
    bid = _save_backup(f"delete item_mods_pet {item_id}/{mod_id}/{pet_type}", item_id,
                        [{"table": "item_mods_pet", "key": [item_id, mod_id, pet_type],
                          "row": {"itemId": item_id, "modId": mod_id, "value": before[0], "petType": pet_type}}])
    cu.execute("delete from item_mods_pet where itemId=%s and modId=%s and petType=%s", (item_id, mod_id, pet_type))
    db.commit(); db.close()
    sql = f"DELETE FROM item_mods_pet WHERE itemId={item_id} AND modId={mod_id} AND petType={pet_type};"
    _journal(comment, [f"-- item_mods_pet {item_id}/{mod_id}/{pet_type} was {before[0]}  backup {bid}", sql])
    return {"sql": sql, "backup": bid}


def pet_type_names():
    """{petType: name} for the UI's add-pet-mod dropdown."""
    return dat.PET_TYPE_NAMES


# ---- item_latents (one-to-many: conditional/hidden mods, full 5-column composite PK) ----------
# PK is (itemId, modId, value, latentId, latentParam) -- `value` is part of the key itself (unlike
# item_mods/item_mods_pet), so there is no single-row "update the value" operation: changing value
# makes a different row by definition. This gives add/delete only, no set-in-place. modId is the
# same Mod enum as item_mods (dat.MOD_NAMES); latentId is dat.LATENT_NAMES, extracted from
# C:\topaz\src\map\latent_effect.h's real `enum class LATENT` -- confirmed live via itemutils.cpp's
# item_latents load query casting column 1 to Mod and column 3 to LATENT, then calling
# CItemEquipment::addLatent(latentId, latentParam, modID, value). latentParam's meaning is
# condition-specific (see the comment baked into each LATENT_NAMES entry) so it stays a raw number.
def add_item_latent(item_id, mod_id, value, latent_id, latent_param, comment=""):
    item_id, mod_id, value, latent_id, latent_param = int(item_id), int(mod_id), int(value), int(latent_id), int(latent_param)
    db = zone_plot._db(); cu = db.cursor()
    cu.execute("select 1 from item_latents where itemId=%s and modId=%s and value=%s and latentId=%s and latentParam=%s",
               (item_id, mod_id, value, latent_id, latent_param))
    if cu.fetchone():
        db.close()
        raise ValueError("an identical item_latents row already exists")
    bid = _save_backup(f"add item_latents {item_id}/{mod_id}/{latent_id}", item_id,
                        [{"table": "item_latents", "key": [item_id, mod_id, value, latent_id, latent_param], "row": None}])
    cu.execute("insert into item_latents (itemId, modId, value, latentId, latentParam) values (%s,%s,%s,%s,%s)",
               (item_id, mod_id, value, latent_id, latent_param))
    db.commit(); db.close()
    sql = f"INSERT INTO item_latents (itemId, modId, value, latentId, latentParam) VALUES ({item_id},{mod_id},{value},{latent_id},{latent_param});"
    _journal(comment, [f"-- item_latents {item_id} add  backup {bid}", sql])
    return {"sql": sql, "backup": bid}


def delete_item_latent(item_id, mod_id, value, latent_id, latent_param, comment=""):
    item_id, mod_id, value, latent_id, latent_param = int(item_id), int(mod_id), int(value), int(latent_id), int(latent_param)
    db = zone_plot._db(); cu = db.cursor()
    cu.execute("select 1 from item_latents where itemId=%s and modId=%s and value=%s and latentId=%s and latentParam=%s",
               (item_id, mod_id, value, latent_id, latent_param))
    if not cu.fetchone():
        db.close()
        raise ValueError("item_latents row not found")
    bid = _save_backup(f"delete item_latents {item_id}/{mod_id}/{latent_id}", item_id,
                        [{"table": "item_latents", "key": [item_id, mod_id, value, latent_id, latent_param],
                          "row": {"itemId": item_id, "modId": mod_id, "value": value, "latentId": latent_id, "latentParam": latent_param}}])
    cu.execute("delete from item_latents where itemId=%s and modId=%s and value=%s and latentId=%s and latentParam=%s",
               (item_id, mod_id, value, latent_id, latent_param))
    db.commit(); db.close()
    sql = f"DELETE FROM item_latents WHERE itemId={item_id} AND modId={mod_id} AND value={value} AND latentId={latent_id} AND latentParam={latent_param};"
    _journal(comment, [f"-- item_latents {item_id} delete  backup {bid}", sql])
    return {"sql": sql, "backup": bid}


def latent_names():
    """{latentId: name} for the UI's add-latent dropdown."""
    return dat.LATENT_NAMES


# ---- edits ----------------------------------------------------------------------------------
def update_item(item_id, table, fields, comment="", sync_client=True):
    """Update one row of one item_* table live, backed up + journalled. `fields` is a dict of
    column -> new value for that table only. If sync_client and the table/fields overlap with a
    field the client DAT also stores (level, jobs, slots, races, superior_level for item_equipment;
    dmg/delay/skill for item_weapon; flags/stack for item_basic), the client DAT record for this
    item is patched too, so the two stay in agreement."""
    item_id = int(item_id)
    if table not in TABLES:
        raise ValueError(f"unknown item table {table!r}")
    key = TABLES[table][0]
    db = zone_plot._db(); cu = db.cursor()
    op = _capture(cu, table, [item_id])
    if op["row"] is None:
        db.close()
        raise ValueError(f"{table}.{key}={item_id} not found")
    cols = _cols(cu, table)
    bad = [k for k in fields if k not in cols]
    if bad:
        db.close()
        raise ValueError(f"{table} has no column(s): {', '.join(bad)}")
    bid = _save_backup(f"edit {table} {item_id}", item_id, [op])
    set_clause = ", ".join(f"{k}=%s" for k in fields)
    cu.execute(f"update {table} set {set_clause} where {key}=%s", tuple(fields.values()) + (item_id,))
    db.commit(); db.close()
    o = op["row"]
    was = ", ".join(f"{k} {o.get(k)}" for k in fields)
    sql = f"UPDATE {table} SET {', '.join(f'{k}={lit(v)}' for k, v in fields.items())} WHERE {key}={item_id};"
    _journal(comment, [f"-- was ({was})  backup {bid}", sql])

    client_report = None
    if sync_client:
        client_fields = _map_to_client_fields(table, fields)
        if client_fields:
            try:
                client_report = dat.patch_client_item(item_id, client_fields)
            except ValueError as ex:
                client_report = {"ok": False, "error": str(ex)}
    return {"sql": sql, "backup": bid, "client": client_report}


def _map_to_client_fields(table, fields):
    """Translate a server-column dict into the equivalent item_dat_tools field names, for the
    subset of columns that really exist on both sides. Anything server-only (MId, shieldSize,
    scriptType, rslot, ilvl_skill/parry/macc, hit, unlock_points, subskill, dmgType, aH,
    BaseSell, NoSale, sortname, validTargets/activation/animation/...) is deliberately left
    server-only -- the client record has no field for it, so there's nothing to sync."""
    out = {}
    if table == "item_equipment":
        for k in ("level", "jobs", "slot", "shieldSize"):
            if k in fields:
                out["slots" if k == "slot" else ("shield_size" if k == "shieldSize" else k)] = fields[k]
    elif table == "item_weapon":
        for k in ("dmg", "delay", "skill"):
            if k in fields:
                out[k] = fields[k]
    elif table == "item_basic":
        if "flags" in fields:
            out["flags"] = fields["flags"]
        if "stackSize" in fields:
            out["stack"] = fields["stackSize"]
        # item_basic.name is NOT real display text -- it's the internal lowercase_underscore
        # name (matches sortname), same style as item_equipment/item_weapon.name. Client DAT's
        # name/singular/plural/description come from item_dat_tools' own text fields, never from
        # here. A prior version of this mapping forwarded item_basic.name into the client DAT's
        # 'name' field on every save (even when unchanged, since the edit UI always submits the
        # whole row) -- patch_client_item's text-key path then defaulted singular/plural from
        # that underscore name AND blanked description (no description supplied), corrupting the
        # item's real client-visible name/flavor text. See item 10478 (Euxine Coat +3), 2026-09-24.
    return out


def create_item(category, item_type, entry, comment=""):
    """Allocate a real free client-DAT slot in `category` (e.g. 'Armor_1', 'Weapons',
    'Consumable' -- see item_dat_tools.ITEM_DATS), write the new item record there, then insert
    matching rows into item_basic + whichever type-table(s) TYPE_TABLES[item_type] says this
    item_type uses, all at that SAME id. Never invents an id -- the id comes only from a real
    free DAT slot found by item_dat_tools.free_slots(), per CLAUDE.md's core rule."""
    item_type = int(item_type)
    client_result = dat.inject_client_item(category, entry)
    item_id = client_result["item_id"]

    db = zone_plot._db(); cu = db.cursor()
    cu.execute("select 1 from item_basic where itemid=%s", (item_id,))
    if cu.fetchone():
        db.close()
        raise ValueError(f"item_basic already has itemid={item_id} -- DAT slot and DB are out of sync, investigate before retrying")

    basic_row = {
        "itemid": item_id, "subid": 0,
        "name": entry.get("name", f"item_{item_id}"), "sortname": entry.get("singular", entry.get("name", ""))[:20],
        "stackSize": int(entry.get("stack", 1)), "flags": int(entry.get("flags", dat.encode_flags(entry.get("flags_decoded", [])))),
        "aH": int(entry.get("aH", 99)), "NoSale": int(entry.get("NoSale", 0)), "BaseSell": int(entry.get("BaseSell", 0)),
    }
    inserts = [("item_basic", basic_row)]

    for table in TYPE_TABLES.get(item_type, []):
        if table == "item_equipment":
            inserts.append(("item_equipment", {
                "itemId": item_id, "name": basic_row["name"], "level": int(entry.get("level", 1)),
                "ilevel": int(entry.get("ilevel", 0)), "jobs": int(entry.get("jobs", dat.encode_jobs(entry.get("jobs_list", [])))),
                "MId": int(entry.get("MId", 0)), "shieldSize": int(entry.get("shield_size", 0)),
                "scriptType": int(entry.get("scriptType", 0)), "slot": int(entry.get("slots", entry.get("slot", 0))),
                "rslot": int(entry.get("rslot", 0)),
            }))
        elif table == "item_weapon":
            inserts.append(("item_weapon", {
                "itemId": item_id, "name": basic_row["name"], "skill": int(entry.get("skill", 0)),
                "subskill": int(entry.get("subskill", 0)), "ilvl_skill": int(entry.get("ilvl_skill", 0)),
                "ilvl_parry": int(entry.get("ilvl_parry", 0)), "ilvl_macc": int(entry.get("ilvl_macc", 0)),
                "dmgType": int(entry.get("dmgType", entry.get("kind", 0))), "hit": int(entry.get("hit", 1)),
                "delay": int(entry.get("delay", 0)), "dmg": int(entry.get("dmg", 0)),
                "unlock_points": int(entry.get("unlock_points", 0)),
            }))
        elif table == "item_usable":
            inserts.append(("item_usable", {
                "itemid": item_id, "name": basic_row["name"], "validTargets": int(entry.get("validTargets", 1)),
                "activation": int(entry.get("activation", 0)), "animation": int(entry.get("animation", 0)),
                "animationTime": int(entry.get("animationTime", 0)), "maxCharges": int(entry.get("max_charges", entry.get("maxCharges", 0))),
                "useDelay": int(entry.get("use_delay", entry.get("useDelay", 0))), "reuseDelay": int(entry.get("reuse_delay", entry.get("reuseDelay", 0))),
                "aoe": int(entry.get("aoe", 0)),
            }))
        elif table == "item_puppet":
            inserts.append(("item_puppet", {
                "itemid": item_id, "name": basic_row["name"], "slot": int(entry.get("puppet_slot", entry.get("slot", 0))),
                "element": int(entry.get("element_charge", entry.get("element", 0))),
            }))
        elif table == "item_furnishing":
            inserts.append(("item_furnishing", {
                "itemid": item_id, "name": basic_row["name"], "storage": int(entry.get("storage", 0)),
                "moghancement": int(entry.get("moghancement", 0)), "element": int(entry.get("element", 0)),
                "aura": int(entry.get("aura", 0)),
            }))

    lines = []
    ops = []
    for table, row in inserts:
        cols = list(row)
        cu.execute(f"insert into {table} ({','.join(cols)}) values ({','.join(['%s'] * len(cols))})", tuple(row[c] for c in cols))
        lines.append(f"INSERT INTO {table} ({','.join(cols)}) VALUES ({','.join(lit(row[c]) for c in cols)});")
        ops.append({"table": table, "key": [item_id], "row": None})
    db.commit(); db.close()

    bid = _save_backup(f"create item {item_id} ({basic_row['name']}) in {category}", item_id, ops)
    _journal(comment or f"CREATE item {item_id} in {category}", [f"-- backup {bid}", f"-- client DAT: {client_result}"] + lines)
    return {"item_id": item_id, "backup": bid, "sql": "\n".join(lines), "client": client_result}


def clone_template(item_id):
    """Build a create_item()-ready {category, item_type, entry} template from an existing item,
    so the New Item form can start from a real, verified example instead of a blank slate needing
    every field hand-typed. Pulls display text/level/jobs/flags/dmg/etc from the source item's
    client DAT record (authoritative -- what the game actually reads) and the handful of
    server-only columns the client record has no field for (aH/NoSale/BaseSell, ilvl_skill/parry/
    macc, hit, subskill, unlock_points, validTargets/activation/animation/animationTime/
    maxCharges/useDelay/reuseDelay/aoe, puppet slot/element, storage/moghancement/element/aura)
    from SQL. Never invents anything -- every value traces back to the source item's own real
    rows/record, same as every other id/value in this project."""
    item_id = int(item_id)
    data = get_item(item_id)
    client = data.get("client")
    if client is None:
        raise ValueError(f"item {item_id} has no client DAT record to clone from")
    basic = data["server"].get("item_basic", {})
    equip = data["server"].get("item_equipment", {})
    weapon = data["server"].get("item_weapon", {})
    usable = data["server"].get("item_usable", {})
    puppet = data["server"].get("item_puppet", {})
    furnishing = data["server"].get("item_furnishing", {})

    entry = {
        "name": client.get("name", ""), "singular": client.get("singular", ""),
        "plural": client.get("plural", ""), "description": client.get("description", ""),
        "stack": client.get("stack", 1), "flags_decoded": client.get("flags_decoded", []),
        "aH": basic.get("aH", 99), "NoSale": basic.get("NoSale", 0), "BaseSell": basic.get("BaseSell", 0),
    }
    if "level" in client:
        entry.update({
            "level": client.get("level", 1), "jobs_list": client.get("jobs_list", []),
            "slots": client.get("slots", 0), "shield_size": equip.get("shieldSize", 0),
            "scriptType": equip.get("scriptType", 0), "rslot": equip.get("rslot", 0),
            "MId": equip.get("MId", 0), "ilevel": equip.get("ilevel", 0),
        })
    if client.get("type") == 4:
        entry.update({
            "skill": client.get("skill", 0), "dmg": client.get("dmg", 0), "delay": client.get("delay", 0),
            "dmgType": client.get("kind", 0),
            "subskill": weapon.get("subskill", 0), "ilvl_skill": weapon.get("ilvl_skill", 0),
            "ilvl_parry": weapon.get("ilvl_parry", 0), "ilvl_macc": weapon.get("ilvl_macc", 0),
            "hit": weapon.get("hit", 1), "unlock_points": weapon.get("unlock_points", 0),
        })
    if usable:
        entry.update({k: usable.get(k, 0) for k in
                       ("validTargets", "activation", "animation", "animationTime",
                        "maxCharges", "useDelay", "reuseDelay", "aoe")})
    if puppet:
        entry.update({"puppet_slot": puppet.get("slot", 0), "element_charge": puppet.get("element", 0)})
    if furnishing:
        entry.update({k: furnishing.get(k, 0) for k in ("storage", "moghancement", "element", "aura")})

    return {"category": client.get("category", ""), "item_type": client.get("type", 0), "entry": entry,
            "source_item_id": item_id, "mods": data["mods"], "pet_mods": data["pet_mods"], "latents": data["latents"]}


def delete_item(item_id, comment=""):
    """Remove an item's rows from every item_* table it appears in. Does NOT touch the client
    DAT record (there is no 'empty' terminator write path here -- the slot is simply left as-is
    and will show up again as a free slot the next time item_dat_tools.free_slots() scans past
    it, since its name string is untouched... note this only actually frees the slot if the DAT
    record's name is blanked separately; left as a manual follow-up, matching zone_edit.py's
    stance of surfacing rather than auto-cleaning ambiguous state)."""
    item_id = int(item_id)
    db = zone_plot._db(); cu = db.cursor()
    ops = []
    for table in TABLES:
        op = _capture(cu, table, [item_id])
        if op["row"] is not None:
            ops.append(op)
    cu.execute("select modId, value from item_mods where itemId=%s", (item_id,))
    mod_rows = cu.fetchall()
    for mod_id, value in mod_rows:
        ops.append({"table": "item_mods", "key": [item_id, mod_id],
                     "row": {"itemId": item_id, "modId": mod_id, "value": value}})
    cu.execute("select modId, value, petType from item_mods_pet where itemId=%s", (item_id,))
    pet_mod_rows = cu.fetchall()
    for mod_id, value, pet_type in pet_mod_rows:
        ops.append({"table": "item_mods_pet", "key": [item_id, mod_id, pet_type],
                     "row": {"itemId": item_id, "modId": mod_id, "value": value, "petType": pet_type}})
    cu.execute("select modId, value, latentId, latentParam from item_latents where itemId=%s", (item_id,))
    latent_rows = cu.fetchall()
    for mod_id, value, latent_id, latent_param in latent_rows:
        ops.append({"table": "item_latents", "key": [item_id, mod_id, value, latent_id, latent_param],
                     "row": {"itemId": item_id, "modId": mod_id, "value": value, "latentId": latent_id, "latentParam": latent_param}})
    if not ops:
        db.close()
        raise ValueError(f"no item_* rows found for itemid={item_id}")
    bid = _save_backup(f"delete item {item_id}", item_id, ops)
    lines = []
    for op in ops:
        if op["table"] == "item_mods":
            mod_id = op["key"][1]
            cu.execute("delete from item_mods where itemId=%s and modId=%s", (item_id, mod_id))
            lines.append(f"DELETE FROM item_mods WHERE itemId={item_id} AND modId={mod_id};")
            continue
        if op["table"] == "item_mods_pet":
            mod_id, pet_type = op["key"][1], op["key"][2]
            cu.execute("delete from item_mods_pet where itemId=%s and modId=%s and petType=%s", (item_id, mod_id, pet_type))
            lines.append(f"DELETE FROM item_mods_pet WHERE itemId={item_id} AND modId={mod_id} AND petType={pet_type};")
            continue
        if op["table"] == "item_latents":
            mod_id, value, latent_id, latent_param = op["key"][1], op["key"][2], op["key"][3], op["key"][4]
            cu.execute("delete from item_latents where itemId=%s and modId=%s and value=%s and latentId=%s and latentParam=%s",
                       (item_id, mod_id, value, latent_id, latent_param))
            lines.append(f"DELETE FROM item_latents WHERE itemId={item_id} AND modId={mod_id} AND value={value} AND latentId={latent_id} AND latentParam={latent_param};")
            continue
        table, key = op["table"], TABLES[op["table"]][0]
        cu.execute(f"delete from {table} where {key}=%s", (item_id,))
        lines.append(f"DELETE FROM {table} WHERE {key}={item_id};")
    db.commit(); db.close()
    _journal(comment, [f"-- backup {bid}"] + lines)
    return {"sql": "\n".join(lines), "backup": bid,
            "warning": "client DAT record left in place (see delete_item docstring) -- clear its name manually via the edit form if you want the slot to read as free"}
